"""
Simplified scheduler for dedicated Valorant and CS YouTube channel bots.
No trending system, no quota balancing — just fetch top clip and post it.
"""
import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from app.clips import get_top_clips_last_n_hours
from app.downloader import download_twitch_clip
from app.video_processor import VideoProcessor
from app.channel_auth import is_channel_authenticated, CHANNEL_CONFIG
from app.channel_uploader import upload_video_to_channel
from app.database import add_channel_clip, is_clip_processed_for_channel

load_dotenv()

logger = logging.getLogger(__name__)


def _download_and_post(channel: str):
    """
    Core logic for dedicated channel bots.
    
    1. Check if the channel is authenticated — if not, skip entirely.
    2. Fetch top clips from past 48 hours for the channel's game.
    3. Filter out clips already posted on this channel.
    4. Pick the top clip by view count.
    5. Download → process → upload.
    
    Args:
        channel: 'valorant' or 'cs'
    """
    cfg = CHANNEL_CONFIG[channel]
    game_id = cfg["game_id"]
    game_name = cfg["game_name"]
    
    logger.info("=" * 80)
    logger.info(f"[{channel.upper()}] 🎮 Checking for {game_name} clips - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    # 1. Auth check — no download attempts if not linked
    if not is_channel_authenticated(channel):
        logger.info(f"[{channel.upper()}] ⏭️ Channel not linked. Skipping.")
        return
    
    try:
        # 2. Fetch top clips from past 24 hours
        logger.info(f"[{channel.upper()}] 🔍 Fetching top {game_name} clips from past 24 hours...")
        clips = get_top_clips_last_n_hours(game_id=game_id, hours=24, limit=50)
        
        if not clips:
            logger.info(f"[{channel.upper()}] 💤 No clips found for {game_name}.")
            return
        
        # 3. Filter out already posted clips for this channel
        qualified = [c for c in clips if not is_clip_processed_for_channel(c['id'], channel)]
        
        if not qualified:
            logger.info(f"[{channel.upper()}] 💤 All {game_name} clips from past 48h already posted.")
            return
        
        # 4. Pick top clip by view count
        qualified.sort(key=lambda x: x['view_count'], reverse=True)
        best_clip = qualified[0]
        logger.info(f"[{channel.upper()}] ✨ Top clip: \"{best_clip['title']}\" ({best_clip['view_count']:,} views)")
        
        # 5. Download
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = "".join(c for c in game_name if c.isalnum() or c in (' ', '-', '_')).strip()
        output_filename = f"{timestamp}_{channel}_{safe_name}_{best_clip['id']}.mp4"
        
        os.makedirs("/app/downloads", exist_ok=True)
        video_path = os.path.join("/app/downloads", output_filename)
        
        if not download_twitch_clip(best_clip['url'], video_path):
            logger.error(f"[{channel.upper()}] ❌ Failed to download clip")
            return
        
        # 6. Process video to vertical format
        processed_path = video_path.replace(".mp4", "_processed.mp4")
        processor = VideoProcessor()
        broadcaster = best_clip.get('broadcaster_name', 'Twitch')
        
        logger.info(f"[{channel.upper()}] 🎨 Processing clip from {broadcaster}...")
        if processor.process_video(video_path, processed_path, broadcaster):
            try:
                Path(video_path).unlink()
            except Exception:
                pass
            video_path = processed_path
            logger.info(f"[{channel.upper()}] ✅ Video processed: {video_path}")
        else:
            logger.warning(f"[{channel.upper()}] ⚠️ Processing failed, using original.")
        
        # 7. Record in database
        best_clip['game_name'] = game_name
        best_clip['game_id'] = game_id
        add_channel_clip(best_clip, video_path, channel)
        
        # 8. Upload to YouTube
        upload_success, yt_id, err = upload_video_to_channel(channel, video_path, best_clip)
        
        if upload_success:
            from app.database import update_upload_status
            update_upload_status(best_clip['id'], yt_id, 'uploaded')
            logger.info(f"[{channel.upper()}] 🎉 Posted: https://youtube.com/watch?v={yt_id}")
            try:
                Path(video_path).unlink()
            except Exception:
                pass
        else:
            from app.database import update_upload_status
            update_upload_status(best_clip['id'], None, 'failed', err)
            logger.error(f"[{channel.upper()}] ❌ Upload failed: {err}")
    
    except Exception as e:
        logger.error(f"[{channel.upper()}] ❌ Error: {e}", exc_info=True)


def download_and_post_valorant():
    """Download and post top Valorant clip to the Valorant YouTube channel."""
    _download_and_post("valorant")


def download_and_post_cs():
    """Download and post top CS clip to the CS YouTube channel."""
    _download_and_post("cs")
