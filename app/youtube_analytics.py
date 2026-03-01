"""
YouTube Analytics API integration.
"""
import logging
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.youtube_auth import get_credentials
from app.channel_auth import get_channel_credentials

logger = logging.getLogger(__name__)


def get_analytics_client(channel=None):
    """Get YouTube Analytics API client for the specified channel."""
    if channel:
        credentials = get_channel_credentials(channel)
    else:
        credentials = get_credentials()
        
    if not credentials:
        return None
    
    return build('youtubeAnalytics', 'v2', credentials=credentials)


def get_channel_analytics(days=30):
    """
    Get channel analytics for the last N days across all connected channels.
    
    Args:
        days: Number of days to fetch (default 30)
    
    Returns:
        dict: Analytics data or None if error
    """
    channels = [None, 'valorant', 'cs']
    aggregated_data = {}
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    
    any_success = False

    for channel in channels:
        try:
            analytics = get_analytics_client(channel)
            if not analytics:
                continue
            
            # Fetch analytics data
            results = analytics.reports().query(
                ids='channel==MINE',
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics='views,estimatedMinutesWatched,averageViewDuration,subscribersGained,subscribersLost',
                dimensions='day',
                sort='day'
            ).execute()
            
            rows = results.get('rows', [])
            if not rows:
                continue
                
            any_success = True
            
            for row in rows:
                day = row[0]
                views = row[1]
                watch_time = row[2]
                avg_duration = row[3]
                subs_gained = row[4]
                subs_lost = row[5]
                
                if day not in aggregated_data:
                    aggregated_data[day] = {
                        'views': 0,
                        'watchTime': 0,
                        'totalDuration': 0, # for computing weighted average
                        'subscribersGained': 0,
                        'subscribersLost': 0
                    }
                    
                aggregated_data[day]['views'] += views
                aggregated_data[day]['watchTime'] += watch_time
                aggregated_data[day]['totalDuration'] += (avg_duration * views)
                aggregated_data[day]['subscribersGained'] += subs_gained
                aggregated_data[day]['subscribersLost'] += subs_lost
                
        except HttpError as e:
            logger.error(f"YouTube Analytics API error for channel {channel}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error fetching analytics for channel {channel}: {e}", exc_info=True)

    if not any_success:
        return None

    # Prepare final sorted arrays
    labels = []
    views = []
    watch_time = []
    avg_view_duration = []
    subscribers_gained = []
    subscribers_lost = []
    
    for day in sorted(aggregated_data.keys()):
        data = aggregated_data[day]
        labels.append(day)
        views.append(data['views'])
        watch_time.append(data['watchTime'])
        
        # Calculate weighted average duration
        avg_dur = data['totalDuration'] / data['views'] if data['views'] > 0 else 0
        avg_view_duration.append(round(avg_dur))
        
        subscribers_gained.append(data['subscribersGained'])
        subscribers_lost.append(data['subscribersLost'])
        
    return {
        'labels': labels,
        'views': views,
        'watchTime': watch_time,
        'avgViewDuration': avg_view_duration,
        'subscribersGained': subscribers_gained,
        'subscribersLost': subscribers_lost
    }


def get_channel_summary():
    """
    Get summary statistics for all connected channels (last 28 days).
    
    Returns:
        dict: Summary stats or None if error
    """
    channels = [None, 'valorant', 'cs']
    
    total_views = 0
    total_watch_time = 0
    total_duration_weighted = 0
    total_subs_gained = 0
    
    any_success = False
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=28)

    for channel in channels:
        try:
            analytics = get_analytics_client(channel)
            if not analytics:
                continue
            
            results = analytics.reports().query(
                ids='channel==MINE',
                startDate=start_date.isoformat(),
                endDate=end_date.isoformat(),
                metrics='views,estimatedMinutesWatched,averageViewDuration,subscribersGained'
            ).execute()
            
            if not results.get('rows'):
                continue
                
            any_success = True
            row = results['rows'][0]
            
            views = row[0]
            watch_time = row[1]
            avg_duration = row[2]
            subs_gained = row[3]
            
            total_views += views
            total_watch_time += watch_time
            total_duration_weighted += (avg_duration * views)
            total_subs_gained += subs_gained
            
        except HttpError as e:
            logger.error(f"YouTube Analytics API error for channel {channel}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error fetching summary for channel {channel}: {e}", exc_info=True)

    if not any_success:
        return None

    avg_view_duration = total_duration_weighted / total_views if total_views > 0 else 0

    return {
        'totalViews': total_views,
        'totalWatchTime': total_watch_time,
        'avgViewDuration': round(avg_view_duration),
        'subscribersGained': total_subs_gained
    }
