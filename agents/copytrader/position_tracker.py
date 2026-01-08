"""
Position tracking and PnL calculation.

Manages current positions and calculates realized/unrealized PnL.
Single source of truth for capital state.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from agents.copytrader.risk_kernel import Position, CapitalState
from agents.copytrader.storage import CopyTraderDB


@dataclass
class TradeRecord:
    """Record of an executed trade."""

    market_id: str
    side: str
    size: Decimal
    price: Decimal
    timestamp: datetime
    trader_id: str


class PositionTracker:
    """
    Tracks positions and calculates PnL.

    Single source of truth for capital state required by risk kernel.
    """

    def __init__(self, db: CopyTraderDB, starting_capital: Decimal):
        """
        Initialize position tracker.

        Args:
            db: Database connection
            starting_capital: Initial capital ($1000 for v1)
        """
        self.db = db
        self.starting_capital = starting_capital

    def get_current_positions(self) -> List[Position]:
        """
        Get all current open positions.

        Returns:
            List of Position objects
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT market_id, side, size, entry_price, entry_timestamp, trader_id
                FROM positions
                ORDER BY entry_timestamp DESC
                """
            )

            positions = []
            for row in cursor.fetchall():
                # TODO: Get current price from Polymarket API
                # For now, use entry price (unrealized PnL = 0)
                entry_price = Decimal(str(row[3]))
                size = Decimal(str(row[2]))

                positions.append(
                    Position(
                        market_id=row[0],
                        side=row[1],
                        size=size,
                        entry_price=entry_price,
                        current_price=entry_price,  # TODO: Real-time price
                        unrealized_pnl=Decimal("0"),  # TODO: Calculate from current price
                    )
                )

            return positions

    def calculate_pnl(self) -> CapitalState:
        """
        Calculate current capital state for risk kernel.

        Returns:
            CapitalState with current PnL
        """
        # Get today's start timestamp
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get total realized PnL
            cursor.execute(
                """
                SELECT COALESCE(SUM(pnl), 0)
                FROM trade_history
                WHERE pnl IS NOT NULL
                """
            )
            total_realized_pnl = Decimal(str(cursor.fetchone()[0]))

            # Get today's realized PnL
            cursor.execute(
                """
                SELECT COALESCE(SUM(pnl), 0)
                FROM trade_history
                WHERE pnl IS NOT NULL AND timestamp >= ?
                """,
                (today.isoformat(),),
            )
            daily_realized_pnl = Decimal(str(cursor.fetchone()[0]))

            # TODO: Add unrealized PnL from open positions
            # For now, only count realized PnL
            unrealized_pnl = Decimal("0")

            total_pnl = total_realized_pnl + unrealized_pnl
            daily_pnl = daily_realized_pnl  # TODO: Add unrealized change today

            current_capital = self.starting_capital + total_pnl

            total_pnl_pct = (
                (total_pnl / self.starting_capital) * Decimal("100")
                if self.starting_capital > 0
                else Decimal("0")
            )
            daily_pnl_pct = (
                (daily_pnl / self.starting_capital) * Decimal("100")
                if self.starting_capital > 0
                else Decimal("0")
            )

            return CapitalState(
                starting_capital=self.starting_capital,
                current_capital=current_capital,
                daily_pnl=daily_pnl,
                total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct,
                daily_pnl_pct=daily_pnl_pct,
            )

    def record_trade(
        self,
        trade: TradeRecord,
        execution_status: str,
        execution_detail: Optional[str] = None,
        pnl: Optional[Decimal] = None,
    ) -> int:
        """
        Record a trade execution.

        Args:
            trade: Trade record
            execution_status: 'success' or 'failed'
            execution_detail: Additional details
            pnl: Realized PnL (for closing trades)

        Returns:
            Trade history ID
        """
        pnl_pct = None
        if pnl is not None and trade.size > 0:
            pnl_pct = (pnl / trade.size) * Decimal("100")

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trade_history (
                    market_id, side, size, price, timestamp, trader_id,
                    execution_status, execution_detail, pnl, pnl_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.market_id,
                    trade.side,
                    float(trade.size),
                    float(trade.price),
                    trade.timestamp.isoformat(),
                    trade.trader_id,
                    execution_status,
                    execution_detail,
                    float(pnl) if pnl else None,
                    float(pnl_pct) if pnl_pct else None,
                ),
            )
            trade_id = cursor.lastrowid

            # Update or create position if trade succeeded
            if execution_status == "success":
                self._update_position(conn, trade)

            return trade_id

    def _update_position(self, conn, trade: TradeRecord):
        """Update position after successful trade. Uses existing connection to avoid locking."""
        cursor = conn.cursor()

        # Check if position exists
        cursor.execute(
            """
            SELECT size, entry_price
            FROM positions
            WHERE market_id = ? AND side = ?
            """,
            (trade.market_id, trade.side),
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing position (average price)
            old_size = Decimal(str(existing[0]))
            old_price = Decimal(str(existing[1]))

            new_size = old_size + trade.size
            new_avg_price = (
                (old_size * old_price + trade.size * trade.price) / new_size
            )

            cursor.execute(
                """
                UPDATE positions
                SET size = ?, entry_price = ?
                WHERE market_id = ? AND side = ?
                """,
                (float(new_size), float(new_avg_price), trade.market_id, trade.side),
            )
        else:
            # Create new position
            cursor.execute(
                """
                INSERT INTO positions (
                    market_id, side, size, entry_price, entry_timestamp, trader_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.market_id,
                    trade.side,
                    float(trade.size),
                    float(trade.price),
                    trade.timestamp.isoformat(),
                    trade.trader_id,
                ),
            )

    def close_position(self, market_id: str, side: str, exit_price: Decimal) -> Decimal:
        """
        Close a position and calculate realized PnL.

        Args:
            market_id: Market to close
            side: Position side
            exit_price: Exit price

        Returns:
            Realized PnL
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT size, entry_price
                FROM positions
                WHERE market_id = ? AND side = ?
                """,
                (market_id, side),
            )
            row = cursor.fetchone()

            if not row:
                return Decimal("0")

            size = Decimal(str(row[0]))
            entry_price = Decimal(str(row[1]))

            # Calculate PnL: (exit_price - entry_price) * size
            # For "sell" positions, invert: (entry_price - exit_price) * size
            if side == "buy":
                pnl = (exit_price - entry_price) * size
            else:
                pnl = (entry_price - exit_price) * size

            # Delete position
            cursor.execute(
                """
                DELETE FROM positions
                WHERE market_id = ? AND side = ?
                """,
                (market_id, side),
            )

            return pnl
