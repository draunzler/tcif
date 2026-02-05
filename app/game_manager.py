"""
Game rotation manager for cycling through top trending games.
"""
import json
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

GAMES_FILE = Path("/app/data/top_games.json")


def ensure_data_dir():
    """Ensure the data directory exists."""
    GAMES_FILE.parent.mkdir(parents=True, exist_ok=True)


def save_top_games(games_data):
    """
    Save the top games to file with timestamp.
    
    Args:
        games_data: List of game dictionaries with 'id' and 'name'
    """
    ensure_data_dir()
    
    data = {
        "updated_at": datetime.utcnow().isoformat(),
        "games": games_data
    }
    
    with open(GAMES_FILE, "w") as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"✅ Saved {len(games_data)} top games")
    for i, game in enumerate(games_data, 1):
        logger.info(f"   {i}. {game['name']} (ID: {game['id']})")


def load_top_games():
    """
    Load the saved top games from file.
    
    Returns:
        List of game dictionaries, or None if file doesn't exist
    """
    if not GAMES_FILE.exists():
        return None
    
    with open(GAMES_FILE, "r") as f:
        data = json.load(f)
    
    return data.get("games", [])


def get_next_game_id():
    """
    Get the next game ID in rotation.
    Uses round-robin rotation through the saved games.
    
    Returns:
        tuple: (game_id, game_name) or (None, None) if no games saved
    """
    ensure_data_dir()
    
    games = load_top_games()
    if not games:
        return None, None
    
    # Track rotation state
    state_file = GAMES_FILE.parent / "rotation_state.json"
    
    if state_file.exists():
        with open(state_file, "r") as f:
            state = json.load(f)
            current_index = state.get("current_index", 0)
    else:
        current_index = 0
    
    # Get current game
    game = games[current_index % len(games)]
    
    # Update rotation state
    next_index = (current_index + 1) % len(games)
    with open(state_file, "w") as f:
        json.dump({"current_index": next_index}, f)
    
    return game["id"], game["name"]

