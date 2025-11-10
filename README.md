# StreamDiffusion Serverless Playback

This repository provides a simple Python script (`playback.py`) to fetch and display video frames from a Daydream API output stream. It is designed to help you view, process, or republish AI-generated video streams from the Daydream StreamDiffusion pipeline.

## Purpose
- **Fetches video frames** from a Livepeer playback URL (e.g., from Daydream's StreamDiffusion API output).
- **Displays the video** locally using OpenCV, with optional headless mode.
- **Supports GPU acceleration** (CUDA) for efficient decoding if available.
- **Can be extended** to republish or process frames for downstream inference or visualization.

## Typical Workflow
1. **Create a Stream** using the Daydream API to get an input (WHIP) and output (playback) URL.
2. **Send video** to the WHIP URL (e.g., using OBS Studio).
3. **Retrieve the output_playback_id** from the API response.
4. **Run the script** to fetch and display frames from the playback stream:
   ```bash
   python playback.py --url "https://livepeercdn.studio/hls/<output_playback_id>/index.m3u8"
   ```
5. **(Optional)** Extend the script to publish or process frames as needed for your use case.

## Example Use Case
- Run StreamDiffusion serverless using the Daydream API.
- Use `playback.py` to fetch the AI-processed video stream.
- Display the output locally or forward frames to another service for further inference or visualization.

## Requirements
- Python 3.x
- ffmpeg & ffprobe (installed and in PATH)
- OpenCV (`cv2`)
- numpy
- (Optional) torch (for GPU detection)


## Notes
- The script automatically selects the highest resolution stream and can use GPU decoding if available.
- You can run in headless mode (no preview window) with `--no-preview`.
- The script is easily extensible for custom frame processing or publishing.

## References
- [Daydream API Documentation](https://docs.daydream.live/)
- [Livepeer Studio](https://livepeer.studio/)

---

**This repo is a starting point for building serverless, AI-powered video streaming applications using Daydream and Livepeer.**
