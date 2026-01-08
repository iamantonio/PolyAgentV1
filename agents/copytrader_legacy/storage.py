"""
SQLite storage backend for CopyTrader v1.

Tracks:
- Intents (for deduplication)
- Orders (execution history)
- Positions (myBoughtSize tracking per market/outcome)
- Daily PnL snapshots
- Trader stats (rolling windows for health monitoring)
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    """Recorded trade intent"""
    intent_id: str
    timestamp: datetime
    source_trader: str
    market_id: str
    outcome: str
    side: str
    size_usdc: Optional[float]
    size_tokens: Optional[float]
    status: str  # 'validated', 'rejected', 'executed'
    rejection_reason: Optional[str] = None


@dataclass
class Order:
    """Executed order record"""
    order_id: str
    intent_id: str
    market_id: str
    outcome: str
    side: str
    requested_size: float
    filled_size: float
    avg_price: float
    tx_hash: Optional[str]
    status: str  # 'pending', 'filled', 'failed'
    executed_at: datetime
    error_message: Optional[str] = None


@dataclass
class Position:
    """Current position tracking with myBoughtSize"""
    market_id: str
    outcome: str
    tokens_bought: float  # Total bought (across all buy orders)
    tokens_sold: float  # Total sold
    tokens_remaining: float  # bought - sold
    avg_buy_price: float
    total_usdc_spent: float
    realized_pnl: float  # From closed portions
    unrealized_pnl: float  # From open portion
    last_updated: datetime


@dataclass
class DailySnapshot:
    """Daily PnL snapshot"""
    date: str  # YYYY-MM-DD
    starting_balance: float
    ending_balance: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    pnl_pct: float
    num_trades: int


@dataclass
class TraderStats:
    """Trader performance stats"""
    trader_address: str
    window_start: datetime
    window_end: datetime
    num_trades: int
    wins: int
    losses: int
    win_rate_pct: float
    total_pnl_pct: float
    last_activity: datetime


class CopyTraderStorage:
    """SQLite storage backend for CopyTrader v1"""

    def __init__(self, db_path: str = "copytrader_v1.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            # Intents table (deduplication)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intents (
                    intent_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    source_trader TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size_usdc REAL,
                    size_tokens REAL,
                    status TEXT NOT NULL,
                    rejection_reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Orders table (execution history)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    intent_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    side TEXT NOT NULL,
                    requested_size REAL NOT NULL,
                    filled_size REAL NOT NULL,
                    avg_price REAL NOT NULL,
                    tx_hash TEXT,
                    status TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    error_message TEXT,
                    FOREIGN KEY (intent_id) REFERENCES intents(intent_id)
                )
            """)

            # Positions table (myBoughtSize tracking)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    market_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    tokens_bought REAL NOT NULL DEFAULT 0,
                    tokens_sold REAL NOT NULL DEFAULT 0,
                    tokens_remaining REAL NOT NULL DEFAULT 0,
                    avg_buy_price REAL NOT NULL DEFAULT 0,
                    total_usdc_spent REAL NOT NULL DEFAULT 0,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    unrealized_pnl REAL NOT NULL DEFAULT 0,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (market_id, outcome)
                )
            """)

            # Daily PnL snapshots
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daily_snapshots (
                    date TEXT PRIMARY KEY,
                    starting_balance REAL NOT NULL,
                    ending_balance REAL NOT NULL,
                    realized_pnl REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    total_pnl REAL NOT NULL,
                    pnl_pct REAL NOT NULL,
                    num_trades INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Trader stats (rolling windows)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trader_stats (
                    trader_address TEXT NOT NULL,
                    window_start TEXT NOT NULL,
                    window_end TEXT NOT NULL,
                    num_trades INTEGER NOT NULL,
                    wins INTEGER NOT NULL,
                    losses INTEGER NOT NULL,
                    win_rate_pct REAL NOT NULL,
                    total_pnl_pct REAL NOT NULL,
                    last_activity TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (trader_address, window_start)
                )
            """)

            # Kill switch state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kill_switch (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    is_active BOOLEAN NOT NULL DEFAULT 0,
                    reason TEXT,
                    triggered_at TEXT,
                    requires_manual_restart BOOLEAN NOT NULL DEFAULT 0
                )
            """)

            # Initialize kill switch row if doesn't exist
            conn.execute("""
                INSERT OR IGNORE INTO kill_switch (id, is_active, requires_manual_restart)
                VALUES (1, 0, 0)
            """)

            conn.commit()

    # Intent methods

    def record_intent(self, intent: Intent) -> None:
        """Record a trade intent"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO intents (
                    intent_id, timestamp, source_trader, market_id, outcome, side,
                    size_usdc, size_tokens, status, rejection_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                intent.intent_id,
                intent.timestamp.isoformat(),
                intent.source_trader,
                intent.market_id,
                intent.outcome,
                intent.side,
                intent.size_usdc,
                intent.size_tokens,
                intent.status,
                intent.rejection_reason,
            ))
            conn.commit()

    def intent_exists(self, intent_id: str) -> bool:
        """Check if intent has been seen before (deduplication)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM intents WHERE intent_id = ?",
                (intent_id,)
            )
            return cursor.fetchone() is not None

    # Order methods

    def record_order(self, order: Order) -> None:
        """Record an executed order"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO orders (
                    order_id, intent_id, market_id, outcome, side,
                    requested_size, filled_size, avg_price, tx_hash,
                    status, executed_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order.order_id,
                order.intent_id,
                order.market_id,
                order.outcome,
                order.side,
                order.requested_size,
                order.filled_size,
                order.avg_price,
                order.tx_hash,
                order.status,
                order.executed_at.isoformat(),
                order.error_message,
            ))
            conn.commit()

    # Position methods

    def update_position_buy(
        self, market_id: str, outcome: str, tokens: float, price: float, usdc: float
    ) -> None:
        """Update position after BUY order"""
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # Get current position
            cursor = conn.execute(
                "SELECT tokens_bought, total_usdc_spent FROM positions WHERE market_id = ? AND outcome = ?",
                (market_id, outcome)
            )
            row = cursor.fetchone()

            if row:
                new_tokens = row[0] + tokens
                new_usdc = row[1] + usdc
                new_avg_price = new_usdc / new_tokens if new_tokens > 0 else 0

                conn.execute("""
                    UPDATE positions
                    SET tokens_bought = ?, total_usdc_spent = ?, avg_buy_price = ?,
                        tokens_remaining = tokens_bought - tokens_sold, last_updated = ?
                    WHERE market_id = ? AND outcome = ?
                """, (new_tokens, new_usdc, new_avg_price, now, market_id, outcome))
            else:
                # Create new position
                conn.execute("""
                    INSERT INTO positions (
                        market_id, outcome, tokens_bought, tokens_sold, tokens_remaining,
                        avg_buy_price, total_usdc_spent, realized_pnl, unrealized_pnl, last_updated
                    ) VALUES (?, ?, ?, 0, ?, ?, ?, 0, 0, ?)
                """, (market_id, outcome, tokens, tokens, price, usdc, now))

            conn.commit()

    def update_position_sell(
        self, market_id: str, outcome: str, tokens: float, price: float
    ) -> float:
        """
        Update position after SELL order.

        Returns realized PnL from the sale.
        """
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            # Get current position
            cursor = conn.execute(
                "SELECT tokens_sold, avg_buy_price FROM positions WHERE market_id = ? AND outcome = ?",
                (market_id, outcome)
            )
            row = cursor.fetchone()

            if not row:
                logger.warning(f"Sell without position for {market_id} {outcome}")
                return 0.0

            new_tokens_sold = row[0] + tokens
            avg_buy_price = row[1]

            # Calculate realized PnL
            realized_pnl = tokens * (price - avg_buy_price)

            conn.execute("""
                UPDATE positions
                SET tokens_sold = ?, tokens_remaining = tokens_bought - ?,
                    realized_pnl = realized_pnl + ?, last_updated = ?
                WHERE market_id = ? AND outcome = ?
            """, (new_tokens_sold, new_tokens_sold, realized_pnl, now, market_id, outcome))

            conn.commit()

            return realized_pnl

    def get_position(self, market_id: str, outcome: str) -> Optional[Position]:
        """Get current position for a market/outcome"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM positions WHERE market_id = ? AND outcome = ?",
                (market_id, outcome)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return Position(
                market_id=row[0],
                outcome=row[1],
                tokens_bought=row[2],
                tokens_sold=row[3],
                tokens_remaining=row[4],
                avg_buy_price=row[5],
                total_usdc_spent=row[6],
                realized_pnl=row[7],
                unrealized_pnl=row[8],
                last_updated=datetime.fromisoformat(row[9]),
            )

    def get_open_positions(self) -> List[Position]:
        """Get all open positions (tokens_remaining > 0)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM positions WHERE tokens_remaining > 0 ORDER BY last_updated DESC"
            )

            positions = []
            for row in cursor.fetchall():
                positions.append(Position(
                    market_id=row[0],
                    outcome=row[1],
                    tokens_bought=row[2],
                    tokens_sold=row[3],
                    tokens_remaining=row[4],
                    avg_buy_price=row[5],
                    total_usdc_spent=row[6],
                    realized_pnl=row[7],
                    unrealized_pnl=row[8],
                    last_updated=datetime.fromisoformat(row[9]),
                ))

            return positions

    # Daily snapshot methods

    def record_daily_snapshot(self, snapshot: DailySnapshot) -> None:
        """Record end-of-day PnL snapshot"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO daily_snapshots (
                    date, starting_balance, ending_balance, realized_pnl,
                    unrealized_pnl, total_pnl, pnl_pct, num_trades
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.date,
                snapshot.starting_balance,
                snapshot.ending_balance,
                snapshot.realized_pnl,
                snapshot.unrealized_pnl,
                snapshot.total_pnl,
                snapshot.pnl_pct,
                snapshot.num_trades,
            ))
            conn.commit()

    def get_daily_snapshots(self, days: int = 7) -> List[DailySnapshot]:
        """Get last N daily snapshots"""
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM daily_snapshots WHERE date >= ? ORDER BY date DESC",
                (cutoff,)
            )

            snapshots = []
            for row in cursor.fetchall():
                snapshots.append(DailySnapshot(
                    date=row[0],
                    starting_balance=row[1],
                    ending_balance=row[2],
                    realized_pnl=row[3],
                    unrealized_pnl=row[4],
                    total_pnl=row[5],
                    pnl_pct=row[6],
                    num_trades=row[7],
                ))

            return snapshots

    # Trader stats methods

    def record_trader_stats(self, stats: TraderStats) -> None:
        """Record trader performance stats"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trader_stats (
                    trader_address, window_start, window_end, num_trades,
                    wins, losses, win_rate_pct, total_pnl_pct, last_activity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stats.trader_address,
                stats.window_start.isoformat(),
                stats.window_end.isoformat(),
                stats.num_trades,
                stats.wins,
                stats.losses,
                stats.win_rate_pct,
                stats.total_pnl_pct,
                stats.last_activity.isoformat(),
            ))
            conn.commit()

    def get_trader_stats(self, trader_address: str, days: int = 7) -> Optional[TraderStats]:
        """Get trader stats for last N days"""
        window_start = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT * FROM trader_stats
                   WHERE trader_address = ? AND window_start >= ?
                   ORDER BY window_start DESC LIMIT 1""",
                (trader_address, window_start)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return TraderStats(
                trader_address=row[0],
                window_start=datetime.fromisoformat(row[1]),
                window_end=datetime.fromisoformat(row[2]),
                num_trades=row[3],
                wins=row[4],
                losses=row[5],
                win_rate_pct=row[6],
                total_pnl_pct=row[7],
                last_activity=datetime.fromisoformat(row[8]),
            )

    # Kill switch methods

    def activate_kill_switch(self, reason: str, requires_restart: bool = False) -> None:
        """Activate kill switch"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE kill_switch
                SET is_active = 1, reason = ?, triggered_at = ?,
                    requires_manual_restart = ?
                WHERE id = 1
            """, (reason, datetime.utcnow().isoformat(), 1 if requires_restart else 0))
            conn.commit()

        logger.critical(f"🚨 KILL SWITCH ACTIVATED: {reason}")

    def is_kill_switch_active(self) -> Tuple[bool, Optional[str]]:
        """Check if kill switch is active"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT is_active, reason FROM kill_switch WHERE id = 1"
            )
            row = cursor.fetchone()
            if row:
                return (bool(row[0]), row[1])
            return (False, None)

    def deactivate_kill_switch(self) -> None:
        """Manually deactivate kill switch (requires manual restart flag check)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE kill_switch
                SET is_active = 0, reason = NULL, triggered_at = NULL,
                    requires_manual_restart = 0
                WHERE id = 1
            """)
            conn.commit()

        logger.info("Kill switch manually deactivated")

    def get_stats(self) -> dict:
        """Get overall storage stats"""
        with sqlite3.connect(self.db_path) as conn:
            # Count intents by status
            cursor = conn.execute(
                "SELECT status, COUNT(*) FROM intents GROUP BY status"
            )
            intent_stats = {row[0]: row[1] for row in cursor.fetchall()}

            # Count orders
            cursor = conn.execute("SELECT COUNT(*) FROM orders")
            order_count = cursor.fetchone()[0]

            # Count positions
            cursor = conn.execute("SELECT COUNT(*) FROM positions WHERE tokens_remaining > 0")
            position_count = cursor.fetchone()[0]

            # Get kill switch status
            is_killed, kill_reason = self.is_kill_switch_active()

            return {
                "intent_stats": intent_stats,
                "total_orders": order_count,
                "open_positions": position_count,
                "kill_switch_active": is_killed,
                "kill_switch_reason": kill_reason,
            }
