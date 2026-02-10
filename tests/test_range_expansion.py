
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock database and other modules before importing scheduler
with patch('app.database.get_recent_clips', return_value=[]), \
     patch('app.database.is_clip_processed', return_value=False), \
     patch('app.database.get_trending_leaderboard', return_value=[]), \
     patch('app.game_manager.load_top_games', return_value=[{'id': '123', 'name': 'Test Game'}]), \
     patch('app.game_manager.get_next_game_id', return_value=('123', 'Test Game')), \
     patch('app.scheduler.download_twitch_clip', return_value=True), \
     patch('app.youtube_auth.is_authenticated', return_value=True), \
     patch('app.youtube_uploader.upload_video', return_value=(True, 'vid123', None)), \
     patch('app.database.add_clip', return_value=1), \
     patch('app.database.update_upload_status'):
    
    from app.scheduler import download_clips

def test_range_expansion():
    # Scenario: 
    # 6h search returns nothing (or clips with < 1500 views)
    # 12h search returns a qualified clip
    
    def side_effect(game_id, hours, limit):
        if hours == 6:
            return [{'id': 'low_view_clip', 'view_count': 500, 'url': 'url1', 'title': 'Low View'}]
        elif hours == 12:
            return [{'id': 'high_view_clip', 'view_count': 2000, 'url': 'url2', 'title': 'High View'}]
        return []

    with patch('app.scheduler.get_top_clips_last_n_hours', side_effect=side_effect) as mock_get_clips, \
         patch('app.scheduler.is_clip_processed', return_value=False) as mock_is_processed:
        
        print("Testing range expansion fallback (6h -> 12h)...")
        # Need to patch get_recent_clips again inside to be safe
        with patch('app.scheduler.get_recent_clips', return_value=[]):
            download_clips()
        
        # Verify get_top_clips_last_n_hours was called for 6h and 12h
        found_6 = False
        found_12 = False
        for call in mock_get_clips.call_args_list:
            args, kwargs = call
            search_hours = kwargs.get('hours') or (args[1] if len(args) > 1 else None)
            if search_hours == 6:
                found_6 = True
            if search_hours == 12:
                found_12 = True
        
        assert found_6, "Should have searched 6h range"
        assert found_12, "Should have expanded search to 12h range"
        print("✅ Expansion to 12h verified!")

if __name__ == "__main__":
    try:
        test_range_expansion()
        print("\nAll tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
