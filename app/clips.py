"""
Twitch Clips API utilities.
"""
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

TOKEN_URL = "https://id.twitch.tv/oauth2/token"

# Token cache
_token_cache = {
    "access_token": None,
    "expires_at": None
}


def get_app_access_token():
    """
    Get a valid app access token, using cached token if still valid.
    Automatically requests a new token when the cached one expires.
    
    Returns:
        str: Valid app access token
    """
    now = datetime.utcnow()
    
    # Check if we have a valid cached token
    if _token_cache["access_token"] and _token_cache["expires_at"]:
        if now < _token_cache["expires_at"]:
            return _token_cache["access_token"]
    
    # Request new token
    token_payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    
    token_response = requests.post(TOKEN_URL, data=token_payload, timeout=15)
    token_response.raise_for_status()
    token_data = token_response.json()
    
    # Cache the token with expiry (subtract 60 seconds for safety margin)
    _token_cache["access_token"] = token_data["access_token"]
    _token_cache["expires_at"] = now + timedelta(seconds=token_data["expires_in"] - 60)
    
    return _token_cache["access_token"]


def get_top_games(limit: int = 20):
    """
    Get the top trending games on Twitch.
    
    Args:
        limit: Number of top games to return (default 20, max 100)
    
    Returns:
        List of game data dictionaries with 'id' and 'name'
    """
    # Get valid access token (cached or new)
    access_token = get_app_access_token()
    
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    
    params = {
        "first": min(limit, 100)  # API max is 100
    }
    
    games_url = "https://api.twitch.tv/helix/games/top"
    r = requests.get(games_url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    
    return r.json()["data"]


def get_top_clips_last_hour(broadcaster_id: str = None, game_id: str = None, limit: int = 1):
    """
    Get the top clips from the last hour.
    
    NOTE: Twitch API requires at least one of broadcaster_id or game_id.
    
    Args:
        broadcaster_id: Broadcaster ID to filter clips (required if game_id not provided)
        game_id: Game ID to filter clips (required if broadcaster_id not provided)
        limit: Number of clips to return (default 1, max 100)
    
    Returns:
        List of clip data dictionaries
    
    Raises:
        ValueError: If neither broadcaster_id nor game_id is provided
    """
    if not broadcaster_id and not game_id:
        raise ValueError(
            "Twitch API requires either broadcaster_id or game_id to fetch clips.\n"
            "Set TWITCH_BROADCASTER_ID or TWITCH_GAME_ID in your .env file.\n\n"
            "To get a broadcaster ID, go to: https://www.streamweasels.com/tools/convert-twitch-username-to-user-id/\n"
            "Common game IDs:\n"
            "  - Just Chatting: 509658\n"
            "  - League of Legends: 21779\n"
            "  - Fortnite: 33214\n"
            "  - Minecraft: 27471\n"
            "  - GTA V: 32982\n"
            "Or find more at: https://www.streamweasels.com/tools/convert-game-name-to-game-id/"
        )
    
    # Get valid access token (cached or new)
    access_token = get_app_access_token()
    
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    
    # Calculate time range (last hour)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)
    
    params = {
        "started_at": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ended_at": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first": min(limit, 100)  # API max is 100
    }
    
    if broadcaster_id:
        params["broadcaster_id"] = broadcaster_id
    if game_id:
        params["game_id"] = game_id
    
    clips_url = "https://api.twitch.tv/helix/clips"
    r = requests.get(clips_url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    
    return r.json()["data"]
def get_game_viewers(game_id: str):
    """
    Get the total current viewer count for a specific game.
    Uses the /helix/streams endpoint.
    
    Args:
        game_id: The ID of the game
        
    Returns:
        int: Total viewer count
    """
    access_token = get_app_access_token()
    
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    
    params = {
        "game_id": game_id,
        "first": 100 # Top 100 streams for aggregate
    }
    
    streams_url = "https://api.twitch.tv/helix/streams"
    r = requests.get(streams_url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    
    data = r.json().get("data", [])
    total_viewers = sum(stream["viewer_count"] for stream in data)
    
    return total_viewers


def get_top_clips_last_n_hours(game_id: str, hours: int = 3, limit: int = 1):
    """
    Get the top clips for a game within the last N hours.
    
    Args:
        game_id: Game ID to filter clips
        hours: Number of hours to look back
        limit: Number of clips to return
        
    Returns:
        List of clip data dictionaries
    """
    access_token = get_app_access_token()
    
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
    }
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    params = {
        "game_id": game_id,
        "started_at": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ended_at": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first": min(limit, 100)
    }
    
    clips_url = "https://api.twitch.tv/helix/clips"
    r = requests.get(clips_url, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    
    return r.json()["data"]
