import yt_dlp
from github import Github, Auth
import os

# --- CONFIGURATION ---
# We now get the token from GitHub Secrets (Safe Mode)
TOKEN = os.environ.get("GH_TOKEN")
REPO_NAME = "nkmisc88-jpg/nkyt"
INPUT_FILE = "nkyt.txt"       
OUTPUT_FILE = "playlist.m3u"  
BRANCH = "main"

def get_channel_live_videos(channel_url):
    found_streams = []
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True, 
        'playlistend': 3,
    }
    search_url = channel_url if "/streams" in channel_url else channel_url.rstrip('/') + "/streams"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_url, download=False)
            if 'entries' in result:
                for entry in result['entries']:
                    if entry.get('id'):
                        found_streams.append({'id': entry['id'], 'title': entry['title']})
    except:
        pass
    return found_streams

def get_direct_link(video_id):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {'quiet': True, 'no_warnings': True, 'format': 'best'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if info.get('is_live') is True:
                return info.get('url'), info.get('uploader'), info.get('title')
    except:
        pass
    return None, None, None

# --- MAIN ---
print("--- STARTING CLOUD GENERATOR ---")

try:
    auth = Auth.Token(TOKEN)
    g = Github(auth=auth)
    repo = g.get_repo(REPO_NAME)
    
    content_file = repo.get_contents(INPUT_FILE, ref=BRANCH)
    file_data = content_file.decoded_content.decode("utf-8")
    raw_urls = [line.strip() for line in file_data.split('\n') if line.strip()]
except Exception as e:
    print(f"Setup Error: {e}")
    exit(1)

m3u_content = "#EXTM3U\n"
total_added = 0

for raw_url in raw_urls:
    url = raw_url if raw_url.startswith("http") else "https://" + raw_url
    print(f"Checking: {url}")
    
    potential_vids = get_channel_live_videos(url)
    for vid in potential_vids:
        stream_link, channel_name, title = get_direct_link(vid['id'])
        if stream_link:
            print(f"  [+] FOUND: {title}")
            clean_name = channel_name.replace(",", " ")
            clean_title = title.replace(",", " ")
            m3u_content += f'#EXTINF:-1 tvg-id="{clean_name}" group-title="{clean_name}", {clean_name} | {clean_title}\n{stream_link}\n'
            total_added += 1

if total_added > 0:
    print(f"Updating GitHub with {total_added} streams...")
    try:
        contents = repo.get_contents(OUTPUT_FILE, ref=BRANCH)
        repo.update_file(contents.path, "Auto-Update", m3u_content, contents.sha, branch=BRANCH)
    except:
        repo.create_file(OUTPUT_FILE, "Auto-Update", m3u_content, branch=BRANCH)
else:
    print("No live streams found.")
