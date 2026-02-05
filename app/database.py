"""
SQLite database for tracking clip downloads and YouTube uploads.
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_FILE = Path("/app/data/clips.db")


def init_database():
    """Initialize the database and create tables if they don't exist."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS clips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clip_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                creator_name TEXT,
                broadcaster_name TEXT,
                game_name TEXT,
                game_id TEXT,
                view_count INTEGER,
                duration REAL,
                url TEXT,
                file_path TEXT,
                downloaded_at TIMESTAMP NOT NULL,
                uploaded_at TIMESTAMP,
                youtube_video_id TEXT,
                youtube_url TEXT,
                upload_status TEXT DEFAULT 'pending',
                upload_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
    
    logger.info("Database initialized")


@contextmanager
def get_db():
    """Get database connection context manager."""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def add_clip(clip_data, file_path):
    """
    Add downloaded clip to database.
    
    Args:
        clip_data: Dictionary with clip information
        file_path: Path to downloaded file
        
    Returns:
        int: ID of inserted record
    """
    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO clips (
                clip_id, title, creator_name, broadcaster_name,
                game_name, game_id, view_count, duration,
                url, file_path, downloaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            clip_data['id'],
            clip_data['title'],
            clip_data.get('creator_name'),
            clip_data.get('broadcaster_name'),
            clip_data.get('game_name'),
            clip_data.get('game_id'),
            clip_data.get('view_count'),
            clip_data.get('duration'),
            clip_data.get('url'),
            file_path,
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        return cursor.lastrowid


def update_upload_status(clip_id, youtube_video_id=None, status='uploaded', error=None):
    """
    Update YouTube upload status for a clip.
    
    Args:
        clip_id: Twitch clip ID
        youtube_video_id: YouTube video ID (if uploaded)
        status: Upload status ('uploaded', 'failed', 'pending')
        error: Error message if failed
    """
    youtube_url = f"https://youtube.com/watch?v={youtube_video_id}" if youtube_video_id else None
    
    with get_db() as conn:
        conn.execute('''
            UPDATE clips
            SET uploaded_at = ?,
                youtube_video_id = ?,
                youtube_url = ?,
                upload_status = ?,
                upload_error = ?
            WHERE clip_id = ?
        ''', (
            datetime.utcnow().isoformat() if status == 'uploaded' else None,
            youtube_video_id,
            youtube_url,
            status,
            error,
            clip_id
        ))
        conn.commit()


def get_stats():
    """
    Get statistics about clips and uploads.
    
    Returns:
        dict: Statistics
    """
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT
                COUNT(*) as total_clips,
                SUM(CASE WHEN upload_status = 'uploaded' THEN 1 ELSE 0 END) as uploaded,
                SUM(CASE WHEN upload_status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN upload_status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM clips
        ''')
        row = cursor.fetchone()
        
        return {
            'total_clips': row['total_clips'] or 0,
            'uploaded': row['uploaded'] or 0,
            'pending': row['pending'] or 0,
            'failed': row['failed'] or 0
        }


def get_recent_clips(limit=50):
    """
    Get recent clips with upload status.
    
    Args:
        limit: Maximum number of clips to return
        
    Returns:
        list: List of clip dictionaries
    """
    with get_db() as conn:
        cursor = conn.execute('''
            SELECT *
            FROM clips
            ORDER BY downloaded_at DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def delete_clip(clip_id):
    """
    Delete a clip from the database.
    
    Args:
        clip_id: Twitch clip ID
        
    Returns:
        str: File path of deleted clip (for cleanup) or None
    """
    with get_db() as conn:
        # Get file path first
        cursor = conn.execute('SELECT file_path FROM clips WHERE clip_id = ?', (clip_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        file_path = row['file_path']
        
        # Delete from database
        conn.execute('DELETE FROM clips WHERE clip_id = ?', (clip_id,))
        conn.commit()
        
        logger.info(f"Deleted clip {clip_id} from database")
        return file_path


def delete_clips_by_status(status):
    """
    Delete all clips with a specific status.
    
    Args:
        status: Upload status ('pending' or 'failed')
        
    Returns:
        list: List of file paths for cleanup
    """
    with get_db() as conn:
        # Get file paths first
        cursor = conn.execute('SELECT file_path FROM clips WHERE upload_status = ?', (status,))
        rows = cursor.fetchall()
        file_paths = [row['file_path'] for row in rows]
        
        # Delete from database
        conn.execute('DELETE FROM clips WHERE upload_status = ?', (status,))
        conn.commit()
        
        logger.info(f"Deleted {len(file_paths)} {status} clips from database")
        return file_paths
