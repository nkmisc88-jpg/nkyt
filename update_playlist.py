import yt_dlp
import os
import datetime
from github import Github, Auth

# --- CONFIGURATION ---
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY") 
INPUT_FILE = "nkyt.txt"       
OUTPUT_FILE = "playlist.m3u"  
BRANCH = "main"

# Comprehensive config for 2026 YouTube protection
YDL_OPTS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'cookiefile': 'cookies.txt',
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'mweb'], # iOS client is very effective for Live
            'skip': ['dash', 'hls'] 
        }
    }
}

def get_channel_live_vids(channel_url):
    """Checks multiple potential live locations for a channel"""
    found_ids = set()
    base_url = channel_url.rstrip('/')
    # Check Home, /live (direct), and /streams tab
    targets = [base_url, f"{base_url}/live", f"{base_url}/streams"]
    
    opts = {**YDL_OPTS_BASE, 'extract_flat': True, 'playlistend': 5}
    
    with yt_dlp.YoutubeDL(opts) as ydl:
        for target in targets:
            try:
                result = ydl.extract_info(target, download=False)
                if 'entries' in result:
                    for entry in result['entries']:
                        if entry.get('id'): found_ids.add(entry['id'])
                elif result.get('id'): # Direct match for /live
                    found_ids.add(result['id'])
            except:
                continue
    return list(found_ids)

def get_live_link(video_id):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_BASE) as ydl:
            info = ydl.extract_info(video_url, download=False)
            status = info.get('live_status')
            
            # Only proceed if it is actually Live or Upcoming
            if status in ['is_live', 'live', 'is_upcoming']:
                formats = info.get('formats', [])
                hls = [f for f in formats if 'm3u8' in str(f.get('protocol', ''))]
                if hls:
                    hls.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)
                    return ("LIVE" if status != 'is_upcoming' else "UPCOMING"), hls[0]['url'], info.get('uploader'), info.get('title')
    except:
        pass
    return None, None, None, None

def run_update():
    if not GITHUB_TOKEN: return
    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(REPO_NAME)
    
    try:
        urls = repo.get_contents(INPUT_FILE, ref=BRANCH).decoded_content.decode("utf-8").splitlines()
    except: return

    m3u = "#EXTM3U\n"
    count = 0
    seen_ids = set()

    for url in [u.strip() for u in urls if u.strip()]:
        print(f"Scanning: {url}")
        video_ids = get_channel_live_vids(url)
        for v_id in video_ids:
            if v_id in seen_ids: continue
            status, link, channel, title = get_live_link(v_id)
            if link:
                clean_ch = str(channel).replace(",", " ")
                m3u += f'#EXTINF:-1 group-title="{clean_ch}", {clean_ch} | {title}\n{link}\n'
                count += 1
                seen_ids.add(v_id)
                print(f"  [+] Added {status}: {title}")

    if count > 0:
        try:
            path = OUTPUT_FILE
            try:
                f = repo.get_contents(path, ref=BRANCH)
                repo.update_file(f.path, "Update Live Playlist", m3u, f.sha, branch=BRANCH)
            except:
                repo.create_file(path, "Create Live Playlist", m3u, branch=BRANCH)
            print(f"Success: {count} streams added.")
        except Exception as e: print(f"Git Error: {e}")
    else:
        print("No live content found. Verify cookies/channels.")

if __name__ == "__main__":
    run_update()
