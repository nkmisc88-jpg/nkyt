import yt_dlp
from github import Github
import os
import requests
import random

TOKEN = os.environ.get("GH_TOKEN")
REPO_NAME = os.environ.get("GITHUB_REPOSITORY")
INPUT_FILE = "nkyt.txt"       
OUTPUT_FILE = "playlist.m3u"  
BRANCH = "main"

def get_fresh_proxies():
    try:
        url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all"
        response = requests.get(url, timeout=10)
        return [p for p in response.text.strip().split('\r\n') if p]
    except:
        return []

PROXIES = get_fresh_proxies()

def get_working_ydl(base_opts):
    if not PROXIES: return yt_dlp.YoutubeDL(base_opts)
    for _ in range(5):
        opts = base_opts.copy()
        opts['proxy'] = f"http://{random.choice(PROXIES)}"
        return yt_dlp.YoutubeDL(opts)
    return yt_dlp.YoutubeDL(base_opts)

def get_channel_videos(channel_url):
    opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'playlistend': 5, 'ignoreerrors': True}
    search_url = channel_url if "/streams" in channel_url else channel_url.rstrip('/') + "/streams"
    try:
        with get_working_ydl(opts) as ydl:
            res = ydl.extract_info(search_url, download=False)
            if res and 'entries' in res:
                return [{'id': e['id'], 'title': e.get('title', 'Unknown')} for e in res['entries'] if e.get('id')]
    except: pass
    return []

def get_smart_link(video_id):
    opts = {'quiet': True, 'no_warnings': True}
    try:
        with get_working_ydl(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if not info: return None, None, None, None
            
            status, title, channel = info.get('live_status'), info.get('title'), info.get('uploader')
            if status == 'is_upcoming': return "UPCOMING", info['webpage_url'], channel, title
            if status == 'is_live':
                hls = sorted([f for f in info.get('formats', []) if 'm3u8' in str(f.get('protocol', ''))], key=lambda x: x.get('height', 0) or 0, reverse=True)
                return "LIVE", hls[0]['url'] if hls else info.get('url'), channel, title
    except: pass
    return None, None, None, None

def main():
    if not TOKEN: return print("ERROR: GH_TOKEN missing!")
    try:
        repo = Github(TOKEN).get_repo(REPO_NAME)
        raw_urls = [line.strip() for line in repo.get_contents(INPUT_FILE, ref=BRANCH).decoded_content.decode("utf-8").split('\n') if line.strip()]
    except: return
    
    m3u = "#EXTM3U\n"
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    added = 0

    for url in raw_urls:
        for vid in get_channel_videos(url if url.startswith("http") else "https://" + url):
            status, link, name, title = get_smart_link(vid['id'])
            if link:
                c_name, c_title = str(name).replace(",", " "), str(title or vid['title']).replace(",", " ")
                if status == "LIVE": m3u += f'#EXTINF:-1 tvg-id="{c_name}" group-title="{c_name}" user-agent="{ua}", {c_name} | {c_title}\n{link}\n'
                elif status == "UPCOMING": m3u += f'#EXTINF:-1 tvg-id="{c_name}" group-title="{c_name}", [UPCOMING] {c_name} | {c_title}\n{link}\n'
                added += 1

    if added > 0:
        try:
            try:
                c = repo.get_contents(OUTPUT_FILE, ref=BRANCH)
                repo.update_file(c.path, "Update", m3u, c.sha, branch=BRANCH)
            except: repo.create_file(OUTPUT_FILE, "Create", m3u, branch=BRANCH)
        except: pass

if __name__ == "__main__": main()
