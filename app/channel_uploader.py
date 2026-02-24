"""
YouTube video uploader for dedicated channel bots (Valorant & CS).
Uses channel-specific credentials from channel_auth.
"""
import os
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from app.channel_auth import get_channel_credentials
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_TAGS = os.getenv("YOUTUBE_TAGS", "twitch,gaming,clips").split(",")
DEFAULT_CATEGORY = os.getenv("YOUTUBE_CATEGORY", "20")  # 20 = Gaming
DEFAULT_PRIVACY = os.getenv("YOUTUBE_PRIVACY", "public")
DEFAULT_TITLE_TEMPLATE = os.getenv("YOUTUBE_TITLE_TEMPLATE", "{clip_title} - Twitch Clips")
DEFAULT_DESCRIPTION = os.getenv("YOUTUBE_DESCRIPTION", "Automatically uploaded Twitch clip.\n\nSource: {clip_url}")


def upload_video_to_channel(channel: str, video_path: str, clip_data: dict):
    """
    Upload video to a specific YouTube channel.
    
    Args:
        channel: Channel name ('valorant' or 'cs')
        video_path: Path to video file
        clip_data: Dictionary with clip information
        
    Returns:
        tuple: (success: bool, youtube_video_id: str or None, error: str or None)
    """
    try:
        creds = get_channel_credentials(channel)
        if not creds:
            return False, None, f"Not authenticated with YouTube ({channel} channel)"
        
        youtube = build('youtube', 'v3', credentials=creds)
        
        title = DEFAULT_TITLE_TEMPLATE.format(
            clip_title=clip_data.get('title', 'Untitled Clip'),
            creator=clip_data.get('creator_name', 'Unknown'),
            broadcaster=clip_data.get('broadcaster_name', 'Unknown'),
            game=clip_data.get('game_name', 'Unknown')
        )
        
        description = DEFAULT_DESCRIPTION.format(
            clip_url=clip_data.get('url', ''),
            creator=clip_data.get('creator_name', 'Unknown'),
            broadcaster=clip_data.get('broadcaster_name', 'Unknown'),
            views=clip_data.get('view_count', 0),
            duration=clip_data.get('duration', 0)
        )
        
        body = {
            'snippet': {
                'title': title[:100],
                'description': description[:5000],
                'tags': DEFAULT_TAGS,
                'categoryId': DEFAULT_CATEGORY
            },
            'status': {
                'privacyStatus': DEFAULT_PRIVACY,
                'selfDeclaredMadeForKids': False
            }
        }
        
        media = MediaFileUpload(
            video_path,
            chunksize=1024*1024,
            resumable=True
        )
        
        logger.info(f"[{channel.upper()}] Uploading video to YouTube: {title}")
        
        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = request.execute()
        
        video_id = response['id']
        logger.info(f"[{channel.upper()}] ✅ Uploaded: https://youtube.com/watch?v={video_id}")
        
        return True, video_id, None
        
    except HttpError as e:
        error_msg = f"YouTube API error ({channel}): {e}"
        logger.error(error_msg)
        return False, None, error_msg
        
    except Exception as e:
        error_msg = f"Upload error ({channel}): {e}"
        logger.error(error_msg, exc_info=True)
        return False, None, error_msg
