import os
import subprocess

INPUT_FILES = ["channels.txt", "nkyt.txt"]
OUTPUT_FILE = "playlist.m3u"

def get_cookie_file():
    # Uses cookies.txt created by GitHub Secrets if available
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 0:
        return "cookies.txt"
    return None

def is_youtube_url(url):
    return "youtube.com/" in url or "youtu.be/" in url

def extract_hls(url, cookie_file=None):
    # If it's already a direct m3u8 or non-YouTube IPTV stream, keep it as-is
    if not is_youtube_url(url):
        return url

    cmd = [
        "yt-dlp",
        "--no-warnings",
        "-g",
        "-f", "best[protocol^=m3u8]/best",
        "--extractor-args", "youtube:player_client=web,ios;po_token=web+http://127.0.0.1:4416"
    ]
    if cookie_file:
        cmd.extend(["--cookies", cookie_file])
    cmd.append(url)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if res.returncode == 0 and res.stdout.strip():
            for line in res.stdout.strip().splitlines():
                if line.startswith("http"):
                    return line.strip()
        else:
            err = res.stderr.strip().splitlines()[-1] if res.stderr.strip() else "Unknown error"
            print(f"  [!] yt-dlp error: {err}")
    except Exception as e:
        print(f"  [!] Exception: {e}")
    return None

def parse_file(filepath):
    channels = []
    if not os.path.exists(filepath):
        return channels

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        raw_lines = [line.strip() for line in f if line.strip()]

    # Skip file if it happens to be a Netscape cookie file instead of channels
    if raw_lines and ("Netscape" in raw_lines[0] or ".youtube.com" in raw_lines[0]):
        return channels

    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]

        # 1. Standard M3U format (#EXTINF followed by URL)
        if line.startswith("#EXTINF"):
            extinf = line
            url = raw_lines[i + 1] if (i + 1) < len(raw_lines) else ""
            if url.startswith("http"):
                name = extinf.split(",")[-1].strip()
                channels.append({"extinf": extinf, "url": url, "name": name})
                i += 2
                continue

        # Ignore other comment lines
        if line.startswith("#") or line.startswith("//"):
            i += 1
            continue

        # 2. Pipe (|) or Comma (,) separated format
        if "|" in line or ("," in line and "http" in line):
            sep = "|" if "|" in line else ","
            parts = [p.strip() for p in line.split(sep)]
            # Find which part has the URL
            url_idx = next((idx for idx, p in enumerate(parts) if p.startswith("http")), None)
            if url_idx is not None:
                url = parts[url_idx]
                name = parts[0] if url_idx > 0 else "Live Channel"
                group = parts[1] if url_idx > 1 else "YouTube Live"
                logo = parts[3] if len(parts) > 3 and not parts[3].startswith("http") else ""
                extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}'
                channels.append({"extinf": extinf, "url": url, "name": name})
                i += 1
                continue

        # 3. Plain URL on a line
        if line.startswith("http"):
            name = line.split("@")[-1].split("/")[0] if "@" in line else "YouTube Channel"
            extinf = f'#EXTINF:-1 group-title="YouTube Live",{name}'
            channels.append({"extinf": extinf, "url": line, "name": name})

        i += 1

    return channels

def main():
    cookie_file = get_cookie_file()
    if cookie_file:
        print(f"Using cookies from: {cookie_file}")
    else:
        print("Running with POT Token Provider (no cookies.txt found)")

    all_channels = []
    seen_urls = set()

    for file in INPUT_FILES:
        parsed = parse_file(file)
        print(f"Loaded {len(parsed)} entries from {file}")
        for ch in parsed:
            if ch["url"] not in seen_urls:
                seen_urls.add(ch["url"])
                all_channels.append(ch)

    print(f"Total unique channels to process: {len(all_channels)}\n")

    output_lines = ["#EXTM3U"]
    success_count = 0

    for ch in all_channels:
        print(f"Fetching: {ch['name']} -> {ch['url']}")
        live_url = extract_hls(ch["url"], cookie_file)
        if live_url:
            output_lines.append(ch["extinf"])
            output_lines.append(live_url)
            success_count += 1
            print("  [+] Added to playlist!")
        else:
            print("  [-] Skipped (Stream offline or blocked)")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines) + "\n")

    print(f"\nCompleted! {success_count}/{len(all_channels)} working channels saved to {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
