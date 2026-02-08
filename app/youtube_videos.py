"""
YouTube Data API service for listing channel videos.
"""
import logging
from googleapiclient.discovery import build
from app.youtube_auth import get_credentials

logger = logging.getLogger(__name__)

def get_youtube_client():
    """Get YouTube Data API v3 client."""
    creds = get_credentials()
    if not creds:
        return None
    return build('youtube', 'v3', credentials=creds)

def get_my_recent_videos(limit=20, raw_format=False):
    """
    Fetch recent uploads from the authenticated channel with analytics.
    
    Args:
        limit: Maximum number of videos to fetch
        raw_format: If True, return YouTube API format with items/snippet structure
    
    Returns:
        dict or list: YouTube API response format or simplified list
    """
    try:
        youtube = get_youtube_client()
        if not youtube:
            return {'items': []} if raw_format else []

        # 1. Get the upload playlist ID for the channel
        channels_response = youtube.channels().list(
            mine=True,
            part='contentDetails'
        ).execute()

        if not channels_response.get('items'):
            return {'items': []} if raw_format else []

        uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # 2. Get videos from the uploads playlist
        playlist_items_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part='snippet,contentDetails',
            maxResults=limit
        ).execute()

        video_ids = [item['contentDetails']['videoId'] for item in playlist_items_response.get('items', [])]
        
        if not video_ids:
            return {'items': []} if raw_format else []

        # 3. Get detailed video information (including view counts, likes, comments)
        videos_response = youtube.videos().list(
            id=','.join(video_ids),
            part='snippet,statistics,status,contentDetails'
        ).execute()

        if raw_format:
            # Return in YouTube API format
            return videos_response
        
        # Return simplified format for dashboard
        videos = []
        for item in videos_response.get('items', []):
            snippet = item.get('snippet', {})
            stats = item.get('statistics', {})
            content_details = item.get('contentDetails', {})
            
            videos.append({
                'id': item['id'],
                'title': snippet.get('title'),
                'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url'),
                'published_at': snippet.get('publishedAt'),
                'view_count': int(stats.get('viewCount', 0)),
                'like_count': int(stats.get('likeCount', 0)),
                'comment_count': int(stats.get('commentCount', 0)),
                'duration': content_details.get('duration', 'PT0S'),
                'url': f"https://youtube.com/watch?v={item['id']}",
                'status': item.get('status', {}).get('privacyStatus', 'public')
            })

        return videos

    except Exception as e:
        logger.error(f"Error fetching YouTube videos: {e}", exc_info=True)
        return {'items': []} if raw_format else []
