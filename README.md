# mcap / foxglove video extract

Extract videos from mcap files with messages that follow _foxglove.CompressedVideo_

Usage:
```sh
$ uv run main.py ~/Downloads/recorder_20250822_014827.mcap
    Found foxglove.CompressedVideo messages on topics:
    - video/RadCam1921682100/stream (93s)
    - video/RadCam1921682101/stream (93s)
    - video/UDPStream0/stream (94s)

$ uv run main.py ~/Downloads/recorder_20250822_014827.mcap video/UDPStream0/stream
    warning: No `requires-python` value found in the workspace. Defaulting to `>=3.11`.
    Extracting video from topic video/UDPStream0/stream in /home/patrick/Downloads/recorder_20250822_014827.mcap
    Saving video to video_UDPStream0_stream.mp4
    Successfully finished writing video_UDPStream0_stream.mp4

$ uv run main.py ~/Downloads/recorder_20250822_014827.mcap all
    Extracting video from topic video/UDPStream0/stream in /home/patrick/Downloads/recorder_20250822_014827.mcap
    Saving video to video_UDPStream0_stream.mp4
    Successfully finished writing video_UDPStream0_stream.mp4
    Extracting video from topic video/RadCam1921682101/stream in /home/patrick/Downloads/recorder_20250822_014827.mcap
    Saving video to video_RadCam1921682101_stream.mp4
    Successfully finished writing video_RadCam1921682101_stream.mp4
    Extracting video from topic video/RadCam1921682100/stream in /home/patrick/Downloads/recorder_20250822_014827.mcap
    Saving video to video_RadCam1921682100_stream.mp4
    Successfully finished writing video_RadCam1921682100_stream.mp4
```
