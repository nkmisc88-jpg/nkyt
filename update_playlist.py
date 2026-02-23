import yt_dlp
import os
import datetime
from github import Github, Auth

# --- CONFIGURATION FROM ENVIRONMENT ---
# Set these in GitHub Repository Secrets
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY") # Automatically provided by GitHub
INPUT_FILE = "nkyt.txt"       
OUTPUT_FILE = "playlist.m3u"  
BRANCH = "main"

def get_channel_videos(channel_url):
    found_streams = []
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'extract_flat': True, 
        'playlistend': 5, 'ignoreerrors': True, 
    }
    search_url = channel_url if "/streams" in channel_url else channel_url.rstrip('/') + "/streams"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_url, download=False)
            if 'entries' in result:
                for entry in result['entries']:
                    if entry.get('id'):
                        found_streams.append({'id': entry['id'], 'title': entry.get('title', 'Unknown')})
    except:
        pass
    return found_streams

def get_smart_link(video_id):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {'quiet': True, 'no_warnings': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            live_status = info.get('live_status')
            title = info.get('title')
            channel = info.get('uploader')

            if live_status == 'is_upcoming':
                return "UPCOMING", video_url, channel, title

            if live_status == 'is_live':
                formats = info.get('formats', [])
                hls_formats = [f for f in formats if 'm3u8' in str(f.get('protocol', ''))]
                if hls_formats:
                    hls_formats.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)
                    best_format = hls_formats[0]
                    return "LIVE", best_format['url'], channel, title
                else:
                    return "LIVE", info.get('url'), channel, title
    except Exception as e:
        if "live event will begin" in str(e):
             return "UPCOMING", video_url, "Scheduled", "Upcoming Match"
    return None, None, None, None

def run_update_cycle():
    print(f"Update started at: {datetime.datetime.now()}")
    
    auth = Auth.Token(GITHUB_TOKEN)
    g = Github(auth=auth)
    repo = g.get_repo(REPO_NAME)
    
    # Read input file from repo
    content_file = repo.get_contents(INPUT_FILE, ref=BRANCH)
    file_data = content_file.decoded_content.decode("utf-8")
    raw_urls = [line.strip() for line in file_data.split('\n') if line.strip()]

    m3u_content = "#EXTM3U\n"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    total_added = 0

    for raw_url in raw_urls:
        url = raw_url if raw_url.startswith("http") else "https://" + raw_url
        potential_vids = get_channel_videos(url)
        for vid in potential_vids:
            status, link, channel_name, title = get_smart_link(vid['id'])
            if link:
                clean_name = str(channel_name).replace(",", " ")
                clean_title = str(title).replace(",", " ")
                if status == "LIVE":
                    m3u_content += f'#EXTINF:-1 tvg-id="{clean_name}" group-title="{clean_name}" user-agent="{user_agent}", {clean_name} | {clean_title}\n{link}\n'
                elif status == "UPCOMING":
                    m3u_content += f'#EXTINF:-1 tvg-id="{clean_name}" group-title="{clean_name}", [UPCOMING] {clean_name} | {clean_title}\n{link}\n'
                total_added += 1

    if total_added > 0:
        try:
            try:
                contents = repo.get_contents(OUTPUT_FILE, ref=BRANCH)
                repo.update_file(contents.path, "Auto-Update Playlist", m3u_content, contents.sha, branch=BRANCH)
            except:
                repo.create_file(OUTPUT_FILE, "Auto-Update Playlist", m3u_content, branch=BRANCH)
            print(f"Successfully updated {OUTPUT_FILE}")
        except Exception as e:
            print(f"Error uploading to GitHub: {e}")

if __name__ == "__main__":
    run_update_cycle()
