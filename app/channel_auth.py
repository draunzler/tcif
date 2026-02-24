"""
YouTube OAuth 2.0 authentication handler for dedicated channel bots (Valorant & CS).
Each channel has its own token file and can optionally use its own OAuth credentials.
"""
import os
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
]

# Channel configurations
CHANNEL_CONFIG = {
    "valorant": {
        "token_file": Path("/app/data/youtube_token_valorant.json"),
        "game_id": "516575",
        "game_name": "Valorant",
        "client_id_env": "VALORANT_YOUTUBE_CLIENT_ID",
        "client_secret_env": "VALORANT_YOUTUBE_CLIENT_SECRET",
        "redirect_uri_env": "VALORANT_YOUTUBE_REDIRECT_URI",
        "default_redirect": "http://localhost:8000/auth/youtube/valorant/callback",
    },
    "cs": {
        "token_file": Path("/app/data/youtube_token_cs.json"),
        "game_id": "32399",
        "game_name": "Counter-Strike",
        "client_id_env": "CS_YOUTUBE_CLIENT_ID",
        "client_secret_env": "CS_YOUTUBE_CLIENT_SECRET",
        "redirect_uri_env": "CS_YOUTUBE_REDIRECT_URI",
        "default_redirect": "http://localhost:8000/auth/youtube/cs/callback",
    },
}


def _get_config(channel: str) -> dict:
    """Get config for a channel, raising if invalid."""
    if channel not in CHANNEL_CONFIG:
        raise ValueError(f"Unknown channel: {channel}. Must be 'valorant' or 'cs'.")
    return CHANNEL_CONFIG[channel]


def _get_client_credentials(channel: str) -> tuple:
    """
    Get OAuth client credentials for a channel.
    Falls back to the main YouTube credentials if channel-specific ones aren't set.
    """
    cfg = _get_config(channel)
    
    client_id = os.getenv(cfg["client_id_env"]) or os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv(cfg["client_secret_env"]) or os.getenv("YOUTUBE_CLIENT_SECRET")
    redirect_uri = os.getenv(cfg["redirect_uri_env"], cfg["default_redirect"])
    
    return client_id, client_secret, redirect_uri


def get_channel_credentials(channel: str):
    """
    Get valid YouTube credentials for a specific channel.
    
    Returns:
        Credentials object or None if not authenticated
    """
    cfg = _get_config(channel)
    token_file = cfg["token_file"]
    
    if not token_file.exists():
        return None
    
    try:
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_channel_credentials(channel, creds)
        
        return creds if creds and creds.valid else None
    except Exception as e:
        logger.error(f"Error loading {channel} channel credentials: {e}")
        return None


def save_channel_credentials(channel: str, creds):
    """Save credentials to the channel-specific token file."""
    cfg = _get_config(channel)
    token_file = cfg["token_file"]
    
    token_file.parent.mkdir(parents=True, exist_ok=True)
    with open(token_file, 'w') as f:
        f.write(creds.to_json())


def create_channel_oauth_flow(channel: str):
    """Create OAuth flow for a specific channel."""
    client_id, client_secret, redirect_uri = _get_client_credentials(channel)
    
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    return flow


def get_channel_authorization_url(channel: str):
    """
    Generate YouTube OAuth authorization URL for a channel.
    
    Returns:
        tuple: (authorization_url, state)
    """
    flow = create_channel_oauth_flow(channel)
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    return authorization_url, state


def exchange_channel_code_for_token(channel: str, code: str, state: str):
    """
    Exchange authorization code for access token for a specific channel.
    
    Returns:
        Credentials object
    """
    flow = create_channel_oauth_flow(channel)
    flow.fetch_token(code=code)
    
    creds = flow.credentials
    save_channel_credentials(channel, creds)
    
    return creds


def is_channel_authenticated(channel: str) -> bool:
    """Check if a specific channel has valid YouTube credentials."""
    creds = get_channel_credentials(channel)
    return creds is not None


def disconnect_channel(channel: str):
    """Disconnect a channel by removing its stored credentials."""
    cfg = _get_config(channel)
    token_file = cfg["token_file"]
    
    if token_file.exists():
        token_file.unlink()
    logger.info(f"{channel} channel YouTube credentials removed")
