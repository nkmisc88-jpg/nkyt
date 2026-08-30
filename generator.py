import yt_dlp
from github import Github
import os

TOKEN = os.environ.get("GH_TOKEN")
# Fallback to manual repo name if the GitHub environment variable fails
REPO_NAME = os.environ.get("GITHUB_REPOSITORY", "nkmisc88-jpg/nkyt")
INPUT_FILE = "nkyt.txt"       
OUTPUT_FILE = "playlist.m3u"  
BRANCH = "main"

# --- THE BYPASS FIX ---
# This forces yt-dlp to pretend it is the Android/TV app. 
# YouTube does not serve bot-checks to these mobile app clients.
YDL_OPTIONS = {
    'quiet': True, 
    'no_warnings': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'tv']
        }
    }
}

def get_channel_videos(channel_url):
    opts = YDL_OPTIONS.copy()
    opts['extract_flat'] = True
    opts['playlistend'] = 5
    opts['ignoreerrors'] = True

    search_url = channel_url if "/streams" in channel_url else channel_url.rstrip('/') + "/streams"
    print(f"Scanning: {search_url}")
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            res = ydl.extract_info(search_url, download=False)
            if res and 'entries' in res:
                return [{'id': e['id'], 'title': e.get('title', 'Unknown')} for e in res['entries'] if e.get('id')]
    except Exception as e:
        print(f"  > Scan failed: {e}")
        
    return []

def get_smart_link(video_id):
    opts = YDL_OPTIONS.copy()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            if not info: return None, None, None, None
            
            status, title, channel = info.get('live_status'), info.get('title'), info.get('uploader')
            if status == 'is_upcoming': 
                return "UPCOMING", info.get('webpage_url'), channel, title
                
            if status == 'is_live':
                # Filter for m3u8 formats for TV compatibility
                hls = sorted([f for f in info.get('formats', []) if 'm3u8' in str(f.get('protocol', ''))], 
                             key=lambda x: x.get('height', 0) or 0, reverse=True)
                
                final_url = hls[0]['url'] if hls else info.get('url')
                return "LIVE", final_url, channel, title
                
    except Exception as e:
        if "live event will begin" in str(e).lower():
            return "UPCOMING", f"https://www.youtube.com/watch?v={video_id}", "Scheduled", "Upcoming Match"
        print(f"  > Link fetch failed: {e}")
        
    return None, None, None, None

def main():
    print("--- STARTING CLOUD GENERATOR (MOBILE BYPASS) ---")
    if not TOKEN: 
        print("ERROR: GH_TOKEN missing!")
        return
        
    try:
        repo = Github(TOKEN).get_repo(REPO_NAME)
        raw_urls = [line.strip() for line in repo.get_contents(INPUT_FILE, ref=BRANCH).decoded_content.decode("utf-8").split('\n') if line.strip()]
    except Exception as e: 
        print(f"GitHub Error: {e}")
        return
    
    m3u = "#EXTM3U\n"
    ua = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
    added = 0

    for url in raw_urls:
        for vid in get_channel_videos(url if url.startswith("http") else "https://" + url):
            status, link, name, title = get_smart_link(vid['id'])
            if link:
                c_name = str(name).replace(",", " ")
                c_title = str(title or vid['title']).replace(",", " ")
                
                if status == "LIVE": 
                    print(f"  [+] LIVE: {c_title}")
                    m3u += f'#EXTINF:-1 tvg-id="{c_name}" group-title="{c_name}" user-agent="{ua}", {c_name} | {c_title}\n{link}\n'
                elif status == "UPCOMING": 
                    print(f"  [O] UPCOMING: {c_title}")
                    m3u += f'#EXTINF:-1 tvg-id="{c_name}" group-title="{c_name}", [UPCOMING] {c_name} | {c_title}\n{link}\n'
                
                added += 1

    if added > 0:
        print(f"Found {added} streams. Uploading to GitHub...")
        try:
            try:
                c = repo.get_contents(OUTPUT_FILE, ref=BRANCH)
                repo.update_file(c.path, "Auto-Update Playlist", m3u, c.sha, branch=BRANCH)
            except: 
                repo.create_file(OUTPUT_FILE, "Initial Creation", m3u, branch=BRANCH)
            print("SUCCESS: Playlist updated.")
        except Exception as e: 
            print(f"Upload Failed: {e}")
    else:
        print("No streams found.")

if __name__ == "__main__": 
    main()
