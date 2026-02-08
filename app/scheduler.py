"""
APScheduler-based scheduler for downloading clips from top trending games.
"""
import os
import sys
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from app.clips import get_top_games, get_top_clips_last_hour, get_game_viewers, get_top_clips_last_n_hours
from app.game_manager import save_top_games, get_next_game_id
from app.downloader import download_twitch_clip
from app.database import (
    save_game_stats, get_game_stats_one_hour_ago, 
    update_trending_status, get_trending_leaderboard,
    get_trending_game_by_id, set_game_post_override,
    add_clip, update_upload_status
)

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def update_top_games():
    """
    Fetch and save the top 5 trending games from Twitch.
    Runs once per day.
    """
    logger.info("="*80)
    logger.info(f"🔄 Updating top trending games - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)
    
    try:
        # Fetch top 5 games
        top_games = get_top_games(limit=5)
        
        if not top_games:
            logger.error("❌ No games found")
            return
        
        # Save the top games
        save_top_games(top_games)
        
    except Exception as e:
        logger.error(f"❌ Error updating top games: {e}", exc_info=True)



def calculate_trending():
    """
    Calculate trending games based on viewer growth.
    Runs every hour.
    """
    logger.info("📈 Calculating trending games...")
    try:
        top_games = get_top_games(limit=20)
        for game in top_games:
            game_id = game['id']
            game_name = game['name']
            
            try:
                current_viewers = get_game_viewers(game_id)
                # Save stats
                save_game_stats(game_id, game_name, current_viewers)
                
                prev_viewers = get_game_stats_one_hour_ago(game_id)
                
                if prev_viewers and prev_viewers > 0:
                    growth_rate = (current_viewers - prev_viewers) / prev_viewers
                    logger.info(f"   - {game_name}: {current_viewers} viewers (Growth: {growth_rate:+.2%})")
                    
                    # Trending heuristic
                    is_trending = growth_rate > 0.25 and current_viewers > 5000
                    
                    # Update trending status in DB
                    if is_trending:
                        logger.info(f"🔥 TRENDING DETECTED: {game_name}")
                        
                        # Check if it's been trending for 24h
                        # (This is simplified for now: we check if it was already trending)
                        existing_trend = get_trending_game_by_id(game_id)
                        if existing_trend and existing_trend.get('is_trending'):
                            # Check timestamp
                            since = datetime.fromisoformat(existing_trend['trending_since'].replace('Z', '+00:00'))
                            if (datetime.utcnow() - since).total_seconds() >= 86400:
                                # Trending for > 24h, set override for 3 days
                                logger.info(f"💪 {game_name} trending for 24h+! Setting 3-day posting boost.")
                                set_game_post_override(game_id, 2, days=3)
                        
                        update_trending_status(game_id, game_name, True)
                    else:
                        # Only mark as not trending if it was previously trending
                        # This avoids cluttering the trending_games table
                        existing_trend = get_trending_game_by_id(game_id)
                        if existing_trend and existing_trend.get('is_trending'):
                            logger.info(f"📉 {game_name} no longer trending")
                            update_trending_status(game_id, game_name, False)
                else:
                    logger.info(f"   - {game_name}: {current_viewers} viewers (No history yet)")
            except Exception as inner_e:
                logger.error(f"Error calculating trending for {game_name}: {inner_e}")
                
    except Exception as e:
        logger.error(f"❌ Error in calculate_trending: {e}", exc_info=True)


def get_game_to_post():
    """
    Determine which game should be posted in the current slot (1-8).
    """
    # Count how many clips were posted in the last 24 hours
    from app.database import get_recent_clips
    recent_clips = get_recent_clips(limit=20) # Get enough to check last 24h
    now = datetime.utcnow()
    posted_today = [c for c in recent_clips if (now - datetime.fromisoformat(c['downloaded_at'].replace('Z', '+00:00'))).total_seconds() < 86400]
    
    if len(posted_today) >= 8:
        logger.info("🚫 Daily limit of 8 videos reached. Skipping this slot.")
        return None, None

    # Determine slot number (0-7)
    slot = len(posted_today)
    
    # Priority 1: CS (slot 0 and 3)
    cs_posted = [c for c in posted_today if c['game_id'] == '32399']
    if len(cs_posted) < 2 and (slot == 0 or slot == 3 or slot >= 6):
        return '32399', 'Counter-Strike'
        
    # Priority 2: Valorant (slot 1 and 4)
    val_posted = [c for c in posted_today if c['game_id'] == '516575']
    if len(val_posted) < 2 and (slot == 1 or slot == 4 or slot >= 6):
        return '516575', 'Valorant'

    # Priority 3: Top Trending Game with override (slot 2 and 5)
    leaderboard = get_trending_leaderboard()
    if leaderboard:
        top_trending = leaderboard[0]
        # Check if it has an active override
        if top_trending.get('post_count_override', 0) > 0:
            # Check if override still valid
            if top_trending.get('override_until'):
                until = datetime.fromisoformat(top_trending['override_until'].replace('Z', '+00:00'))
                if now < until:
                    # Check if already posted 2 for this game
                    trending_posted = [c for c in posted_today if c['game_id'] == top_trending['game_id']]
                    if len(trending_posted) < 2:
                        return top_trending['game_id'], top_trending['game_name']

    # Priority 4: Any trending game (if not CS/Val and we have space)
    if leaderboard:
        for tg in leaderboard:
            if tg['game_id'] not in ['32399', '516575']:
                # See if we already posted it today
                if not any(c for c in posted_today if c['game_id'] == tg['game_id']):
                    return tg['game_id'], tg['game_name']

    # Priority 5: Rotating top games
    return get_next_game_id()


def download_clips():
    """
    Download clips from the next game in rotation.
    Runs hourly.
    """
    logger.info("="*80)
    logger.info(f"⬇️  Downloading clips - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)
    
    try:
        # Determine which game to post
        game_id, game_name = get_game_to_post()
        
        if not game_id:
            return
        
        logger.info(f"🎮 Selected game: {game_name} (ID: {game_id})")
        
        # Check if it's a trending game to fetch the right clips
        existing_trend = get_trending_game_by_id(game_id)
        if existing_trend and existing_trend.get('is_trending'):
            logger.info("🔍 Fetching top clips from the last 3 hours (Trending rule)...")
            clips = get_top_clips_last_n_hours(game_id=game_id, hours=3, limit=10)
        else:
            logger.info("🔍 Fetching top clips from the last hour...")
            clips = get_top_clips_last_hour(game_id=game_id, limit=10)
        
        if not clips:
            logger.warning(f"❌ No clips found in the last hour for {game_name}.")
            return
        
        # Display the list of clips
        logger.info(f"📊 Found {len(clips)} clip(s):")
        logger.info("=" * 80)
        
        for i, clip in enumerate(clips, 1):
            logger.info(f"{i}. {clip['title']}")
            logger.info(f"   👤 Creator: {clip['creator_name']} | 📺 Broadcaster: {clip['broadcaster_name']}")
            logger.info(f"   👁️  Views: {clip['view_count']:,} | ⏱️  Duration: {clip['duration']:.1f}s")
            logger.info(f"   🔗 {clip['url']}")
            logger.info("-" * 80)
        
        # Download the top clip
        top_clip = clips[0]
        logger.info(f"⬇️  Downloading top clip: \"{top_clip['title']}\"")
        
        clip_url = top_clip['url']
        
        # Add timestamp and game name to filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_game_name = "".join(c for c in game_name if c.isalnum() or c in (' ', '-', '_')).strip()
        output_filename = f"{timestamp}_{safe_game_name}_{top_clip['id']}.mp4"
        
        # Ensure downloads directory exists
        os.makedirs("/app/downloads", exist_ok=True)
        video_output_path = os.path.join("/app/downloads", output_filename)
        
        success = download_twitch_clip(clip_url, video_output_path)
        
        if success:
            logger.info(f"✅ Successfully downloaded to: {output_filename}")
            
            # Add to database
            from app.database import add_clip, update_upload_status
            
            # Add game_name to clip data
            top_clip['game_name'] = game_name
            top_clip['game_id'] = game_id
            
            clip_db_id = add_clip(top_clip, video_output_path)
            logger.info(f"📝 Saved to database (ID: {clip_db_id})")
            
            # Check if YouTube is connected and upload
            from app.youtube_auth import is_authenticated
            from app.youtube_uploader import upload_video
            from pathlib import Path
            
            if is_authenticated():
                logger.info("📤 YouTube connected - uploading video...")
                
                video_path = Path("/app/downloads") / output_filename
                upload_success, youtube_video_id, error = upload_video(str(video_path), top_clip)
                
                if upload_success:
                    update_upload_status(top_clip['id'], youtube_video_id, 'uploaded')
                    logger.info(f"🎉 Uploaded to YouTube: https://youtube.com/watch?v={youtube_video_id}")
                    
                    # Delete video file after successful upload to save disk space
                    try:
                        video_path.unlink()
                        logger.info(f"🗑️  Deleted local file: {output_filename} (saved disk space)")
                    except Exception as delete_error:
                        logger.warning(f"⚠️  Could not delete file {output_filename}: {delete_error}")
                else:
                    update_upload_status(top_clip['id'], None, 'failed', error)
                    logger.error(f"❌ YouTube upload failed: {error}")
                    logger.info(f"📁 Keeping local file: {output_filename}")
            else:
                logger.info("ℹ️  YouTube not connected - skipping upload")
                update_upload_status(top_clip['id'], None, 'pending')
        else:
            logger.error(f"❌ Failed to download clip")
            
    except Exception as e:
        logger.error(f"❌ Error downloading clips: {e}", exc_info=True)



def main():
    """
    Start the scheduler.
    """
    logger.info("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                   TWITCH CLIP DOWNLOADER SCHEDULER                        ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)
    
    scheduler = BlockingScheduler()
    
    # Run initial checks
    logger.info("🚀 Running initial tasks...")
    update_top_games()
    calculate_trending()
    # Skip immediate download to avoid double posting if restarted frequently
    # download_clips()
    
    # Schedule daily game update at 3 AM UTC
    scheduler.add_job(
        update_top_games,
        trigger=CronTrigger(hour=3, minute=0),
        id='update_top_games',
        name='Update top trending games',
        replace_existing=True
    )
    
    # Schedule trending calculation every hour
    scheduler.add_job(
        calculate_trending,
        trigger=CronTrigger(minute=5),  # 5 minutes past every hour
        id='calculate_trending',
        name='Calculate trending games',
        replace_existing=True
    )
    
    # Schedule clip downloads every 3 hours (to match 8/day limit)
    scheduler.add_job(
        download_clips,
        trigger=CronTrigger(hour='*/3', minute=30),  # Every 3 hours at :30
        id='download_clips',
        name='Download and post clips',
        replace_existing=True
    )
    
    logger.info("✅ Scheduler started! Running continuously...")
    logger.info("   Press Ctrl+C to stop")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Scheduler stopped")


if __name__ == "__main__":
    main()
