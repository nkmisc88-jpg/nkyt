import os

def get_stream_link(channel_url):
    # Runs yt-dlp to get the direct m3u8 link for a live broadcast
    # --g: get url
    # --match-filter is_live: ensure it is live
    command = f'yt-dlp -g --match-filter is_live "{channel_url}"'
    stream_url = os.popen(command).read().strip()
    return stream_url

def generate_m3u():
    with open('nkyt.txt', 'r') as f:
        channels = f.readlines()

    with open('playlist.m3u', 'w') as m3u:
        m3u.write('#EXTM3U\n')
        
        for line in channels:
            if ',' in line:
                name, url = line.strip().split(',', 1)
                name = name.strip()
                url = url.strip()
                
                print(f"Checking {name}...")
                stream_link = get_stream_link(url)
                
                if stream_link:
                    # If live, add to playlist
                    m3u.write(f'#EXTINF:-1 group-title="YouTube Live" tvg-id="{name}", {name}\n')
                    m3u.write(f'{stream_link}\n')
                else:
                    print(f"  -> {name} is NOT live right now.")

if __name__ == "__main__":
    generate_m3u()
