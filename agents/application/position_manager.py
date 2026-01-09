"""
Position Manager - Real-time tracking and exit strategy execution.

Tracks all open positions and executes exits based on:
- Take profit targets
- Stop loss limits
- Time-based exits
- Trailing stops
- Target prices

Prevents massive losses by cutting losers early and taking winners!
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Add project root to path
sys.path.insert(0, '/home/tony/Dev/agents')

from agents.application.exit_strategies import (
    ExitStrategy,
    TakeProfitStrategy,
    StopLossStrategy,
    TimeBasedStrategy,
    TrailingStopStrategy,
    TargetPriceStrategy
)


@dataclass
class Position:
    """Represents an open trading position."""
    market_id: str
    market_question: str
    outcome: str  # "YES" or "NO"
    entry_price: float
    quantity: float
    entry_timestamp: str
    order_id: Optional[str] = None

    # Dynamic fields updated during tracking
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    highest_price: float = 0.0  # For trailing stop
    hold_duration_hours: float = 0.0
    last_updated: Optional[str] = None

    # Exit tracking
    exit_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None

    def __post_init__(self):
        """Initialize calculated fields."""
        self.highest_price = self.entry_price
        self.current_price = self.entry_price
        self.last_updated = datetime.now().isoformat()

    def update_price(self, new_price: float):
        """Update current price and calculate PnL."""
        self.current_price = new_price
        self.last_updated = datetime.now().isoformat()

        # Update highest price for trailing stop
        if new_price > self.highest_price:
            self.highest_price = new_price

        # Calculate unrealized PnL
        price_diff = new_price - self.entry_price
        self.unrealized_pnl = price_diff * self.quantity

        if self.entry_price > 0:
            self.unrealized_pnl_pct = (price_diff / self.entry_price) * 100

        # Calculate hold duration
        entry_dt = datetime.fromisoformat(self.entry_timestamp)
        self.hold_duration_hours = (datetime.now() - entry_dt).total_seconds() / 3600

    def close_position(self, exit_price: float, reason: str):
        """Mark position as closed with exit details."""
        self.exit_price = exit_price
        self.exit_timestamp = datetime.now().isoformat()
        self.exit_reason = reason

        # Calculate realized PnL
        price_diff = exit_price - self.entry_price
        self.realized_pnl = price_diff * self.quantity

        if self.entry_price > 0:
            self.realized_pnl_pct = (price_diff / self.entry_price) * 100

    def is_closed(self) -> bool:
        """Check if position is closed."""
        return self.exit_price is not None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class PositionManager:
    """
    Manages all open positions with real-time tracking and exit execution.

    Features:
    - Real-time position tracking
    - Multiple exit strategies
    - Automatic exit execution
    - Performance metrics
    - Persistent storage
    """

    def __init__(self, storage_path: str = "data/positions.json"):
        """Initialize position manager."""
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Load configuration from environment
        self.config = {
            'take_profit_pct': float(os.getenv('TAKE_PROFIT_PCT', '20.0')),
            'stop_loss_pct': float(os.getenv('STOP_LOSS_PCT', '10.0')),
            'max_hold_hours': float(os.getenv('MAX_HOLD_HOURS', '72')),
            'trailing_stop_pct': float(os.getenv('TRAILING_STOP_PCT', '5.0')),
            'enable_auto_exit': os.getenv('ENABLE_AUTO_EXIT', 'true').lower() == 'true'
        }

        # Initialize exit strategies
        self.strategies: List[ExitStrategy] = [
            TakeProfitStrategy(self.config['take_profit_pct']),
            StopLossStrategy(self.config['stop_loss_pct']),
            TimeBasedStrategy(self.config['max_hold_hours']),
            TrailingStopStrategy(self.config['trailing_stop_pct'])
        ]

        # Load existing positions
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Position] = []
        self._load_positions()

        print(f"✅ PositionManager initialized")
        print(f"   Take Profit: +{self.config['take_profit_pct']}%")
        print(f"   Stop Loss: -{self.config['stop_loss_pct']}%")
        print(f"   Max Hold: {self.config['max_hold_hours']}h")
        print(f"   Trailing Stop: {self.config['trailing_stop_pct']}%")
        print(f"   Auto Exit: {self.config['enable_auto_exit']}")

    def open_position(self, market_id: str, market_question: str, outcome: str,
                     entry_price: float, quantity: float, order_id: Optional[str] = None) -> Position:
        """
        Record a new open position.

        Args:
            market_id: Market identifier
            market_question: Market question text
            outcome: "YES" or "NO"
            entry_price: Price at entry
            quantity: Number of shares
            order_id: Optional order ID from exchange

        Returns:
            Position object
        """
        position = Position(
            market_id=market_id,
            market_question=market_question,
            outcome=outcome,
            entry_price=entry_price,
            quantity=quantity,
            entry_timestamp=datetime.now().isoformat(),
            order_id=order_id
        )

        self.positions[market_id] = position
        self._save_positions()

        print(f"\n📈 POSITION OPENED")
        print(f"   Market: {market_question[:60]}...")
        print(f"   Outcome: {outcome}")
        print(f"   Entry: ${entry_price:.4f} x {quantity} shares")
        print(f"   Cost: ${entry_price * quantity:.2f}")

        return position

    def update_position(self, market_id: str, current_price: float) -> Optional[Tuple[bool, str]]:
        """
        Update position with current price and check exit conditions.

        Args:
            market_id: Market identifier
            current_price: Current market price

        Returns:
            (should_exit, reason) if exit triggered, None otherwise
        """
        if market_id not in self.positions:
            return None

        position = self.positions[market_id]

        # CRITICAL: Update price BEFORE checking exit conditions
        # This ensures highest_price is set for trailing stop
        position.update_price(current_price)

        # Check all exit strategies
        exit_decision = self.should_exit(position, current_price)

        if exit_decision[0]:
            print(f"\n🚨 EXIT SIGNAL TRIGGERED")
            print(f"   Market: {position.market_question[:60]}...")
            print(f"   Reason: {exit_decision[1]}")
            print(f"   PnL: ${position.unrealized_pnl:.2f} ({position.unrealized_pnl_pct:+.2f}%)")

            if self.config['enable_auto_exit']:
                self.execute_exit(position, current_price, exit_decision[1])

        self._save_positions()
        return exit_decision if exit_decision[0] else None

    def should_exit(self, position: Position, current_price: float) -> Tuple[bool, str]:
        """
        Check if position should exit based on all strategies.

        Args:
            position: Position to check
            current_price: Current market price

        Returns:
            (should_exit, reason)
        """
        for strategy in self.strategies:
            should_exit, reason = strategy.should_exit(position, current_price)
            if should_exit:
                return (True, reason)

        return (False, "")

    def execute_exit(self, position: Position, exit_price: float, reason: str) -> bool:
        """
        Execute exit for position (place sell order).

        Args:
            position: Position to exit
            exit_price: Exit price
            reason: Exit reason

        Returns:
            True if successful
        """
        try:
            # TODO: Integrate with Polymarket API to place sell order
            # For now, just mark as closed

            position.close_position(exit_price, reason)

            # Move to closed positions
            self.closed_positions.append(position)
            del self.positions[position.market_id]

            self._save_positions()

            print(f"\n✅ POSITION CLOSED")
            print(f"   Market: {position.market_question[:60]}...")
            print(f"   Entry: ${position.entry_price:.4f}")
            print(f"   Exit: ${exit_price:.4f}")
            print(f"   PnL: ${position.realized_pnl:.2f} ({position.realized_pnl_pct:+.2f}%)")
            print(f"   Reason: {reason}")
            print(f"   Duration: {position.hold_duration_hours:.1f}h")

            return True

        except Exception as e:
            print(f"❌ Failed to execute exit: {e}")
            return False

    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return list(self.positions.values())

    def get_closed_positions(self) -> List[Position]:
        """Get all closed positions."""
        return self.closed_positions

    def get_position(self, market_id: str) -> Optional[Position]:
        """Get specific position by market ID."""
        return self.positions.get(market_id)

    def get_performance_metrics(self) -> dict:
        """
        Calculate performance metrics across all closed positions.

        Returns:
            Dictionary with performance statistics
        """
        if not self.closed_positions:
            return {
                'total_positions': 0,
                'winning_positions': 0,
                'losing_positions': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
                'total_pnl': 0.0,
                'avg_pnl_pct': 0.0,
                'best_trade': 0.0,
                'worst_trade': 0.0,
                'avg_hold_hours': 0.0
            }

        winners = [p for p in self.closed_positions if p.realized_pnl > 0]
        losers = [p for p in self.closed_positions if p.realized_pnl <= 0]

        total_pnl = sum(p.realized_pnl for p in self.closed_positions)
        avg_profit = sum(p.realized_pnl for p in winners) / len(winners) if winners else 0
        avg_loss = sum(p.realized_pnl for p in losers) / len(losers) if losers else 0

        pnl_pcts = [p.realized_pnl_pct for p in self.closed_positions]
        avg_pnl_pct = sum(pnl_pcts) / len(pnl_pcts) if pnl_pcts else 0

        hold_durations = [p.hold_duration_hours for p in self.closed_positions]
        avg_hold = sum(hold_durations) / len(hold_durations) if hold_durations else 0

        return {
            'total_positions': len(self.closed_positions),
            'winning_positions': len(winners),
            'losing_positions': len(losers),
            'win_rate': (len(winners) / len(self.closed_positions) * 100) if self.closed_positions else 0,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'total_pnl': total_pnl,
            'avg_pnl_pct': avg_pnl_pct,
            'best_trade': max(p.realized_pnl for p in self.closed_positions),
            'worst_trade': min(p.realized_pnl for p in self.closed_positions),
            'avg_hold_hours': avg_hold
        }

    def print_status(self):
        """Print current status of all positions."""
        print(f"\n{'='*80}")
        print(f"POSITION MANAGER STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")

        # Open positions
        print(f"\n📊 OPEN POSITIONS ({len(self.positions)})")
        if self.positions:
            for pos in self.positions.values():
                print(f"\n   Market: {pos.market_question[:60]}...")
                print(f"   Outcome: {pos.outcome} | Entry: ${pos.entry_price:.4f} | Current: ${pos.current_price:.4f}")
                print(f"   PnL: ${pos.unrealized_pnl:+.2f} ({pos.unrealized_pnl_pct:+.2f}%) | Hold: {pos.hold_duration_hours:.1f}h")
        else:
            print("   No open positions")

        # Performance metrics
        print(f"\n📈 PERFORMANCE METRICS")
        metrics = self.get_performance_metrics()
        print(f"   Total Closed: {metrics['total_positions']}")
        print(f"   Win Rate: {metrics['win_rate']:.1f}%")
        print(f"   Total PnL: ${metrics['total_pnl']:+.2f}")
        print(f"   Avg PnL: {metrics['avg_pnl_pct']:+.2f}%")
        print(f"   Best Trade: ${metrics['best_trade']:+.2f}")
        print(f"   Worst Trade: ${metrics['worst_trade']:+.2f}")
        print(f"   Avg Hold: {metrics['avg_hold_hours']:.1f}h")

        print(f"\n{'='*80}\n")

    def _save_positions(self):
        """Save positions to disk."""
        try:
            data = {
                'open_positions': [pos.to_dict() for pos in self.positions.values()],
                'closed_positions': [pos.to_dict() for pos in self.closed_positions],
                'last_updated': datetime.now().isoformat()
            }

            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            print(f"⚠️ Failed to save positions: {e}")

    def _load_positions(self):
        """Load positions from disk."""
        try:
            if not self.storage_path.exists():
                return

            with open(self.storage_path, 'r') as f:
                data = json.load(f)

            # Load open positions
            for pos_dict in data.get('open_positions', []):
                position = Position(**pos_dict)
                self.positions[position.market_id] = position

            # Load closed positions
            for pos_dict in data.get('closed_positions', []):
                position = Position(**pos_dict)
                self.closed_positions.append(position)

            print(f"📂 Loaded {len(self.positions)} open positions, {len(self.closed_positions)} closed positions")

        except Exception as e:
            print(f"⚠️ Failed to load positions: {e}")


# Convenience function for testing
def demo():
    """Demo position manager functionality."""
    manager = PositionManager()

    # Open test position
    pos = manager.open_position(
        market_id="test_market_1",
        market_question="Will Bitcoin reach $100k in 2024?",
        outcome="YES",
        entry_price=0.65,
        quantity=100
    )

    # Simulate price updates
    print("\n🔄 Simulating price changes...")

    prices = [0.70, 0.75, 0.80, 0.78, 0.76]  # Take profit at +20%
    for price in prices:
        print(f"\n   Price: ${price:.2f}")
        exit_signal = manager.update_position("test_market_1", price)
        time.sleep(1)

    manager.print_status()


if __name__ == "__main__":
    demo()
