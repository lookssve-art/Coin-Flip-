"""SQLite database for tracking deals and avoiding duplicate notifications."""

import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "deals.db")


def get_connection():
    """Get a SQLite connection, creating tables if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_title TEXT NOT NULL,
            normalized_title TEXT NOT NULL,
            source_site TEXT NOT NULL,
            buy_price REAL,
            buy_currency TEXT,
            sell_price_eur REAL,
            profit_eur REAL,
            profit_percent REAL,
            buy_url TEXT,
            sell_url TEXT,
            notified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            last_run TEXT DEFAULT (datetime('now')),
            results_count INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_deals_normalized ON deals(normalized_title);
        CREATE INDEX IF NOT EXISTS idx_deals_created ON deals(created_at);
    """)
    conn.commit()


def deal_exists(conn, normalized_title, source_site, buy_url):
    """Check if a similar deal was already found (within last 24 hours)."""
    cursor = conn.execute(
        """SELECT id FROM deals
           WHERE normalized_title = ? AND source_site = ? AND buy_url = ?
           AND created_at > datetime('now', '-24 hours')""",
        (normalized_title, source_site, buy_url),
    )
    return cursor.fetchone() is not None


def save_deal(conn, deal_data):
    """Save a new deal to the database."""
    conn.execute(
        """INSERT INTO deals
           (product_title, normalized_title, source_site, buy_price, buy_currency,
            sell_price_eur, profit_eur, profit_percent, buy_url, sell_url, notified)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            deal_data["product_title"],
            deal_data["normalized_title"],
            deal_data["source_site"],
            deal_data["buy_price"],
            deal_data["buy_currency"],
            deal_data["sell_price_eur"],
            deal_data["profit_eur"],
            deal_data["profit_percent"],
            deal_data["buy_url"],
            deal_data["sell_url"],
            1,
        ),
    )
    conn.commit()


def update_search_history(conn, query, results_count):
    """Update or insert search history entry."""
    conn.execute(
        """INSERT INTO search_history (query, results_count)
           VALUES (?, ?)""",
        (query, results_count),
    )
    conn.commit()


def get_recent_deals(conn, hours=24):
    """Get deals found in the last N hours."""
    cursor = conn.execute(
        """SELECT * FROM deals
           WHERE created_at > datetime('now', ?)
           ORDER BY profit_percent DESC""",
        (f'-{hours} hours',),
    )
    return cursor.fetchall()
