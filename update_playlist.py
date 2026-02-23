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

# Enhanced config for 2026 YouTube detection
YDL_OPTS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'cookiefile': 'cookies.txt',
    'extractor_args': {
        'youtube': {
            'player_client': ['mweb', 'ios'], # Added iOS client for better live detection
            'skip': ['dash', 'hls'] # Focus on getting the metadata first
        }
    }
}

def get_channel_videos(channel_url):
    found_streams = []
    # We check the main URL and the /streams suffix
    urls_to_check = [channel_url.rstrip('/') , channel_url.rstrip('/') + "/streams"]
    
    opts = {**YDL_OPTS_BASE, 'extract_flat': True, 'playlistend': 10}
    
    with yt_dlp.YoutubeDL(opts) as ydl:
        for url in urls_to_check:
            try:
                result = ydl.extract_info(url, download=False)
                if 'entries' in result:
                    for entry in result['entries']:
                        if entry.get('id'):
                            found_streams.append({'id': entry['id'], 'title': entry.get('title', 'Unknown')})
            except:
                continue
    return found_streams

def get_smart_link(video_id):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_BASE) as ydl:
            info = ydl.extract_info(video_url, download=False)
            live_status = info.get('live_status')
            
            # If the video is live or upcoming
            if live_status in ['is_live', 'is_upcoming', 'live']:
                formats = info.get('formats', [])
                hls = [f for f in formats if 'm3u8' in str(f.get('protocol', ''))]
                # Sort by resolution to get the best quality
                if hls:
                    hls.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)
                    link = hls[0]['url']
                else:
                    link = info.get('url')
                    
                return ("LIVE" if live_status in ['is_live', 'live'] else "UPCOMING"), link, info.get('uploader'), info.get('title')
    except:
        pass
    return None, None, None, None

def run_update_cycle():
    if not GITHUB_TOKEN: return
    
    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(REPO_NAME)
    
    try:
        content_file = repo.get_contents(INPUT_FILE, ref=BRANCH)
        raw_urls = content_file.decoded_content.decode("utf-8").splitlines()
    except: return

    m3u_content = "#EXTM3U\n"
    total = 0
    # Clean up and deduplicate IDs to avoid double-checking
    processed_vids = set()

    for url in [u.strip() for u in raw_urls if u.strip()]:
        print(f"Checking: {url}")
        vids = get_channel_videos(url)
        for vid in vids:
            if vid['id'] in processed_vids: continue
            
            status, link, channel, title = get_smart_link(vid['id'])
            if link:
                clean_ch = str(channel).replace(",", " ")
                m3u_content += f'#EXTINF:-1 group-title="{clean_ch}", {clean_ch} | {title}\n{link}\n'
                total += 1
                processed_vids.add(vid['id'])
                print(f"  [+] Found {status}: {title}")

    if total > 0:
        try:
            try:
                cur = repo.get_contents(OUTPUT_FILE, ref=BRANCH)
                repo.update_file(cur.path, "Update Playlist", m3u_content, cur.sha, branch=BRANCH)
            except:
                repo.create_file(OUTPUT_FILE, "Create Playlist", m3u_content, branch=BRANCH)
            print(f"SUCCESS: {total} streams found.")
        except Exception as e:
            print(f"Upload failed: {e}")
    else:
        print("No live streams found. Check if cookies are still valid.")

if __name__ == "__main__":
    run_update_cycle()
