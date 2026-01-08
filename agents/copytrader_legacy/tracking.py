"""
Purchase tracking for accurate sell calculations.

This module implements "myBoughtSize" style tracking to prevent position drift.
When we BUY, we record the exact tokens purchased. When we SELL, we use this
to calculate the proportional amount to sell based on what WE actually bought,
not what the trader's current position is.

Storage backend is pluggable (SQLite by default, MongoDB optional).
"""

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PurchaseRecord:
    """Record of a purchase we made"""

    market_id: str
    asset_id: str
    tokens_bought: float
    price_paid: float
    usdc_spent: float
    timestamp: datetime
    source_trader: str
    intent_id: str
    order_id: Optional[str] = None


class TrackingBackend(ABC):
    """Abstract interface for purchase tracking storage"""

    @abstractmethod
    def record_purchase(self, purchase: PurchaseRecord) -> None:
        """Record a purchase"""
        pass

    @abstractmethod
    def record_sale(
        self, market_id: str, asset_id: str, tokens_sold: float, timestamp: datetime
    ) -> None:
        """Record a sale (reduces tracked purchases proportionally)"""
        pass

    @abstractmethod
    def get_total_bought(self, market_id: str, asset_id: str) -> float:
        """Get total tokens bought for a market/asset (accounting for sells)"""
        pass

    @abstractmethod
    def get_purchases(self, market_id: str, asset_id: str) -> List[PurchaseRecord]:
        """Get all purchase records for a market/asset"""
        pass

    @abstractmethod
    def clear_position(self, market_id: str, asset_id: str) -> None:
        """Clear all purchases for a market/asset (called when position is fully closed)"""
        pass


class SQLiteTrackingBackend(TrackingBackend):
    """
    SQLite-based purchase tracking.

    This is the default backend. It's simple, fast, and requires no external services.
    Data is persisted to a local SQLite file.
    """

    def __init__(self, db_path: Path = Path("copytrader_tracking.db")):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    tokens_bought REAL NOT NULL,
                    tokens_remaining REAL NOT NULL,
                    price_paid REAL NOT NULL,
                    usdc_spent REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    source_trader TEXT NOT NULL,
                    intent_id TEXT NOT NULL,
                    order_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Index for fast lookups
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_asset
                ON purchases(market_id, asset_id)
            """
            )

            conn.commit()

    def record_purchase(self, purchase: PurchaseRecord) -> None:
        """Record a purchase"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO purchases (
                    market_id, asset_id, tokens_bought, tokens_remaining,
                    price_paid, usdc_spent, timestamp, source_trader,
                    intent_id, order_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    purchase.market_id,
                    purchase.asset_id,
                    purchase.tokens_bought,
                    purchase.tokens_bought,  # Initially, all tokens remain
                    purchase.price_paid,
                    purchase.usdc_spent,
                    purchase.timestamp.isoformat(),
                    purchase.source_trader,
                    purchase.intent_id,
                    purchase.order_id,
                ),
            )
            conn.commit()

        logger.info(
            f"Recorded purchase: {purchase.tokens_bought:.2f} tokens "
            f"on {purchase.market_id[:16]}... for ${purchase.usdc_spent:.2f}"
        )

    def record_sale(
        self, market_id: str, asset_id: str, tokens_sold: float, timestamp: datetime
    ) -> None:
        """
        Record a sale by reducing tracked purchases proportionally.

        This implements FIFO (first-in-first-out) allocation.
        """
        with sqlite3.connect(self.db_path) as conn:
            # Get purchases with remaining tokens (FIFO order)
            cursor = conn.execute(
                """
                SELECT id, tokens_remaining
                FROM purchases
                WHERE market_id = ? AND asset_id = ? AND tokens_remaining > 0
                ORDER BY timestamp ASC
            """,
                (market_id, asset_id),
            )
            purchases = cursor.fetchall()

            remaining_to_sell = tokens_sold

            for purchase_id, tokens_remaining in purchases:
                if remaining_to_sell <= 0:
                    break

                # Allocate sale to this purchase
                allocated = min(remaining_to_sell, tokens_remaining)
                new_remaining = tokens_remaining - allocated

                conn.execute(
                    """
                    UPDATE purchases
                    SET tokens_remaining = ?
                    WHERE id = ?
                """,
                    (new_remaining, purchase_id),
                )

                remaining_to_sell -= allocated

                logger.debug(
                    f"Allocated {allocated:.2f} tokens sold to purchase {purchase_id}"
                )

            conn.commit()

            if remaining_to_sell > 0:
                logger.warning(
                    f"Oversold: {remaining_to_sell:.2f} tokens sold but no purchases to allocate to"
                )

        logger.info(
            f"Recorded sale: {tokens_sold:.2f} tokens on {market_id[:16]}..."
        )

    def get_total_bought(self, market_id: str, asset_id: str) -> float:
        """Get total tokens remaining (bought - sold)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT SUM(tokens_remaining)
                FROM purchases
                WHERE market_id = ? AND asset_id = ?
            """,
                (market_id, asset_id),
            )
            result = cursor.fetchone()[0]
            return float(result) if result else 0.0

    def get_purchases(self, market_id: str, asset_id: str) -> List[PurchaseRecord]:
        """Get all purchase records"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT market_id, asset_id, tokens_bought, price_paid, usdc_spent,
                       timestamp, source_trader, intent_id, order_id
                FROM purchases
                WHERE market_id = ? AND asset_id = ?
                ORDER BY timestamp ASC
            """,
                (market_id, asset_id),
            )

            purchases = []
            for row in cursor.fetchall():
                purchases.append(
                    PurchaseRecord(
                        market_id=row[0],
                        asset_id=row[1],
                        tokens_bought=row[2],
                        price_paid=row[3],
                        usdc_spent=row[4],
                        timestamp=datetime.fromisoformat(row[5]),
                        source_trader=row[6],
                        intent_id=row[7],
                        order_id=row[8],
                    )
                )

            return purchases

    def clear_position(self, market_id: str, asset_id: str) -> None:
        """Clear all purchases for a position (called when fully closed)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                DELETE FROM purchases
                WHERE market_id = ? AND asset_id = ?
            """,
                (market_id, asset_id),
            )
            deleted = cursor.rowcount
            conn.commit()

        logger.info(
            f"Cleared position: {deleted} purchase records on {market_id[:16]}..."
        )

    def get_stats(self) -> dict:
        """Get tracking statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total_purchases,
                    COUNT(DISTINCT market_id) as unique_markets,
                    SUM(tokens_remaining) as total_tokens_remaining,
                    SUM(usdc_spent) as total_usdc_spent
                FROM purchases
                WHERE tokens_remaining > 0
            """
            )
            row = cursor.fetchone()

            return {
                "total_purchases": row[0] or 0,
                "unique_markets": row[1] or 0,
                "total_tokens_remaining": row[2] or 0.0,
                "total_usdc_spent": row[3] or 0.0,
            }


class PurchaseTracker:
    """
    High-level interface for purchase tracking.

    This wraps the backend and provides convenience methods for
    the strategy layer.
    """

    def __init__(self, backend: Optional[TrackingBackend] = None):
        self.backend = backend or SQLiteTrackingBackend()

    def track_buy(
        self,
        market_id: str,
        asset_id: str,
        tokens_bought: float,
        price_paid: float,
        usdc_spent: float,
        source_trader: str,
        intent_id: str,
        order_id: Optional[str] = None,
    ) -> None:
        """Track a BUY order execution"""
        purchase = PurchaseRecord(
            market_id=market_id,
            asset_id=asset_id,
            tokens_bought=tokens_bought,
            price_paid=price_paid,
            usdc_spent=usdc_spent,
            timestamp=datetime.utcnow(),
            source_trader=source_trader,
            intent_id=intent_id,
            order_id=order_id,
        )
        self.backend.record_purchase(purchase)

    def track_sell(
        self, market_id: str, asset_id: str, tokens_sold: float
    ) -> None:
        """Track a SELL order execution"""
        self.backend.record_sale(market_id, asset_id, tokens_sold, datetime.utcnow())

    def get_tracked_position(self, market_id: str, asset_id: str) -> float:
        """Get total tracked tokens for a position"""
        return self.backend.get_total_bought(market_id, asset_id)

    def calculate_sell_amount(
        self, market_id: str, asset_id: str, trader_sell_percent: float
    ) -> float:
        """
        Calculate how many tokens to sell based on tracked purchases.

        Args:
            market_id: Market ID
            asset_id: Asset ID
            trader_sell_percent: Percentage of position trader is selling (0.0 - 1.0)

        Returns:
            Number of tokens to sell
        """
        tracked = self.get_tracked_position(market_id, asset_id)

        if tracked == 0:
            logger.warning(
                f"No tracked purchases for {market_id[:16]}... - "
                f"cannot calculate proportional sell"
            )
            return 0.0

        sell_amount = tracked * trader_sell_percent

        logger.info(
            f"Sell calculation: {tracked:.2f} tracked × {trader_sell_percent:.2%} = "
            f"{sell_amount:.2f} tokens"
        )

        return sell_amount

    def close_position(self, market_id: str, asset_id: str) -> None:
        """Clear tracking when position is fully closed"""
        self.backend.clear_position(market_id, asset_id)
