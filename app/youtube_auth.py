"""
YouTube OAuth 2.0 authentication handler.
"""
import os
import json
import logging
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# YouTube OAuth scopes
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly'
]

# Credentials file path
CREDENTIALS_FILE = Path("/app/data/youtube_credentials.json")
TOKEN_FILE = Path("/app/data/youtube_token.json")

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:8000/auth/youtube/callback")


def get_credentials():
    """
    Get valid YouTube credentials from stored token.
    
    Returns:
        Credentials object or None if not authenticated
    """
    if not TOKEN_FILE.exists():
        return None
    
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        
        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_credentials(creds)
        
        return creds if creds and creds.valid else None
    except Exception as e:
        logger.error(f"Error loading YouTube credentials: {e}")
        return None


def save_credentials(creds):
    """
    Save credentials to file.
    
    Args:
        creds: Credentials object
    """
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())


def create_oauth_flow():
    """
    Create OAuth flow for YouTube authentication.
    
    Returns:
        Flow object
    """
    client_config = {
        "web": {
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    return flow


def get_authorization_url():
    """
    Generate YouTube OAuth authorization URL.
    
    Returns:
        tuple: (authorization_url, state)
    """
    flow = create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    return authorization_url, state


def exchange_code_for_token(code, state):
    """
    Exchange authorization code for access token.
    
    Args:
        code: Authorization code from OAuth callback
        state: State parameter from OAuth callback
        
    Returns:
        Credentials object
    """
    flow = create_oauth_flow()
    flow.fetch_token(code=code)
    
    creds = flow.credentials
    save_credentials(creds)
    
    return creds


def is_authenticated():
    """
    Check if YouTube is authenticated.
    
    Returns:
        bool: True if authenticated, False otherwise
    """
    creds = get_credentials()
    return creds is not None


def disconnect():
    """
    Disconnect YouTube by removing stored credentials.
    """
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    logger.info("YouTube credentials removed")
