"""
YouTube Analytics API integration.
"""
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.youtube_auth import get_credentials

logger = logging.getLogger(__name__)


def get_analytics_client():
    """Get YouTube Analytics API client."""
    credentials = get_credentials()
    if not credentials:
        return None
    
    return build('youtubeAnalytics', 'v2', credentials=credentials)


def get_channel_analytics(days=30):
    """
    Get channel analytics for the last N days.
    
    Args:
        days: Number of days to fetch (default 30)
    
    Returns:
        dict: Analytics data or None if error
    """
    try:
        analytics = get_analytics_client()
        if not analytics:
            logger.warning("YouTube Analytics not authenticated")
            return None
        
        # Get date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Fetch analytics data
        results = analytics.reports().query(
            ids='channel==MINE',
            startDate=start_date.isoformat(),
            endDate=end_date.isoformat(),
            metrics='views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost',
            dimensions='day',
            sort='day'
        ).execute()
        
        # Parse results
        columns = results.get('columnHeaders', [])
        rows = results.get('rows', [])
        
        if not rows:
            logger.info("No analytics data available")
            return {
                'labels': [],
                'views': [],
                'watchTime': [],
                'avgViewDuration': [],
                'subscribersGained': [],
                'subscribersLost': []
            }
        
        # Extract data
        labels = []
        views = []
        watch_time = []
        avg_view_duration = []
        subscribers_gained = []
        subscribers_lost = []
        
        for row in rows:
            labels.append(row[0])  # day
            views.append(row[1])  # views
            watch_time.append(row[2])  # estimatedMinutesWatched
            avg_view_duration.append(row[3])  # averageViewDuration
            subscribers_gained.append(row[4])  # subscribersGained
            subscribers_lost.append(row[5])  # subscribersLost
        
        return {
            'labels': labels,
            'views': views,
            'watchTime': watch_time,
            'avgViewDuration': avg_view_duration,
            'subscribersGained': subscribers_gained,
            'subscribersLost': subscribers_lost
        }
        
    except HttpError as e:
        logger.error(f"YouTube Analytics API error: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}", exc_info=True)
        return None


def get_channel_summary():
    """
    Get summary statistics for the channel (last 28 days).
    
    Returns:
        dict: Summary stats or None if error
    """
    try:
        analytics = get_analytics_client()
        if not analytics:
            return None
        
        # Get last 28 days
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=28)
        
        results = analytics.reports().query(
            ids='channel==MINE',
            startDate=start_date.isoformat(),
            endDate=end_date.isoformat(),
            metrics='views,estimatedMinutesWatched,averageViewDuration,subscribersGained'
        ).execute()
        
        if not results.get('rows'):
            return {
                'totalViews': 0,
                'totalWatchTime': 0,
                'avgViewDuration': 0,
                'subscribersGained': 0
            }
        
        row = results['rows'][0]
        
        return {
            'totalViews': row[0],
            'totalWatchTime': row[1],
            'avgViewDuration': row[2],
            'subscribersGained': row[3]
        }
        
    except HttpError as e:
        logger.error(f"YouTube Analytics API error: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error fetching summary: {e}", exc_info=True)
        return None
