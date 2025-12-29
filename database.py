import sqlite3
import os
from datetime import datetime, timedelta

DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

DB_PATH = os.path.join(DATA_DIR, "listings.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_listings (
                id TEXT PRIMARY KEY,
                notified BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def is_seen(listing_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT 1 FROM seen_listings WHERE id = ?", (listing_id,))
        return cursor.fetchone() is not None

def is_notified(listing_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT 1 FROM seen_listings WHERE id = ? AND notified = 1", (listing_id,))
        return cursor.fetchone() is not None

def mark_as_seen(listing_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO seen_listings (id, notified) VALUES (?, 0)", (listing_id,))
        conn.commit()

def mark_as_notified(listing_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE seen_listings SET notified = 1 WHERE id = ?", (listing_id,))
        conn.commit()

def cleanup_old_items(days: int = 7):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM seen_listings WHERE created_at < ?", (cutoff,))
        conn.commit()
