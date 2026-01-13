#!/usr/bin/env python3
"""
Database Migration Script

Migrates data from /tmp to persistent storage and adds required columns.
Run this ONCE before restarting the bot.

Usage:
    python scripts/migrate_database.py
"""

import os
import sqlite3
import shutil
from datetime import datetime

OLD_DB = "/tmp/learning_trader.db"
NEW_DIR = os.path.expanduser("~/.polymarket")
NEW_DB = os.path.join(NEW_DIR, "learning_trader.db")


def migrate():
    print("=" * 60)
    print("DATABASE MIGRATION")
    print("=" * 60)

    # Create new directory
    os.makedirs(NEW_DIR, exist_ok=True)
    print(f"\n1. Created directory: {NEW_DIR}")

    # Check for existing data
    if os.path.exists(OLD_DB):
        print(f"\n2. Found old database at {OLD_DB}")

        # Get row counts
        try:
            old_conn = sqlite3.connect(OLD_DB)
            old_cursor = old_conn.cursor()
            old_cursor.execute("SELECT COUNT(*) FROM predictions")
            old_count = old_cursor.fetchone()[0]
            old_conn.close()

            print(f"   Contains {old_count} predictions")

            # Copy if has data
            if old_count > 0:
                if os.path.exists(NEW_DB):
                    backup = NEW_DB + f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy(NEW_DB, backup)
                    print(f"   Backed up existing DB to {backup}")

                shutil.copy(OLD_DB, NEW_DB)
                print(f"   Copied data to {NEW_DB}")
            else:
                print("   No data to migrate")
        except Exception as e:
            print(f"   Error reading old database: {e}")
    else:
        print(f"\n2. No old database found at {OLD_DB}")

    # Check if new database exists from a previous run
    if not os.path.exists(NEW_DB):
        print(f"\n   Creating new database at {NEW_DB}")
        conn = sqlite3.connect(NEW_DB)
        cursor = conn.cursor()

        # Create predictions table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                token_id TEXT,
                market_type TEXT,
                prediction REAL,
                confidence REAL,
                entry_price REAL,
                position_size REAL,
                trade_executed INTEGER DEFAULT 0,
                position_open INTEGER DEFAULT 0,
                actual_outcome REAL,
                pnl REAL,
                resolved_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        print("   Created predictions table")

    # Ensure new database has required schema
    print("\n3. Ensuring database schema...")
    conn = sqlite3.connect(NEW_DB)
    cursor = conn.cursor()

    # Add columns if they don't exist
    columns_to_add = [
        ("resolved_at", "TEXT"),
        ("pnl", "REAL"),
        ("token_id", "TEXT"),
        ("market_type", "TEXT"),
        ("position_open", "INTEGER DEFAULT 0"),
        ("actual_outcome", "REAL")
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE predictions ADD COLUMN {col_name} {col_type}")
            print(f"   Added column: {col_name}")
        except sqlite3.OperationalError:
            print(f"   Column exists: {col_name}")

    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_token_id ON predictions(token_id)",
        "CREATE INDEX IF NOT EXISTS idx_market_type ON predictions(market_type)",
        "CREATE INDEX IF NOT EXISTS idx_position_open ON predictions(position_open)",
        "CREATE INDEX IF NOT EXISTS idx_trade_executed ON predictions(trade_executed)"
    ]

    for idx in indexes:
        cursor.execute(idx)

    conn.commit()
    print("   Indexes created")

    # Show current state
    cursor.execute('''
        SELECT COUNT(*),
               SUM(trade_executed),
               SUM(actual_outcome IS NOT NULL)
        FROM predictions
    ''')
    total, executed, with_outcome = cursor.fetchone()

    print(f"\n4. Database state:")
    print(f"   Total predictions: {total or 0}")
    print(f"   Trades executed: {executed or 0}")
    print(f"   With outcomes: {with_outcome or 0}")

    conn.close()

    print(f"\n5. Migration complete!")
    print(f"   New database location: {NEW_DB}")
    print(f"\n   Next step: Run outcome sync to populate P&L data:")
    print(f"   python -m agents.polymarket.outcome_sync")


if __name__ == "__main__":
    migrate()
