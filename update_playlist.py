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

# YouTube configuration for 2026 bot bypass
YDL_OPTS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'cookiefile': 'cookies.txt',  # Path to the file created by the Workflow
    'extractor_args': {
        'youtube': {
            'player_client': ['mweb'], # Mobile web is currently more stable
            'player_skip': ['webpage', 'configs']
        }
    }
}

def get_channel_videos(channel_url):
    found_streams = []
    opts = {**YDL_OPTS_BASE, 'extract_flat': True, 'playlistend': 5}
    # Ensure URL is formatted for streams
    search_url = channel_url if "/streams" in channel_url else channel_url.rstrip('/') + "/streams"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(search_url, download=False)
            if 'entries' in result:
                for entry in result['entries']:
                    if entry.get('id'):
                        found_streams.append({'id': entry['id'], 'title': entry.get('title', 'Unknown')})
    except Exception as e:
        print(f"Error accessing {channel_url}: {e}")
    return found_streams

def get_smart_link(video_id):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_BASE) as ydl:
            info = ydl.extract_info(video_url, download=False)
            live_status = info.get('live_status')
            
            if live_status in ['is_live', 'is_upcoming']:
                formats = info.get('formats', [])
                # Prioritize HLS (m3u8) for IPTV players
                hls = [f for f in formats if 'm3u8' in str(f.get('protocol', ''))]
                link = hls[0]['url'] if hls else info.get('url')
                return ("LIVE" if live_status == 'is_live' else "UPCOMING"), link, info.get('uploader'), info.get('title')
    except:
        pass
    return None, None, None, None

def run_update_cycle():
    if not GITHUB_TOKEN or not REPO_NAME:
        print("Missing Environment Variables")
        return
    
    g = Github(auth=Auth.Token(GITHUB_TOKEN))
    repo = g.get_repo(REPO_NAME)
    
    try:
        content_file = repo.get_contents(INPUT_FILE, ref=BRANCH)
        raw_urls = content_file.decoded_content.decode("utf-8").splitlines()
    except Exception as e:
        print(f"Error reading input file: {e}")
        return

    m3u_content = "#EXTM3U\n"
    user_agent = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    total = 0

    for url in [u.strip() for u in raw_urls if u.strip()]:
        print(f"Checking: {url}")
        for vid in get_channel_videos(url):
            status, link, channel, title = get_smart_link(vid['id'])
            if link:
                prefix = "[UPCOMING] " if status == "UPCOMING" else ""
                m3u_content += f'#EXTINF:-1 tvg-id="{channel}" group-title="{channel}" user-agent="{user_agent}", {prefix}{channel} | {title}\n{link}\n'
                total += 1
                print(f"  [+] Added {status}: {title}")

    if total > 0:
        try:
            try:
                cur = repo.get_contents(OUTPUT_FILE, ref=BRANCH)
                repo.update_file(cur.path, "Update Playlist [Bot-Bypass]", m3u_content, cur.sha, branch=BRANCH)
            except:
                repo.create_file(OUTPUT_FILE, "Create Playlist [Bot-Bypass]", m3u_content, branch=BRANCH)
            print(f"SUCCESS: {total} streams written to {OUTPUT_FILE}")
        except Exception as e:
            print(f"GitHub Update Failed: {e}")
    else:
        print("No live or upcoming streams found.")

if __name__ == "__main__":
    run_update_cycle()
