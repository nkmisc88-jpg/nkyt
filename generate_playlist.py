#!/usr/bin/env python3
import os
import yt_dlp

CHANNELS_FILE = "channels.txt"
OUTPUT_FILE = "playlist.m3u"
COOKIES_FILE = "cookies.txt"

# Prioritize mobile/TV clients first to bypass YouTube bot detection (PO-Token requirements)
CLIENT_ORDER = ["android", "tv", "ios", "mweb", "web"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def normalize_url(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    if not line.startswith("http"):
        line = "https://" + line
    if not line.rstrip("/").endswith("/live"):
        line = line.rstrip("/") + "/live"
    return line

def get_live_stream(url: str):
    has_cookies = os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0

    for client in CLIENT_ORDER:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "best[protocol^=m3u8]/best",
            "extractor_args": {"youtube": {"player_client": [client]}},
        }

        # Apply cookies if available
        if has_cookies:
            ydl_opts["cookiefile"] = COOKIES_FILE

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    continue

                if info.get("is_live"):
                    # Find highest resolution HLS/m3u8 stream available
                    formats = info.get("formats", [])
                    hls_formats = [f for f in formats if "m3u8" in str(f.get("protocol", ""))]
                    
                    if hls_formats:
                        hls_formats.sort(key=lambda x: x.get("height", 0) or 0, reverse=True)
                        stream_url = hls_formats[0]["url"]
                    else:
                        stream_url = info.get("url")

                    title = info.get("title", "Live Stream")
                    uploader = info.get("uploader", "Live Channel")
                    return title, uploader, stream_url

                if not info.get("is_live"):
                    return None

        except Exception as e:
            err = str(e)
            if "not currently live" in err.lower():
                return None
            print(f"  -> client={client} failed ({err.strip()})")
            continue

    return None

def main():
    if not os.path.exists(CHANNELS_FILE):
        print(f"Error: {CHANNELS_FILE} not found!")
        return

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
            title, uploader, stream_url = result
            print(f"  -> LIVE: {title}")
            clean_uploader = str(uploader).replace(",", " ")
            clean_title = str(title).replace(",", " ")
            entries.append((clean_uploader, clean_title, stream_url))
        else:
            print("  -> Not live")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for uploader, title, stream_url in entries:
            f.write(f'#EXTINF:-1 tvg-id="{uploader}" group-title="{uploader}" user-agent="{USER_AGENT}", {uploader} | {title}\n')
            f.write(f"{stream_url}\n")

    print(f"\nDone. {len(entries)} live stream(s) written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
