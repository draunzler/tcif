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

from app.clips import get_top_games, get_top_clips_last_hour
from app.game_manager import save_top_games, get_next_game_id
from app.downloader import download_twitch_clip

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



def download_clips():
    """
    Download clips from the next game in rotation.
    Runs hourly.
    """
    logger.info("="*80)
    logger.info(f"⬇️  Downloading clips - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)
    
    try:
        # Get next game in rotation
        game_id, game_name = get_next_game_id()
        
        if not game_id:
            logger.error("❌ No games available. Run game update first.")
            return
        
        logger.info(f"🎮 Selected game: {game_name} (ID: {game_id})")
        
        # Fetch top clips from this game
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
    
    # Run game update immediately on startup, then daily at 3 AM
    logger.info("📅 Scheduling jobs:")
    logger.info("   - Top games update: Daily at 3:00 AM UTC (fetches top 5 games)")
    logger.info("   - Clip downloads: Every 3 hours (rotates through the 5 games)")
    
    # Update games immediately on startup
    logger.info("🚀 Running initial top games update...")
    update_top_games()
    
    # Download a clip immediately for testing
    logger.info("🧪 Running immediate test download...")
    download_clips()
    
    # Schedule daily game update at 3 AM UTC
    scheduler.add_job(
        update_top_games,
        trigger=CronTrigger(hour=3, minute=0),
        id='update_top_games',
        name='Update top trending games',
        replace_existing=True
    )
    
    # Schedule clip downloads every 3 hours
    scheduler.add_job(
        download_clips,
        trigger=CronTrigger(hour='*/3', minute=0),  # Run every 3 hours
        id='download_clips',
        name='Download clips from rotating games',
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
