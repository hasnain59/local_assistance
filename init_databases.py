#!/usr/bin/env python3
"""Initialize all local databases with error handling."""
import sqlite3
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_directories():
    dirs = ["local_data/images", "local_data/audio", "local_data/backups", "logs"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory: {d}")

def init_calendar():
    try:
        conn = sqlite3.connect("local_data/calendar.db")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS appointments (...);
            CREATE TABLE IF NOT EXISTS availability_windows (...);
        """)
        conn.commit()
        conn.close()
        logger.info("Calendar DB initialized")
    except sqlite3.Error as e:
        logger.error(f"Calendar DB init failed: {e}")
        raise

# ... similar for tasks, calls, media, contacts, settings ...

if __name__ == "__main__":
    create_directories()
    init_calendar()
    # ... call other init functions
    logger.info("All databases ready")
