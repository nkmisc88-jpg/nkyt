#!/usr/bin/env python3
"""
Generates an M3U playlist of currently-live YouTube channel streams.

Reads channel URLs from channels.txt (one per line), checks each
channel's /live page with yt-dlp, and writes any live streams found
to playlist.m3u.

Note: YouTube's direct stream URLs expire after a few hours, so this
script is meant to be re-run periodically (see the included GitHub
Actions workflow).
"""

import os
import yt_dlp

CHANNELS_FILE = "channels.txt"
OUTPUT_FILE = "playlist.m3u"
COOKIES_FILE = "cookies.txt"  # optional; only used if the file exists


def normalize_url(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    if not line.startswith("http"):
        line = "https://" + line
    # Append /live if not already present, so yt-dlp checks the live tab
    if not line.rstrip("/").endswith("/live"):
        line = line.rstrip("/") + "/live"
    return line


# Player clients to try, in order. With cookies present, "web" and "mweb"
# correctly recognize a logged-in browser session. The device clients
# (android/tv/ios) expect their own session type and return empty format
# lists when given browser cookies, so they're only useful as a fallback
# when no cookies file exists.
PLAYER_CLIENTS_WITH_COOKIES = ["web", "mweb"]
PLAYER_CLIENTS_NO_COOKIES = ["android", "tv", "ios", "web"]


def get_live_stream(url: str):
    """Returns (title, direct_stream_url) if the channel is live, else None."""
    has_cookies = os.path.exists(COOKIES_FILE)
    clients = PLAYER_CLIENTS_WITH_COOKIES if has_cookies else PLAYER_CLIENTS_NO_COOKIES

    for client in clients:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "best[protocol^=m3u8]/best",
            "extractor_args": {
                "youtube": {
                    "player_client": [client],
                    "formats": ["missing_pot"],
                }
            },
        }
        if has_cookies:
            ydl_opts["cookiefile"] = COOKIES_FILE
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info.get("is_live") and info.get("url"):
                    return info.get("title", "Live Stream"), info.get("url")
                elif not info.get("is_live"):
                    # Genuinely not live - no point trying other clients
                    return None
        except Exception as e:
            print(f"  -> client={client} failed ({e})")
            continue
    return None


def main():
    with open(CHANNELS_FILE, "r") as f:
        raw_lines = f.readlines()

    entries = []
    for raw in raw_lines:
        url = normalize_url(raw)
        if not url:
            continue
        print(f"Checking {url} ...")
        result = get_live_stream(url)
        if result:
            title, stream_url = result
            print(f"  -> LIVE: {title}")
            entries.append((title, stream_url))
        else:
            print("  -> Not live")

    with open(OUTPUT_FILE, "w") as f:
        f.write("#EXTM3U\n")
        for title, stream_url in entries:
            f.write(f"#EXTINF:-1,{title}\n")
            f.write(f"{stream_url}\n")

    print(f"\nDone. {len(entries)} live stream(s) written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
