import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_database, save_game_stats, get_game_stats_one_hour_ago, get_trending_leaderboard, update_trending_status

def test_trending_logic():
    print("🚀 Testing Trending Logic...")
    init_database()
    
    game_id = "test_game_123"
    game_name = "Test Trending Game"
    
    # 1. Save stats from 1 hour ago
    print(f"   - Saving stats from 1h ago for {game_name}")
    save_game_stats(game_id, game_name, 1000)
    
    # Manually update the timestamp to 1 hour ago for testing
    import sqlite3
    db_path = "/app/data/clips.db"
    conn = sqlite3.connect(db_path)
    one_hour_ago = (datetime.utcnow() - timedelta(hours=1, minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute("UPDATE game_stats SET timestamp = ? WHERE game_id = ?", (one_hour_ago, game_id))
    conn.commit()
    conn.close()
    
    # 2. Get stats from 1h ago
    prev_viewers = get_game_stats_one_hour_ago(game_id)
    print(f"   - Previous viewers: {prev_viewers}")
    assert prev_viewers == 1000
    
    # 3. Calculate growth
    current_viewers = 1500 # 50% growth
    growth_rate = (current_viewers - prev_viewers) / prev_viewers
    print(f"   - Growth rate: {growth_rate:.2%}")
    
    is_trending = growth_rate > 0.25 and current_viewers > 500 # lowered for test
    if is_trending:
        print(f"   - 🔥 Game is trending!")
        update_trending_status(game_id, game_name, True)
    
    # 4. Check leaderboard
    # Insert a current stat so JOIN works in get_trending_leaderboard
    save_game_stats(game_id, game_name, current_viewers)
    
    leaderboard = get_trending_leaderboard()
    print(f"   - Leaderboard: {leaderboard}")
    assert len(leaderboard) > 0
    assert leaderboard[0]['game_id'] == game_id
    
    print("✅ Trending Logic Test Passed!")

if __name__ == "__main__":
    test_trending_logic()
