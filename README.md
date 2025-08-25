# mcap-foxglove-video-extract

## Usage
```
usage: main.py [-h] [--output OUTPUT] mcap_file [topic]

List topics containing foxglove.CompressedVideo messages in an MCAP file or
extract a specific video topic

positional arguments:
  mcap_file        Path to MCAP file
  topic            Topic name to extract video from, use 'all' to extract all
                   topics

options:
  -h, --help       show this help message and exit
  --output OUTPUT  Output directory

```

```sh
docker run -v ~/Downloads:/video extractor /video/recorder_20250822_014827.mcap video/UDPStream0/stream --output /video
```