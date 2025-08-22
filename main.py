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


def get_video_topics(mcap_file):
    video_topics = set()
    with open(mcap_file, "rb") as f:
        reader = make_reader(f)
        for schema, channel, message in reader.iter_messages():
            if schema.name == MESSAGE_SCHEMA_NAME:
                video_topics.add(channel.topic)
    return video_topics


def get_topic_duration(mcap_file, topic) -> int:
    first_timestamp = None
    last_timestamp = None

    with open(mcap_file, "rb") as f:
        reader = make_reader(f)
        for schema, channel, message in reader.iter_messages():
            if schema.name == MESSAGE_SCHEMA_NAME and channel.topic == topic:
                # Decode the message data to get the timestamp
                try:
                    video_msg = decode_cdr(CompressedVideo, message.data)
                except Exception:
                    continue
                ts = video_msg.timestamp
                # Convert to nanoseconds for comparison
                t_ns = int(ts.sec) * 1_000_000_000 + int(ts.nsec)
                if first_timestamp is None:
                    first_timestamp = t_ns
                last_timestamp = t_ns

    if first_timestamp is not None and last_timestamp is not None and last_timestamp >= first_timestamp:
        duration_ns = last_timestamp - first_timestamp
        return duration_ns // 1_000_000_000
    return 0


def list_video_messages(mcap_file):
    video_topics = get_video_topics(mcap_file)
    if not video_topics:
        print("No foxglove.CompressedVideo messages found")
        return

    print("\nFound foxglove.CompressedVideo messages on topics:")
    for topic in sorted(video_topics):
        print(f"- {topic} ({get_topic_duration(mcap_file, topic)}s)")

def extract_video(mcap_file, topic):
    print(f"Extracting video from topic {topic} in {mcap_file}")

    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib

    Gst.init(None)

    safe_topic = topic.replace("/", "_")
    output_filename = f"{safe_topic}.mp4"
    print(f"Saving video to {output_filename}")

    # Updated pipeline: we still use appsrc with caps
    pipeline = Gst.parse_launch(
        f"appsrc name=src do-timestamp=true "
        f"caps=video/x-h264,stream-format=byte-stream,framerate=30/1 ! "
        f"h264parse ! "
        f"mp4mux faststart=true ! "
        f"filesink location={output_filename}"
    )

    src = pipeline.get_by_name("src")

    # 🔧 Configure appsrc to handle timing
    src.set_property("do-timestamp", True)          # Auto-timestamp if we don't set
    src.set_property("format", Gst.Format.TIME)     # Expect time-based input

    ret = pipeline.set_state(Gst.State.PLAYING)
    if ret == Gst.StateChangeReturn.FAILURE:
        raise RuntimeError("Failed to set pipeline to playing state")

    # Wait for state change
    bus = pipeline.get_bus()
    bus.timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.STATE_CHANGED)

    try:
        with open(mcap_file, "rb") as f:
            reader = make_reader(f)
            src = pipeline.get_by_name("src")

            timestamp = None
            prev_publish_time = None
            frame_count = 0

            for schema, channel, message in reader.iter_messages():
                if schema.name == MESSAGE_SCHEMA_NAME and channel.topic == topic:
                    decoded = decode_cdr(CompressedVideo, message.data)

                    # Use message.publish_time (in nanoseconds) if available
                    current_time = message.publish_time  # Usually in nanoseconds

                    buf = Gst.Buffer.new_wrapped(decoded.data)

                    if prev_publish_time is not None:
                        # Calculate duration since last frame
                        delta = current_time - prev_publish_time
                        buf.duration = max(1, delta)  # Avoid zero duration
                    else:
                        # First frame: assume 30 FPS as fallback
                        buf.duration = Gst.SECOND // 30

                    # Set PTS: cumulative or use absolute time
                    buf.pts = current_time
                    buf.dts = current_time

                    ret = src.emit("push-buffer", buf)
                    if ret != Gst.FlowReturn.OK:
                        print(f"Failed to push buffer: {ret}")
                        break

                    prev_publish_time = current_time
                    frame_count += 1

            # End of stream
            src.emit("end-of-stream")

            # Wait for EOS
            msg = bus.timed_pop_filtered(
                30 * Gst.SECOND,
                Gst.MessageType.EOS | Gst.MessageType.ERROR
            )

            if msg and msg.type == Gst.MessageType.EOS:
                print(f"Successfully finished writing {output_filename}")
            elif msg and msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                print(f"Error: {err} | Debug: {debug}")

    except Exception as e:
        print(f"Error during extraction: {e}")
    finally:
        pipeline.set_state(Gst.State.NULL)


def main():
    parser = argparse.ArgumentParser(description="List topics containing foxglove.CompressedVideo messages in an MCAP file or extract a specific video topic")
    parser.add_argument("mcap_file", help="Path to MCAP file")
    parser.add_argument("topic", nargs="?", help="Topic name to extract video from, use 'all' to extract all topics")
    args = parser.parse_args()

    if not args.topic:
        list_video_messages(args.mcap_file)
        return

    if args.topic == "all":
        video_topics = get_video_topics(args.mcap_file)
        for topic in video_topics:
            extract_video(args.mcap_file, topic)
        return

    extract_video(args.mcap_file, args.topic)


if __name__ == "__main__":
    main()