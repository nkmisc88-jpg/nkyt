import os
import subprocess

# Read the URLs from the text file
try:
    with open("nkyt.txt", "r") as file:
        lines = file.readlines()
except FileNotFoundError:
    print("Error: nkyt.txt file not found. Please create it in the repository.")
    lines = []

# Open the M3U file to start writing
with open("playlist.m3u", "w") as f:
    f.write("#EXTM3U\n")
    
    for line in lines:
        url = line.strip()
        
        # Skip empty lines
        if not url:
            continue
            
        # Ensure the URL starts with https://
        if url.startswith("www."):
            url = "https://" + url
            
        # Extract the channel name from the URL (e.g., getting "ACBofficial" from the link)
        if "@" in url:
            channel_name = url.split("@")[-1].split("/")[0]
        else:
            channel_name = "Live Channel"
            
        print(f"Fetching stream for: {channel_name}...")
        
        try:
            # Run yt-dlp to extract the direct m3u8 link
            result = subprocess.run(
                ['yt-dlp', '-f', 'best', '-g', url],
                capture_output=True, text=True, check=True
            )
            stream_url = result.stdout.strip()
            
            # If a link was found, write it to the playlist
            if stream_url:
                f.write(f'#EXTINF:-1 tvg-id="" tvg-logo="",{channel_name}\n')
                f.write(f'{stream_url}\n')
        except Exception as e:
            print(f"Could not get link for {url}. The stream might be offline.")

print("Playlist generated successfully!")
