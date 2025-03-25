"""
Utility functions for the FEWS chat application.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

def load_config():
    """Load configuration from environment variables."""
    # Load .env file from the project root
    env_path = Path(__file__).parent.parent / "env" / ".env"
    load_dotenv(dotenv_path=env_path)
    
    # Get database path from environment or use default
    db_path = os.getenv("FEWS_DB_PATH", "../db/fews_config.db3")
    db_path = Path(db_path).resolve()
    
    # Get log directory from environment or use default
    log_dir = os.getenv("FEWS_LOG_DIR", str(Path(__file__).parent.parent / "logs"))
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "db_path": str(db_path),
        "log_dir": str(log_dir)
    }
