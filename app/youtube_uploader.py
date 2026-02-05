"""
YouTube video uploader.
"""
import os
import logging
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from app.youtube_auth import get_credentials, REDIRECT_URI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Upload settings from environment
DEFAULT_TITLE_TEMPLATE = os.getenv("YOUTUBE_TITLE_TEMPLATE", "{clip_title} - Twitch Clips")
DEFAULT_DESCRIPTION = os.getenv("YOUTUBE_DESCRIPTION", "Automatically uploaded Twitch clip.\n\nSource: {clip_url}")
DEFAULT_TAGS = os.getenv("YOUTUBE_TAGS", "twitch,gaming,clips").split(",")
DEFAULT_CATEGORY = os.getenv("YOUTUBE_CATEGORY", "20")  # 20 = Gaming
DEFAULT_PRIVACY = os.getenv("YOUTUBE_PRIVACY", "public")  # public, unlisted, or private


def upload_video(video_path, clip_data):
    """
    Upload video to YouTube.
    
    Args:
        video_path: Path to video file
        clip_data: Dictionary with clip information (title, url, creator_name, etc.)
        
    Returns:
        tuple: (success: bool, youtube_video_id: str or None, error: str or None)
    """
    try:
        creds = get_credentials()
        if not creds:
            return False, None, "Not authenticated with YouTube"
        
        # Build YouTube API client
        youtube = build('youtube', 'v3', credentials=creds)
        
        # Prepare video metadata
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
        
        # Request body
        body = {
            'snippet': {
                'title': title[:100],  # YouTube max title length
                'description': description[:5000],  # YouTube max description length
                'tags': DEFAULT_TAGS,
                'categoryId': DEFAULT_CATEGORY
            },
            'status': {
                'privacyStatus': DEFAULT_PRIVACY,
                'selfDeclaredMadeForKids': False
            }
        }
        
        # Upload video
        media = MediaFileUpload(
            video_path,
            chunksize=1024*1024,  # 1MB chunks
            resumable=True
        )
        
        logger.info(f"Uploading video to YouTube: {title}")
        
        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = request.execute()
        
        video_id = response['id']
        logger.info(f"✅ Successfully uploaded to YouTube: https://youtube.com/watch?v={video_id}")
        
        return True, video_id, None
        
    except HttpError as e:
        error_msg = f"YouTube API error: {e}"
        logger.error(error_msg)
        return False, None, error_msg
        
    except Exception as e:
        error_msg = f"Upload error: {e}"
        logger.error(error_msg, exc_info=True)
        return False, None, error_msg
