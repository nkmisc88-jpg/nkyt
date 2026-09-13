import subprocess
import re
from pathlib import Path

CHANNEL_FILE = "nkyt.txt"
OUTPUT_FILE = "playlist.m3u"


def clean_name(name):
    name = re.sub(r"^https?://(www\.)?youtube\.com/@", "", name)
    name = re.sub(r"^https?://(www\.)?youtube\.com/", "", name)
    return name.strip("/").strip()


def get_live_stream(channel_url):
    live_url = channel_url.rstrip("/") + "/live"

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--quiet",
        "--no-playlist",
        "--get-title",
        "--get-url",
        "-f",
        "best[protocol^=m3u8]/best",
        live_url,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return None

        lines = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        ]

        if len(lines) < 2:
            return None

        title = lines[0]
        stream_url = lines[-1]

        # Make sure yt-dlp actually returned a stream URL
        if not stream_url.startswith(("http://", "https://")):
            return None

        return title, stream_url

    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    channels = Path(CHANNEL_FILE).read_text(
        encoding="utf-8"
    ).splitlines()

    playlist = [
        "#EXTM3U",
        "# Generated automatically using yt-dlp",
        ""
    ]

    live_count = 0

    for channel in channels:
        channel = channel.strip()

        if not channel or channel.startswith("#"):
            continue

        print(f"Checking: {channel}")

        result = get_live_stream(channel)

        if not result:
            print("  Not live")
            continue

        title, stream_url = result
        channel_name = clean_name(channel)

        print(f"  LIVE: {title}")

        playlist.append(
            f'#EXTINF:-1 tvg-name="{channel_name}",{channel_name} - {title}'
        )
        playlist.append(stream_url)
        playlist.append("")

        live_count += 1

    Path(OUTPUT_FILE).write_text(
        "\n".join(playlist),
        encoding="utf-8"
    )

    print(f"\nCreated {OUTPUT_FILE}")
    print(f"Live channels found: {live_count}")


if __name__ == "__main__":
    main()