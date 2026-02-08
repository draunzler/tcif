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
    Download clips based on strict quotas and >1500 views requirement.
    8 total per day:
    - 2 CS
    - 2 Valorant
    - 2 Trending (if available, else 2 General)
    - 2 General (or more to reach 8 total)
    """
    logger.info("="*80)
    logger.info(f"⬇️  Checking for qualified clips (>1500 views) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)
    
    try:
        # 1. Total Daily Check
        recent_clips = get_recent_clips(limit=24) # check plenty
        now_utc = datetime.utcnow()
        posted_today = [c for c in recent_clips if (now_utc - datetime.fromisoformat(c['downloaded_at'].replace('Z', '+00:00'))).total_seconds() < 86400]
        
        if len(posted_today) >= 8:
            logger.info(f"🚫 Daily limit of 8 videos already reached. Skipping scanning.")
            return

        # 2. Count what we have per category for today
        cs_today = [c for c in posted_today if c['game_id'] == '32399']
        val_today = [c for c in posted_today if c['game_id'] == '516575']
        
        leaderboard = get_trending_leaderboard()
        trending_ids = [tg['game_id'] for tg in leaderboard]
        trending_today = [c for c in posted_today if c['game_id'] in trending_ids and c['game_id'] not in ['32399', '516575']]
        
        general_today = [c for c in posted_today if c['game_id'] not in trending_ids and c['game_id'] not in ['32399', '516575']]

        logger.info(f"📊 Activity Today: CS:{len(cs_today)} Val:{len(val_today)} Trending:{len(trending_today)} General:{len(general_today)}")

        # 3. Determine which category to hunt for
        targets = [] # list of (id_list, name, quota)
        
        # Priority 1: CS
        if len(cs_today) < 2:
            targets.append((['32399'], 'Counter-Strike', 2 - len(cs_today)))
            
        # Priority 2: Valorant
        if len(val_today) < 2:
            targets.append((['516575'], 'Valorant', 2 - len(val_today)))
            
        # Priority 3: Trending
        if len(trending_today) < 2 and trending_ids:
            # Filter out CS/Val from trending if they overlap
            actual_trend_ids = [tid for tid in trending_ids if tid not in ['32399', '516575']]
            if actual_trend_ids:
                targets.append((actual_trend_ids, 'Trending', 2 - len(trending_today)))
        
        # Priority 4: General (Top Games)
        quota_remaining = 8 - len(posted_today)
        # We only hunt for general if we have slots left after priority targets
        # Or if we've already filled priority and still have total slots.
        if quota_remaining > 0:
            managed_games = load_top_games()
            general_ids = [g['id'] for g in managed_games if g['id'] not in ['32399', '516575'] and g['id'] not in trending_ids]
            if general_ids:
                targets.append((general_ids, 'General', quota_remaining))

        # 4. Loop through targets and try to find ONE qualifying clip per run
        # This prevents posting 5 videos at once if we've been offline.
        processed_count = 0
        for ids, cat_name, needed in targets:
            if processed_count > 0: break # Only 1 clip per 30 min run to keep it snappy
            
            logger.info(f"🎯 Hunting for {cat_name} (Need {needed} more today)...")
            
            for g_id in ids:
                # Find game name
                g_name = cat_name
                if cat_name in ['Trending', 'General']:
                    # Try to find specific name if available
                    if cat_name == 'Trending':
                        g_info = next((t for t in leaderboard if t['game_id'] == g_id), None)
                        g_name = g_info['game_name'] if g_info else cat_name
                    else:
                        g_info = next((g for g in managed_games if g['id'] == g_id), None)
                        g_name = g_info['name'] if g_info else cat_name

                # Fetch and filter
                clips = get_top_clips_last_n_hours(game_id=g_id, hours=6, limit=10)
                qualified = [c for c in clips if c['view_count'] >= 1500 and not is_clip_processed(c['id'])]
                
                if qualified:
                    best_clip = qualified[0]
                    logger.info(f"✨ Found candidate: \"{best_clip['title']}\" ({best_clip['view_count']:,} views)")
                    
                    # Download and process
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    safe_game_name = "".join(c for c in g_name if c.isalnum() or c in (' ', '-', '_')).strip()
                    output_filename = f"{timestamp}_{safe_game_name}_{best_clip['id']}.mp4"
                    
                    os.makedirs("/app/downloads", exist_ok=True)
                    video_output_path = os.path.join("/app/downloads", output_filename)
                    
                    if download_twitch_clip(best_clip['url'], video_output_path):
                        best_clip['game_name'] = g_name
                        best_clip['game_id'] = g_id
                        
                        clip_db_id = add_clip(best_clip, video_output_path)
                        
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
                        else:
                            update_upload_status(best_clip['id'], None, 'pending')
                        
                        processed_count += 1
                        break # Found one, move out
                    else:
                        logger.error(f"❌ Failed to download qualified clip")
            
        if processed_count == 0:
            logger.info("💤 No qualifying clips (>= 1500 views) found for needed categories.")

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
    
    # Schedule clip downloads every 3 hours to check for qualified candidates
    scheduler.add_job(
        download_clips,
        trigger=CronTrigger(hour='*/3'),  # Every 3 hours
        id='download_clips',
        name='Download qualified clips (Strict Quota)',
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
