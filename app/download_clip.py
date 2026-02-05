#!/usr/bin/env python3
"""
List top Twitch clips from the last hour and download the topmost one.
"""
import os
import sys
from dotenv import load_dotenv
from app.clips import get_top_clips_last_hour
from app.downloader import download_twitch_clip

load_dotenv()


def main():
    """List top clips from the last hour and download the topmost one."""
    
    # Get broadcaster or game filter from environment
    broadcaster_id = os.getenv("TWITCH_BROADCASTER_ID")
    game_id = os.getenv("TWITCH_GAME_ID")
    
    # Check if we have any filter
    if not broadcaster_id and not game_id:
        print("❌ Configuration Error:")
        print("This script requires either TWITCH_BROADCASTER_ID or TWITCH_GAME_ID in your .env file.")
        print("\nFor automated downloads from trending games, use the scheduler instead:")
        print("  python3 -m app.scheduler")
        sys.exit(1)
    
    print("🔍 Fetching top clips from the last hour...\n")
    
    try:
        clips = get_top_clips_last_hour(
            broadcaster_id=broadcaster_id,
            game_id=game_id,
            limit=10
        )
    except ValueError as e:
        print(f"❌ Configuration Error:\n{e}")
        sys.exit(1)
    
    if not clips:
        print("❌ No clips found in the last hour.")
        return
    
    # Display the list of clips
    print(f"📊 Found {len(clips)} clip(s):\n")
    print("=" * 80)
    
    for i, clip in enumerate(clips, 1):
        print(f"{i}. {clip['title']}")
        print(f"   👤 Creator: {clip['creator_name']} | 📺 Broadcaster: {clip['broadcaster_name']}")
        print(f"   👁️  Views: {clip['view_count']:,} | ⏱️  Duration: {clip['duration']:.1f}s")
        print(f"   🔗 {clip['url']}")
        print("-" * 80)
    
    # Download the top clip
    top_clip = clips[0]
    print(f"\n⬇️  Downloading top clip: \"{top_clip['title']}\"")
    
    clip_url = top_clip['url']
    output_filename = f"{top_clip['id']}.mp4"
    
    success = download_twitch_clip(clip_url, output_filename)
    
    if success:
        print(f"\n✅ Successfully downloaded to: {output_filename}")
    else:
        print(f"\n❌ Failed to download clip")
        sys.exit(1)


if __name__ == "__main__":
    main()
