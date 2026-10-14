import os
import subprocess

INPUT_FILE = "channels.txt"
OUTPUT_FILE = "playlist.m3u"

def get_cookie_file():
    # Priority 1: GitHub Secret written to cookies.txt
    if os.path.exists("cookies.txt") and os.path.getsize("cookies.txt") > 0:
        return "cookies.txt"
    # Priority 2: If nkyt.txt is a Netscape cookie file
    if os.path.exists("nkyt.txt"):
        with open("nkyt.txt", "r", encoding="utf-8", errors="ignore") as f:
            first_chunk = f.read(500)
            if "Netscape" in first_chunk or ".youtube.com" in first_chunk:
                return "nkyt.txt"
    return None

def extract_hls(url, cookie_file=None):
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
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
        if res.returncode == 0 and res.stdout.strip():
            # Return the first valid m3u8 URL
            for line in res.stdout.strip().splitlines():
                if line.startswith("http"):
                    return line.strip()
        else:
            print(f"  [!] yt-dlp error: {res.stderr.strip().splitlines()[-1] if res.stderr.strip() else 'Unknown error'}")
    except Exception as e:
        print(f"  [!] Exception: {e}")
    return None

def parse_channels(filepath):
    channels = []
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found!")
        return channels

    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    i = 0
    while i < len(lines):
        line = lines[i]
        # Format A: Already an #EXTINF tag followed by a URL on the next line
        if line.startswith("#EXTINF"):
            extinf = line
            url = lines[i + 1] if (i + 1) < len(lines) else ""
            if url.startswith("http"):
                channels.append({"extinf": extinf, "url": url, "name": extinf.split(",")[-1]})
                i += 2
                continue
        # Format B: Pipe or Comma separated (e.g., Name | Group | URL or Name, URL)
        elif "|" in line or ("," in line and "http" in line):
            sep = "|" if "|" in line else ","
            parts = [p.strip() for p in line.split(sep)]
            if len(parts) >= 3 and parts[2].startswith("http"):
                name, group, url = parts[0], parts[1], parts[2]
                logo = parts[3] if len(parts) >= 4 else ""
                extinf = f'#EXTINF:-1 tvg-logo="{logo}" group-title="{group}",{name}'
                channels.append({"extinf": extinf, "url": url, "name": name})
            elif len(parts) == 2 and parts[1].startswith("http"):
                name, url = parts[0], parts[1]
                extinf = f'#EXTINF:-1 group-title="YouTube Live",{name}'
                channels.append({"extinf": extinf, "url": url, "name": name})
        # Format C: Just a raw URL
        elif line.startswith("http"):
            name = line.split("@")[-1].split("/")[0] if "@" in line else "YouTube Live"
            extinf = f'#EXTINF:-1 group-title="YouTube Live",{name}'
            channels.append({"extinf": extinf, "url": line, "name": name})
        i += 1

    return channels

def main():
    cookie_file = get_cookie_file()
    if cookie_file:
        print(f"Using cookies from: {cookie_file}")
    else:
        print("Running without cookies (using POT provider only)")

    channels = parse_channels(INPUT_FILE)
    print(f"Found {len(channels)} channels in {INPUT_FILE}")

    output_lines = ["#EXTM3U"]
    success_count = 0

    for ch in channels:
        print(f"Fetching: {ch['name']} ({ch['url']})")
        live_url = extract_hls(ch["url"], cookie_file)
        if live_url:
            output_lines.append(ch["extinf"])
            output_lines.append(live_url)
            success_count += 1
            print("  [+] Success!")
        else:
            print("  [-] Failed / Offline")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines) + "\n")

    print(f"\nDone! {success_count}/{len(channels)} channels written to {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()
