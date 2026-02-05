import yt_dlp
import os

def download_twitch_clip(clip_url: str, output_filename: str = None) -> bool:
    """
    Downloads a Twitch clip using yt-dlp (works on public clips in 2026).
    Handles both old and new URL formats automatically.
    """
    if output_filename is None:
        # Extract slug for default name
        slug = clip_url.rstrip('/').split('/')[-1].split('?')[0]
        output_filename = f"{slug}.mp4"

    ydl_opts = {
        'outtmpl': output_filename,          # output path/name
        'quiet': True,                       # less spam
        'no_warnings': True,
        'format': 'best[ext=mp4]',           # best MP4 quality available
        'continuedl': True,                  # resume if interrupted
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading clip from: {clip_url}")
            ydl.download([clip_url])
        
        if os.path.exists(output_filename):
            print(f"Success! Saved as: {output_filename}")
            return True
        else:
            print("Download completed but file not found?")
            return False

    except yt_dlp.utils.DownloadError as e:
        print(f"Download failed: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
