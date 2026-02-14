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
from app.game_manager import save_top_games, get_next_game_id, load_top_games
from app.downloader import download_twitch_clip
from app.video_processor import VideoProcessor
from app.database import (
    save_game_stats, get_game_stats_one_hour_ago, 
    update_trending_status, get_trending_leaderboard,
    get_trending_game_by_id, set_game_post_override,
    add_clip, update_upload_status, is_clip_processed,
    get_recent_clips
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
    Runs every hour.
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
    Download clips based on new algorithm:
    - 4-day search range (96 hours)
    - Always 2 CS (32399) and 2 Valorant (516575) daily
    - Pick top viewed Clip
    - 8 total per day
    """
    logger.info("="*80)
    logger.info(f"⬇️  Searching for top clips (Last 4 days) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)
    
    try:
        # 1. Total Daily Check
        recent_clips = get_recent_clips(limit=50) # check plenty for 4 days
        now_utc = datetime.utcnow()
        posted_today = [c for c in recent_clips if (now_utc - datetime.fromisoformat(c['downloaded_at'].replace('Z', '+00:00'))).total_seconds() < 86400]
        
        if len(posted_today) >= 8:
            logger.info(f"🚫 Daily limit of 8 videos already reached. Skipping scanning.")
            return

        # 2. Quota Check for Today
        cs_today = [c for c in posted_today if c['game_id'] == '32399']
        val_today = [c for c in posted_today if c['game_id'] == '516575']
        
        target_game_id = None
        target_game_name = None
        
        if len(cs_today) < 2:
            target_game_id = '32399'
            target_game_name = 'Counter-Strike'
            logger.info(f"🎯 Target: {target_game_name} (Posted today: {len(cs_today)}/2)")
        elif len(val_today) < 2:
            target_game_id = '516575'
            target_game_name = 'Valorant'
            logger.info(f"🎯 Target: {target_game_name} (Posted today: {len(val_today)}/2)")
        else:
            # If quotas met, pick from trending or rotation
            leaderboard = get_trending_leaderboard()
            if leaderboard:
                actual_trends = [tg for tg in leaderboard if tg['game_id'] not in ['32399', '516575']]
                if actual_trends:
                    target_game_id = actual_trends[0]['game_id']
                    target_game_name = actual_trends[0]['game_name']
                    logger.info(f"🎯 Target: Trending - {target_game_name}")
            
            if not target_game_id:
                target_game_id = get_next_game_id()
                managed_games = load_top_games()
                g_info = next((g for g in managed_games if g['id'] == target_game_id), None)
                target_game_name = g_info['name'] if g_info else "Rotation"
                logger.info(f"🎯 Target: Rotation - {target_game_name}")

        # 3. Fetch Top Clip from Last 4 Days
        logger.info(f"🔍 Fetching top clips for {target_game_name} (ID: {target_game_id}) from last 4 days...")
        clips = get_top_clips_last_n_hours(game_id=target_game_id, hours=96, limit=50)
        
        # Filter out already processed
        qualified = [c for c in clips if not is_clip_processed(c['id'])]
        
        if not qualified:
            logger.info(f"💤 No new clips found for {target_game_name} in the last 4 days.")
            return

        # Sort by view count descending and pick the top one
        qualified.sort(key=lambda x: x['view_count'], reverse=True)
        best_clip = qualified[0]
        logger.info(f"✨ Best candidate: \"{best_clip['title']}\" ({best_clip['view_count']:,} views)")

        # 4. Download and Process
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_game_name = "".join(c for c in target_game_name if c.isalnum() or c in (' ', '-', '_')).strip()
        output_filename = f"{timestamp}_{safe_game_name}_{best_clip['id']}.mp4"
        
        # Ensure we are using the correct path (Docker context vs Local)
        # Based on logs and previous code, /app/downloads seems to be the target
        os.makedirs("/app/downloads", exist_ok=True)
        video_output_path = os.path.join("/app/downloads", output_filename)
        
        if download_twitch_clip(best_clip['url'], video_output_path):
            # Process video to vertical format with overlay
            processed_output_path = video_output_path.replace(".mp4", "_processed.mp4")
            processor = VideoProcessor()
            
            # broadcaster_name is needed for overlay
            broadcaster = best_clip.get('broadcaster_name', 'Twitch')
            logger.info(f"🎨 Processing clip for {broadcaster}...")
            
            if processor.process_video(video_output_path, processed_output_path, broadcaster):
                # Use the processed video
                try: 
                    from pathlib import Path
                    Path(video_output_path).unlink()
                except: pass
                video_output_path = processed_output_path
                logger.info(f"✅ Video processed: {video_output_path}")
            else:
                logger.warning("⚠️ Processing failed, using original.")

            best_clip['game_name'] = target_game_name
            best_clip['game_id'] = target_game_id
            
            clip_db_id = add_clip(best_clip, video_output_path)
            
            # 5. Upload to YouTube
            from app.youtube_auth import is_authenticated
            from app.youtube_uploader import upload_video
            from pathlib import Path
            
            if is_authenticated():
                upload_success, yt_id, err = upload_video(video_output_path, best_clip)
                if upload_success:
                    update_upload_status(best_clip['id'], yt_id, 'uploaded')
                    logger.info(f"🎉 Posted to YT: https://youtube.com/watch?v={yt_id}")
                    try: Path(video_output_path).unlink()
                    except: pass
                else:
                    update_upload_status(best_clip['id'], None, 'failed', err)
                    logger.error(f"❌ Upload failed: {err}")
            else:
                update_upload_status(best_clip['id'], None, 'pending')
                logger.warning("🕒 YT not authenticated, clip pending.")
                
        else:
            logger.error(f"❌ Failed to download clip")

    except Exception as e:
        logger.error(f"❌ Error in targeted download loop: {e}", exc_info=True)



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
    
    # Schedule daily game update every hour
    scheduler.add_job(
        update_top_games,
        trigger=CronTrigger(hour='*'),  # Every hour
        id='update_top_games',
        name='Update top trending games',
        replace_existing=True,
        misfire_grace_time=3600
    )
    
    # Schedule trending calculation every hour
    scheduler.add_job(
        calculate_trending,
        trigger=CronTrigger(minute=5),  # 5 minutes past every hour
        id='calculate_trending',
        name='Calculate trending games',
        replace_existing=True,
        misfire_grace_time=3600
    )
    
    # Schedule clip downloads every 3 hours to check for qualified candidates
    scheduler.add_job(
        download_clips,
        trigger=CronTrigger(hour='*/3', minute=10),  # Every 3 hours, at 10 mins past
        id='download_clips',
        name='Download qualified clips (Strict Quota)',
        replace_existing=True,
        misfire_grace_time=3600
    )
    
    logger.info("✅ Scheduler started! Running continuously...")
    logger.info("   Press Ctrl+C to stop")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Scheduler stopped")


if __name__ == "__main__":
    main()
