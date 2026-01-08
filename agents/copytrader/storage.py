"""
SQLite storage schema and operations.

Tables:
- positions: Current open positions
- trade_history: All executed trades
- intent_log: All intents (accepted and rejected)
- risk_events: Risk limit triggers and kills

Fail-loud: DB errors raise exceptions, never silent.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

# Schema version for migration tracking
SCHEMA_VERSION = 1


class CopyTraderDB:
    """SQLite database for CopyTrader persistence."""

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema. Idempotent."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Metadata table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            # Check schema version
            cursor.execute("SELECT value FROM metadata WHERE key = 'schema_version'")
            row = cursor.fetchone()
            if row:
                existing_version = int(row[0])
                if existing_version != SCHEMA_VERSION:
                    raise RuntimeError(
                        f"Schema version mismatch: expected {SCHEMA_VERSION}, got {existing_version}"
                    )
            else:
                cursor.execute(
                    "INSERT INTO metadata (key, value) VALUES ('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )

            # Positions table - current open positions
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_timestamp TEXT NOT NULL,
                    trader_id TEXT NOT NULL,
                    UNIQUE(market_id, side)
                )
                """
            )

            # Trade history - all executed trades
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    intent_id INTEGER,
                    market_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    trader_id TEXT NOT NULL,
                    execution_status TEXT NOT NULL,
                    execution_detail TEXT,
                    pnl REAL,
                    pnl_pct REAL,
                    FOREIGN KEY (intent_id) REFERENCES intent_log(id)
                )
                """
            )

            # Intent log - all intents (accepted and rejected)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS intent_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trader_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    intent_timestamp TEXT NOT NULL,
                    received_timestamp TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    rejection_reason TEXT,
                    rejection_detail TEXT,
                    risk_decision TEXT,
                    risk_decision_detail TEXT
                )
                """
            )

            # Risk events - limit triggers, kills, stops
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    daily_pnl REAL NOT NULL,
                    daily_pnl_pct REAL NOT NULL,
                    total_pnl REAL NOT NULL,
                    total_pnl_pct REAL NOT NULL,
                    detail TEXT,
                    triggered_by_trade_id INTEGER,
                    FOREIGN KEY (triggered_by_trade_id) REFERENCES trade_history(id)
                )
                """
            )

            # Capital state tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS capital_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    starting_capital REAL NOT NULL,
                    current_capital REAL NOT NULL,
                    daily_pnl REAL NOT NULL,
                    total_pnl REAL NOT NULL
                )
                """
            )

            conn.commit()

    def log_intent(
        self,
        trader_id: str,
        market_id: str,
        side: str,
        size: Decimal,
        intent_timestamp: datetime,
        validation_status: str,
        rejection_reason: Optional[str] = None,
        rejection_detail: Optional[str] = None,
        risk_decision: Optional[str] = None,
        risk_decision_detail: Optional[str] = None,
    ) -> int:
        """
        Log an intent (accepted or rejected).

        Returns:
            Intent log ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO intent_log (
                    trader_id, market_id, side, size, intent_timestamp,
                    received_timestamp, validation_status, rejection_reason,
                    rejection_detail, risk_decision, risk_decision_detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trader_id,
                    market_id,
                    side,
                    float(size),
                    intent_timestamp.isoformat(),
                    datetime.now().isoformat(),
                    validation_status,
                    rejection_reason,
                    rejection_detail,
                    risk_decision,
                    risk_decision_detail,
                ),
            )
            return cursor.lastrowid

    def log_risk_event(
        self,
        event_type: str,
        daily_pnl: Decimal,
        daily_pnl_pct: Decimal,
        total_pnl: Decimal,
        total_pnl_pct: Decimal,
        detail: Optional[str] = None,
        triggered_by_trade_id: Optional[int] = None,
    ) -> int:
        """
        Log a risk event (stop, kill, etc.).

        Returns:
            Risk event log ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO risk_events (
                    event_type, timestamp, daily_pnl, daily_pnl_pct,
                    total_pnl, total_pnl_pct, detail, triggered_by_trade_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    datetime.now().isoformat(),
                    float(daily_pnl),
                    float(daily_pnl_pct),
                    float(total_pnl),
                    float(total_pnl_pct),
                    detail,
                    triggered_by_trade_id,
                ),
            )
            return cursor.lastrowid

    def record_capital_state(
        self,
        starting_capital: Decimal,
        current_capital: Decimal,
        daily_pnl: Decimal,
        total_pnl: Decimal,
    ):
        """Record current capital state snapshot."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO capital_state (
                    timestamp, starting_capital, current_capital,
                    daily_pnl, total_pnl
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(),
                    float(starting_capital),
                    float(current_capital),
                    float(daily_pnl),
                    float(total_pnl),
                ),
            )
