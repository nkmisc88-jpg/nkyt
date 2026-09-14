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


def pick_stream_url(formats):
    """Prefer an HLS (m3u8) format since that's playable in most IPTV apps."""
    m3u8_formats = [f for f in formats if (f.get("protocol") or "").startswith("m3u8")]
    candidates = m3u8_formats or formats
    if not candidates:
        return None
    # Formats are usually ordered worst->best; take the last (highest quality)
    return candidates[-1].get("url")


def resolve_live_video(channel_live_url: str, has_cookies: bool):
    """Step 1: resolve a channel's /live URL to (video_id, title, formats).

    This uses the cookie-authenticated "web" client, which reliably
    resolves the channel-tab redirect even though it may not always
    return usable formats (that's step 2's job). Returns None if the
    channel is confirmed not live or only has an upcoming/scheduled
    stream.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignore_no_formats_error": True,
        "geo_bypass": True,
        "geo_bypass_country": "IN",
        "extractor_args": {"youtube": {"player_client": ["web"]}},
    }
    if has_cookies:
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_live_url, download=False)
    except Exception as e:
        print(f"  -> resolve: {e}")
        return None

    status = info.get("live_status")
    print(f"  -> resolve: live_status={status}, is_live={info.get('is_live')}, id={info.get('id')}")

    if status == "is_upcoming":
        print("  -> Scheduled/waiting-room stream - not actually broadcasting yet.")
        return None
    if status not in ("is_live", "was_live", "post_live") and not info.get("is_live"):
        return None

    return info.get("id"), info.get("title", "Live Stream"), info.get("formats") or []


def get_formats_for_video(video_id: str, has_cookies: bool):
    """Step 2: given a known-live video ID, try to get real playable
    formats. android_vr is tried first since it doesn't require a PO
    token (per yt-dlp's PO Token guide) and works directly on a video
    URL, unlike on a channel's /live tab."""
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    attempts = [("android_vr", False)]
    if has_cookies:
        attempts += [("web", True), ("mweb", True)]
    else:
        attempts += [("android", False), ("tv", False), ("ios", False)]

    for client, use_cookies in attempts:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignore_no_formats_error": True,
            "geo_bypass": True,
            "geo_bypass_country": "IN",
            "extractor_args": {"youtube": {"player_client": [client]}},
        }
        if use_cookies:
            ydl_opts["cookiefile"] = COOKIES_FILE

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
        except Exception as e:
            print(f"  -> client={client} (video-level): extraction raised an error: {e}")
            continue

        formats = info.get("formats") or []
        print(f"  -> client={client} (video-level): formats_found={len(formats)}")
        stream_url = pick_stream_url(formats)
        if stream_url:
            return info.get("title"), stream_url

    return None


def get_live_stream(url: str):
    """Returns (title, direct_stream_url) if the channel is genuinely
    broadcasting live, else None."""
    has_cookies = os.path.exists(COOKIES_FILE)

    resolved = resolve_live_video(url, has_cookies)
    if not resolved:
        return None
    video_id, title, formats = resolved

    # The resolve step might already have usable formats - check before
    # doing a second round of extraction.
    stream_url = pick_stream_url(formats)
    if stream_url:
        return title, stream_url

    result = get_formats_for_video(video_id, has_cookies)
    if result:
        found_title, stream_url = result
        return found_title or title, stream_url

    return None


def main():
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
    print(f"Cookies file present: {os.path.exists(COOKIES_FILE)}")
    print("Geo-bypass country: IN (testing whether streams are India-restricted)")

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
