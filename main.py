import argparse

from mcap.reader import make_reader
from cdr import decode_cdr, UInt32
from pydantic import BaseModel

MESSAGE_SCHEMA_NAME = "foxglove.CompressedVideo"

class Timestamp(BaseModel):
    sec: UInt32
    nsec: UInt32


class CompressedVideo(BaseModel):
    timestamp: Timestamp
    frame_id: str
    data: bytes
    format: str


def list_video_messages(mcap_file):
    with open(mcap_file, "rb") as f:
        reader = make_reader(f)
        video_topics = set()
        for schema, channel, message in reader.iter_messages():
            if schema.name == MESSAGE_SCHEMA_NAME:
                video_topics.add(channel.topic)

        if not video_topics:
            print("No foxglove.CompressedVideo messages found")
            return

        print("\nFound foxglove.CompressedVideo messages on topics:")
        for topic in sorted(video_topics):
            print(f"- {topic}")

def extract_video(mcap_file, topic):
    print(f"Extracting video from topic {topic} in {mcap_file}")

    # Import GStreamer dependencies at top level
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib

    # Initialize GStreamer once
    Gst.init(None)

    # Create pipeline
    pipeline = Gst.parse_launch(
        "appsrc name=src ! "
        "h264parse ! "
        "avdec_h264 ! "
        "videoconvert ! "
        "autovideosink"
    )

    # Get appsrc element and set caps
    src = pipeline.get_by_name("src")
    if not src:
        raise RuntimeError("Failed to get appsrc element")

    src.set_property("caps", Gst.Caps.from_string(
        "video/x-h264,stream-format=byte-stream,alignment=au"
    ))

    # Set pipeline to playing state
    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        raise RuntimeError("Failed to set pipeline to playing state")

    # Create event loop
    loop = GLib.MainLoop()

    try:
        # Process video frames
        with open(mcap_file, "rb") as f:
            reader = make_reader(f)
            for schema, channel, message in reader.iter_messages():
                if schema.name == MESSAGE_SCHEMA_NAME and channel.topic == topic:
                    decoded = decode_cdr(CompressedVideo, message.data)

                    # Push buffer to pipeline
                    buf = Gst.Buffer.new_wrapped(decoded.data)
                    if src.emit("push-buffer", buf) != Gst.FlowReturn.OK:
                        raise RuntimeError("Error pushing buffer to pipeline")

        # Signal end of stream
        src.emit("end-of-stream")

        # Run pipeline until EOS or interrupted
        loop.run()

    except KeyboardInterrupt:
        print("\nPlayback interrupted")
    except Exception as e:
        print(f"\nError during playback: {e}")
    finally:
        # Clean up
        pipeline.set_state(Gst.State.NULL)
        loop.quit()

def main():
    parser = argparse.ArgumentParser(description="List topics containing foxglove.CompressedVideo messages in an MCAP file or extract a specific video topic")
    parser.add_argument("mcap_file", help="Path to MCAP file")
    parser.add_argument("topic", nargs="?", help="Topic name to extract video from")
    args = parser.parse_args()

    if not args.topic:
        list_video_messages(args.mcap_file)
        return

    extract_video(args.mcap_file, args.topic)


if __name__ == "__main__":
    main()