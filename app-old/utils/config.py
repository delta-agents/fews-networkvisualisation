"""
Configuration utilities for the FEWS visualization application.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

def load_config():
    """Load configuration from environment variables."""
    # Load .env file from the project root
    env_path = Path(__file__).parent.parent.parent / "env" / ".env"
    load_dotenv(dotenv_path=env_path)
    
    # Get database path from environment or use default
    db_path = os.getenv("FEWS_DB_PATH", "../db/fews_config.db3")
    db_path = Path(db_path).resolve()
    
    # Get log directory from environment or use default
    log_dir = os.getenv("FEWS_LOG_DIR", str(Path(__file__).parent.parent.parent / "logs"))
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Get application title from environment or use default
    app_title = os.getenv("FEWS_APP_TITLE", "FEWS Network Visualization")
    
    # Get application version from environment or use default
    app_version = os.getenv("FEWS_APP_VERSION", "0.2.0")
    
    return {
        "db_path": str(db_path),
        "log_dir": str(log_dir),
        "app_title": app_title,
        "app_version": app_version
    } 