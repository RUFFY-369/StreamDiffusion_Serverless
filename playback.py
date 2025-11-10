
import argparse
import time
import subprocess
import threading
import queue
import sys
import cv2
import numpy as np

def get_highest_res_stream_index(url):
    # Use ffprobe to get all video streams and pick the highest resolution
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_streams", "-select_streams", "v", "-of", "json", url
    ]
    try:
        out = subprocess.check_output(probe_cmd, stderr=subprocess.STDOUT).decode()
        import json
        info = json.loads(out)
        best_idx = None
        best_area = 0
        best_w = 0
        best_h = 0
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video':
                w = stream.get('width', 0)
                h = stream.get('height', 0)
                idx = stream.get('index')
                try:
                    area = int(w) * int(h)
                    if area > best_area:
                        best_area = area
                        best_idx = idx
                        best_w = w
                        best_h = h
                except Exception:
                    continue
        if best_idx is not None:
            print(f"[INFO] Selected video stream index: {best_idx} (resolution: {best_w}x{best_h})")
            return best_idx, best_w, best_h
        else:
            print("[WARN] Could not find a video stream.")
            return 0, 640, 360
    except Exception as e:
        print(f"[WARN] Could not get stream index: {e}")
        return 0, 640, 360

# Try to import torch to check for GPU
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    GPU_AVAILABLE = False

STREAM_URL = "https://lvpr.tv/?v=0729c3sb3s9rig46"

def build_ffmpeg_cmd(url, use_gpu, width=None, height=None):
    # Find the highest resolution video stream index
    stream_idx, stream_w, stream_h = get_highest_res_stream_index(url)
    # Use the selected stream's width/height unless overridden
    out_w = width if width else stream_w
    out_h = height if height else stream_h
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "info",
        "-fflags", "+genpts",
        "-i", url,
        "-map", f"0:{stream_idx}",
        "-an",  # no audio
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
    ]
    if use_gpu:
        # Try NVDEC (Nvidia GPU decode)
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "info",
            "-hwaccel", "cuda",
            "-hwaccel_output_format", "cuda",
            "-i", url,
            "-map", f"0:{stream_idx}",
            "-an",
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
        ]
    if out_w and out_h:
        cmd += ["-vf", f"scale={out_w}:{out_h}"]
    cmd.append("-")  # output to stdout
    print(f"[DEBUG] ffmpeg command: {' '.join(cmd)}")
    return cmd, out_w, out_h

def get_video_info(url):
    # Get width, height, fps using ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1", url
    ]
    try:
        out = subprocess.check_output(probe_cmd, stderr=subprocess.STDOUT).decode().splitlines()
        width, height, fps = int(out[0]), int(out[1]), out[2]
        num, denom = map(int, fps.split("/"))
        fps = num / denom if denom != 0 else 30
        return width, height, fps
    except Exception as e:
        print(f"[WARN] Could not get video info: {e}")
        return 640, 360, 30

def frame_reader(cmd, width, height, frame_queue, stop_event):
    while not stop_event.is_set():
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=10**8)
            frame_size = width * height * 3
            print(f"[DEBUG] Expecting frame size: {frame_size} bytes ({width}x{height})")
            while not stop_event.is_set():
                raw = proc.stdout.read(frame_size)
                print(f"[DEBUG] Read {len(raw) if raw else 0} bytes from ffmpeg pipe")
                if not raw or len(raw) < frame_size:
                    print("[INFO] Stream ended or dropped, reconnecting...")
                    break
                try:
                    frame = np.frombuffer(raw, np.uint8).reshape((height, width, 3))
                except Exception as e:
                    print(f"[ERROR] Could not reshape frame: {e}")
                    continue
                frame_queue.put(frame)
                print("[DEBUG] Frame put into queue")
            proc.kill()
            time.sleep(1)  # Wait before reconnect
        except Exception as e:
            print(f"[ERROR] Frame reader error: {e}")
            time.sleep(2)

def main():
    parser = argparse.ArgumentParser(description="Video Stream Frame Grabber with GPU/CPU fallback")
    parser.add_argument("--url", type=str, default=STREAM_URL, help="Stream URL (HLS/RTMP)")
    parser.add_argument("--no-preview", action="store_true", help="Run headless (no window)")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU decoding")
    parser.add_argument("--width", type=int, default=None, help="Resize width")
    parser.add_argument("--height", type=int, default=None, help="Resize height")
    args = parser.parse_args()

    # Try GPU first unless forced CPU
    use_gpu = GPU_AVAILABLE and not args.force_cpu
    tried_gpu = False
    frame_queue = queue.Queue(maxsize=30)
    stop_event = threading.Event()

    while True:
        # Always get the correct stream index and dimensions
        cmd, width, height = build_ffmpeg_cmd(args.url, use_gpu, args.width, args.height)
        print(f"[INFO] Starting ffmpeg with {'GPU' if use_gpu else 'CPU'} decoding...")
        reader_thread = threading.Thread(target=frame_reader, args=(cmd, width, height, frame_queue, stop_event))
        reader_thread.start()
        last_time = time.time()
        frame_count = 0
        print("[DEBUG] Main loop started")
        try:
            while not stop_event.is_set():
                print("[DEBUG] Main loop waiting for frame...")
                try:
                    frame = frame_queue.get(timeout=5)
                    print("[DEBUG] Frame received from queue")
                except queue.Empty:
                    print("[WARN] No frames received, waiting again...")
                    continue
                frame_count += 1
                now = time.time()
                if now - last_time >= 1.0:
                    print(f"[FPS] {frame_count} frames/sec")
                    frame_count = 0
                    last_time = now
                if not args.no_preview:
                    cv2.imshow("Stream Preview", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("[INFO] Quitting...")
                        stop_event.set()
                        break
        except KeyboardInterrupt:
            print("[INFO] Interrupted by user.")
            stop_event.set()
            break
        finally:
            stop_event.set()
            reader_thread.join()
            if not args.no_preview:
                cv2.destroyAllWindows()
        # If GPU failed, try CPU
        if use_gpu and not tried_gpu:
            print("[WARN] GPU decoding failed, falling back to CPU...")
            use_gpu = False
            tried_gpu = True
            stop_event.clear()
            continue
        break

if __name__ == "__main__":
    main()
