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
    if not line.rstrip("/").endswith("/live"):
        line = line.rstrip("/") + "/live"
    return line


# With cookies present, "web" and "mweb" correctly recognize a logged-in
# browser session. The device clients (android/tv/ios) expect their own
# session type and misbehave when given browser cookies, so they're only
# used as a fallback when no cookies file exists.
PLAYER_CLIENTS_WITH_COOKIES = ["web", "mweb"]
PLAYER_CLIENTS_NO_COOKIES = ["android", "tv", "ios", "web"]


def pick_stream_url(formats):
    """Prefer an HLS (m3u8) format since that's playable in most IPTV apps."""
    m3u8_formats = [f for f in formats if (f.get("protocol") or "").startswith("m3u8")]
    candidates = m3u8_formats or formats
    if not candidates:
        return None
    # Formats are usually ordered worst->best; take the last (highest quality)
    return candidates[-1].get("url")


def get_live_stream(url: str):
    """Returns (title, direct_stream_url) if the channel is genuinely
    broadcasting live, else None. Prints diagnostics along the way."""
    has_cookies = os.path.exists(COOKIES_FILE)
    clients = PLAYER_CLIENTS_WITH_COOKIES if has_cookies else PLAYER_CLIENTS_NO_COOKIES

    for client in clients:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            # Deliberately NOT setting "format" here - forcing a format
            # selector makes yt-dlp raise an exception (instead of just
            # returning info) when no formats match, which hides the
            # live_status/formats diagnostics we need below.
            "extractor_args": {"youtube": {"player_client": [client]}},
        }
        if has_cookies:
            ydl_opts["cookiefile"] = COOKIES_FILE

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"  -> client={client}: extraction raised an error: {e}")
            continue

        status = info.get("live_status")
        formats = info.get("formats") or []
        print(
            f"  -> client={client}: live_status={status}, "
            f"is_live={info.get('is_live')}, formats_found={len(formats)}"
        )

        if status == "is_upcoming":
            print("  -> Scheduled/waiting-room stream - not actually broadcasting yet.")
            return None

        if status not in ("is_live", "was_live", "post_live") and not info.get("is_live"):
            return None

        if formats:
            stream_url = pick_stream_url(formats)
            if stream_url:
                return info.get("title", "Live Stream"), stream_url
            print("  -> Formats existed but none had a usable URL, trying next client")
        else:
            print("  -> live_status says live/broadcasting but 0 formats returned - "
                  "extraction is being blocked, not a scheduling issue")
        # keep trying remaining clients

    return None


def main():
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
    print(f"Cookies file present: {os.path.exists(COOKIES_FILE)}")

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