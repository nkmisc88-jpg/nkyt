import subprocess
import json
from pathlib import Path


CHANNEL_FILE = "nkyt.txt"
OUTPUT_FILE = "playlist.m3u"


def get_live_video(channel_url):
    channel_url = channel_url.strip().rstrip("/")

    # Ask yt-dlp for channel information.
    # We use the channel's /live page.
    live_url = channel_url + "/live"

    command = [
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "--no-playlist",
        live_url,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=90,
    )

    # IMPORTANT:
    # Show the actual error instead of calling it "Not live".
    if result.returncode != 0:
        print("yt-dlp ERROR:")
        print(result.stderr)
        return None

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not read yt-dlp JSON output:")
        print(result.stdout)
        return None

    live_status = info.get("live_status")

    print("Live status:", live_status)
    print("Title:", info.get("title"))

    if live_status != "is_live":
        return None

    video_id = info.get("id")
    title = info.get("title", "LIVE")

    if not video_id:
        return None

    video_url = f"https://www.youtube.com/watch?v={video_id}"

    # Now extract the actual HLS URL.
    command = [
        "yt-dlp",
        "--dump-single-json",
        "--skip-download",
        "--no-warnings",
        "-f",
        "best[protocol=m3u8]/best",
        video_url,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=90,
    )

    if result.returncode != 0:
        print("Stream extraction ERROR:")
        print(result.stderr)
        return None

    try:
        stream_info = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Could not parse stream information")
        return None

    stream_url = stream_info.get("url")

    if not stream_url:
        print("No stream URL found")
        return None

    return title, stream_url


def main():

    channels = Path(CHANNEL_FILE).read_text(
        encoding="utf-8"
    ).splitlines()

    playlist = [
        "#EXTM3U",
        ""
    ]

    live_count = 0

    for channel in channels:

        channel = channel.strip()

        if not channel or channel.startswith("#"):
            continue

        print()
        print("=" * 60)
        print("Checking:", channel)

        result = get_live_video(channel)

        if result is None:
            print("Result: NOT LIVE / EXTRACTION FAILED")
            continue

        title, stream_url = result

        channel_name = (
            channel
            .replace("https://www.youtube.com/@", "")
            .replace("http://www.youtube.com/@", "")
            .replace("www.youtube.com/@", "")
            .strip("/")
        )

        print("RESULT: LIVE")
        print("Title:", title)

        playlist.append(
            f'#EXTINF:-1 tvg-name="{channel_name}",{channel_name}'
        )

        playlist.append(stream_url)
        playlist.append("")

        live_count += 1

    Path(OUTPUT_FILE).write_text(
        "\n".join(playlist),
        encoding="utf-8"
    )

    print()
    print("=" * 60)
    print("Created:", OUTPUT_FILE)
    print("Live channels found:", live_count)


if __name__ == "__main__":
    main()