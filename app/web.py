"""
FastAPI web application for dashboard and YouTube OAuth.
"""
import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.youtube_auth import (
    get_authorization_url,
    exchange_code_for_token,
    is_authenticated,
    disconnect as youtube_disconnect
)
from app.database import get_stats, get_recent_clips, delete_clip, delete_clips_by_status
from app.youtube_analytics import get_channel_analytics, get_channel_summary

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="Twitch Clip Auto-Uploader")

# Get absolute path to static directory
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Store OAuth state temporarily
oauth_states = set()


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard homepage."""
    with open(os.path.join(STATIC_DIR, "index.html")) as f:
        return HTMLResponse(content=f.read())


@app.get("/api/stats")
async def api_stats():
    """Get statistics."""
    stats = get_stats()
    stats['youtube_connected'] = is_authenticated()
    return JSONResponse(stats)


@app.get("/api/uploads")
async def api_uploads(limit: int = 50):
    """Get recent uploads."""
    clips = get_recent_clips(limit=limit)
    return JSONResponse(clips)


@app.get("/auth/youtube")
async def youtube_auth():
    """Start YouTube OAuth flow."""
    try:
        auth_url, state = get_authorization_url()
        oauth_states.add(state)
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"OAuth initiation error: {e}", exc_info=True)
        return JSONResponse(
            {"error": "Failed to initiate YouTube authentication"},
            status_code=500
        )


@app.get("/auth/youtube/callback")
async def youtube_callback(code: str = None, state: str = None, error: str = None):
    """Handle YouTube OAuth callback."""
    if error:
        logger.error(f"OAuth error: {error}")
        return RedirectResponse(url="/?error=oauth_failed")
    
    if not code or not state:
        return RedirectResponse(url="/?error=missing_params")
    
    if state not in oauth_states:
        return RedirectResponse(url="/?error=invalid_state")
    
    oauth_states.discard(state)
    
    try:
        exchange_code_for_token(code, state)
        logger.info("✅ YouTube authentication successful")
        return RedirectResponse(url="/?success=youtube_connected")
    except Exception as e:
        logger.error(f"Token exchange error: {e}", exc_info=True)
        return RedirectResponse(url="/?error=token_exchange_failed")


@app.post("/api/disconnect")
async def api_disconnect():
    """Disconnect YouTube account."""
    try:
        youtube_disconnect()
        return JSONResponse({"success": True, "message": "Disconnected from YouTube"})
    except Exception as e:
        logger.error(f"Disconnect error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to disconnect"},
            status_code=500
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/api/analytics")
async def api_analytics(days: int = 30):
    """Get YouTube Analytics data."""
    try:
        if not is_authenticated():
            return JSONResponse(
                {"error": "YouTube not connected"},
                status_code=401
            )
        
        analytics_data = get_channel_analytics(days=days)
        summary = get_channel_summary()
        
        if analytics_data is None:
            return JSONResponse(
                {"error": "Failed to fetch analytics. You may need to re-authenticate to grant analytics permissions."},
                status_code=500
            )
        
        return JSONResponse({
            "timeSeries": analytics_data,
            "summary": summary
        })
        
    except Exception as e:
        logger.error(f"Analytics API error: {e}", exc_info=True)
        return JSONResponse(
            {"error": "Failed to fetch analytics"},
            status_code=500
        )


@app.delete("/api/clips/{clip_id}")
async def api_delete_clip(clip_id: str):
    """Delete a specific clip."""
    try:
        file_path = delete_clip(clip_id)
        
        if not file_path:
            return JSONResponse(
                {"success": False, "error": "Clip not found"},
                status_code=404
            )
        
        # Delete file from filesystem
        import os
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
        
        return JSONResponse({
            "success": True,
            "message": f"Clip {clip_id} deleted"
        })
        
    except Exception as e:
        logger.error(f"Delete clip error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to delete clip"},
            status_code=500
        )


@app.delete("/api/clips/cleanup")
async def api_cleanup_clips(status: str = "pending"):
    """Bulk delete clips by status (pending or failed)."""
    try:
        if status not in ['pending', 'failed']:
            return JSONResponse(
                {"success": False, "error": "Status must be 'pending' or 'failed'"},
                status_code=400
            )
        
        file_paths = delete_clips_by_status(status)
        
        # Delete files from filesystem
        import os
        deleted_count = 0
        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} {status} clips")
        
        return JSONResponse({
            "success": True,
            "message": f"Deleted {deleted_count} {status} clips",
            "count": deleted_count
        })
        
    except Exception as e:
        logger.error(f"Cleanup error: {e}", exc_info=True)
        return JSONResponse(
            {"success": False, "error": "Failed to cleanup clips"},
            status_code=500
        )
