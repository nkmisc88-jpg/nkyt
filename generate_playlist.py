import os
import re
import subprocess

INPUT_FILES = ["channels.txt", "nkyt.txt"]
OUTPUT_FILE = "playlist.m3u"

def get_cookie_file():
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 0:
        return "cookies.txt"
    if os.path.exists("nkyt.txt"):
        with open("nkyt.txt", "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(400)
            if "Netscape" in head or "TRUE\t" in head or "FALSE\t" in head:
                return "nkyt.txt"
    return None

def is_youtube_url(url):
    return "youtube.com/" in url or "youtu.be/" in url

def extract_hls(url, cookie_file=None):
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
        print(f"File not found: {filepath}")
        return channels

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        raw_lines = [line.strip() for line in f if line.strip()]

    if not raw_lines:
        print(f"{filepath} is empty!")
        return channels

    # Skip if it's strictly a Netscape cookie file (contains tab-separated cookie rows)
    if "Netscape" in raw_lines[0] or any("\tTRUE\t" in l or "\tFALSE\t" in l for l in raw_lines[:10]):
        print(f"Skipping {filepath} (detected as a Netscape cookie file)")
        return channels

    print(f"--- Debug: First 3 lines of {filepath} ---")
    for sample in raw_lines[:3]:
        print(f"  {sample[:100]}")
    print("-----------------------------------------")

    url_pattern = re.compile(r'(https?://[^\s|,"\'<>]+)')

    pending_name = "YouTube Live"
    pending_group = "YouTube"
    pending_logo = ""
    pending_extinf = None

    for line in raw_lines:
        if line.startswith("~~") or line.startswith("#EXTM3U"):
            continue

        # Case 1: #EXTINF line
        if line.startswith("#EXTINF"):
            pending_extinf = line
            pending_name = line.split(",")[-1].strip() if "," in line else "YouTube Live"
            continue

        # Search for a URL anywhere on the current line
        url_match = url_pattern.search(line)

        if url_match:
            url = url_match.group(1).strip()

            # Check if the same line also has pipe/comma metadata before the URL
            if not pending_extinf and ("|" in line or "," in line):
                sep = "|" if "|" in line else ","
                parts = [p.strip() for p in line.split(sep) if p.strip() != url]
                if len(parts) >= 1 and not parts[0].startswith("http"):
                    pending_name = parts[0]
                if len(parts) >= 2 and not parts[1].startswith("http"):
                    pending_group = parts[1]
                if len(parts) >= 3 and parts[2].startswith("http"):
                    pending_logo = parts[2]

            if pending_extinf:
                extinf = pending_extinf
            else:
                if pending_name == "YouTube Live" and "@" in url:
                    pending_name = url.split("@")[-1].split("/")[0]
                extinf = f'#EXTINF:-1 tvg-logo="{pending_logo}" group-title="{pending_group}",{pending_name}'

            channels.append({
                "name": pending_name,
                "url": url,
                "extinf": extinf
            })

            # Reset pending metadata for next channel
            pending_name = "YouTube Live"
            pending_group = "YouTube"
            pending_logo = ""
            pending_extinf = None

        else:
            # No URL on this line -> Check if it's metadata for the NEXT line (e.g., Name | Group | Logo | tvg-id)
            if not line.startswith("#") and ("|" in line or "," in line):
                sep = "|" if "|" in line else ","
                parts = [p.strip() for p in line.split(sep)]
                if len(parts) >= 1 and parts[0]:
                    pending_name = parts[0]
                if len(parts) >= 2 and parts[1]:
                    pending_group = parts[1]
                if len(parts) >= 3 and parts[2]:
                    pending_logo = parts[2]
            elif not line.startswith("#") and len(line) < 60:
                pending_name = line

    return channels

def main():
    cookie_file = get_cookie_file()
    if cookie_file:
        print(f"Using cookies from: {cookie_file}")
    else:
        print("Running with POT Token Provider only")

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
