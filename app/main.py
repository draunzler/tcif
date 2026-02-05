"""
Main application runner - runs both web server and scheduler concurrently.
"""
import os
import sys
import logging
import threading
import uvicorn
from dotenv import load_dotenv

# Initialize database before anything else
from app.database import init_database
init_database()

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def run_scheduler():
    """Run the clip download scheduler."""
    from app.scheduler import main
    main()


def run_web_server():
    """Run the web dashboard server."""
    uvicorn.run(
        "app.web:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


def main():
    """Run both scheduler and web server concurrently."""
    logger.info("""
╔═══════════════════════════════════════════════════════════════════════════╗
║         TWITCH CLIP AUTO-UPLOADER - Scheduler + Dashboard                ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """)
    
    logger.info("🌐 Starting web dashboard on http://0.0.0.0:8000")
    logger.info("⏰ Starting clip download scheduler")
    
    # Run web server in a separate thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Run scheduler in main thread (blocking)
    run_scheduler()


if __name__ == "__main__":
    main()
