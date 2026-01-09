"""
Exit Strategies - Logic for different position exit conditions.

Implements multiple exit strategies:
- Take Profit: Exit at profit target
- Stop Loss: Exit at loss limit
- Time-based: Exit after hold period
- Trailing Stop: Lock in profits
- Target Price: Exit at specific price
"""

from abc import ABC, abstractmethod
from typing import Tuple
from datetime import datetime


class ExitStrategy(ABC):
    """Base class for exit strategies."""

    @abstractmethod
    def should_exit(self, position, current_price: float) -> Tuple[bool, str]:
        """
        Check if position should exit.

        Args:
            position: Position object
            current_price: Current market price

        Returns:
            (should_exit, reason)
        """
        pass


class TakeProfitStrategy(ExitStrategy):
    """Exit when profit reaches target percentage."""

    def __init__(self, profit_target_pct: float):
        """
        Initialize take profit strategy.

        Args:
            profit_target_pct: Profit target as percentage (e.g., 20.0 for +20%)
        """
        self.profit_target_pct = profit_target_pct

    def should_exit(self, position, current_price: float) -> Tuple[bool, str]:
        """Check if profit target reached."""
        profit_pct = ((current_price - position.entry_price) / position.entry_price) * 100

        # Use slight tolerance for floating point comparison
        if profit_pct >= (self.profit_target_pct - 0.01):
            return (True, f"Take Profit: +{profit_pct:.1f}% (target: +{self.profit_target_pct}%)")

        return (False, "")


class StopLossStrategy(ExitStrategy):
    """Exit when loss reaches maximum acceptable percentage."""

    def __init__(self, max_loss_pct: float):
        """
        Initialize stop loss strategy.

        Args:
            max_loss_pct: Maximum acceptable loss as percentage (e.g., 10.0 for -10%)
        """
        self.max_loss_pct = max_loss_pct

    def should_exit(self, position, current_price: float) -> Tuple[bool, str]:
        """Check if stop loss triggered."""
        loss_pct = ((current_price - position.entry_price) / position.entry_price) * 100

        # Use slight tolerance for floating point comparison
        if loss_pct <= (-self.max_loss_pct + 0.01):
            return (True, f"Stop Loss: {loss_pct:.1f}% (max: -{self.max_loss_pct}%)")

        return (False, "")


class TimeBasedStrategy(ExitStrategy):
    """Exit after holding for maximum time period."""

    def __init__(self, max_hold_hours: float):
        """
        Initialize time-based strategy.

        Args:
            max_hold_hours: Maximum hold time in hours
        """
        self.max_hold_hours = max_hold_hours

    def should_exit(self, position, current_price: float) -> Tuple[bool, str]:
        """Check if maximum hold time exceeded."""
        entry_dt = datetime.fromisoformat(position.entry_timestamp)
        hold_hours = (datetime.now() - entry_dt).total_seconds() / 3600

        if hold_hours >= self.max_hold_hours:
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            return (True, f"Time Limit: {hold_hours:.1f}h (max: {self.max_hold_hours}h) | PnL: {pnl_pct:+.1f}%")

        return (False, "")


class TrailingStopStrategy(ExitStrategy):
    """Exit when price drops by trailing percentage from highest point."""

    def __init__(self, trail_pct: float):
        """
        Initialize trailing stop strategy.

        Args:
            trail_pct: Trailing stop percentage (e.g., 5.0 for -5% from peak)
        """
        self.trail_pct = trail_pct

    def should_exit(self, position, current_price: float) -> Tuple[bool, str]:
        """Check if trailing stop triggered."""
        # Only trigger if we're in profit
        if position.highest_price <= position.entry_price:
            return (False, "")

        # Calculate drop from highest price
        drop_from_peak_pct = ((current_price - position.highest_price) / position.highest_price) * 100

        if drop_from_peak_pct <= -self.trail_pct:
            profit_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            return (True, f"Trailing Stop: {drop_from_peak_pct:.1f}% from peak (trail: -{self.trail_pct}%) | PnL: {profit_pct:+.1f}%")

        return (False, "")


class TargetPriceStrategy(ExitStrategy):
    """Exit when specific target price is reached."""

    def __init__(self, target_price: float):
        """
        Initialize target price strategy.

        Args:
            target_price: Target exit price
        """
        self.target_price = target_price

    def should_exit(self, position, current_price: float) -> Tuple[bool, str]:
        """Check if target price reached."""
        # Exit if current price >= target for long, or <= target for short
        if current_price >= self.target_price:
            profit_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            return (True, f"Target Price: ${current_price:.4f} (target: ${self.target_price:.4f}) | PnL: {profit_pct:+.1f}%")

        return (False, "")


class CombinedExitStrategy(ExitStrategy):
    """Combine multiple exit strategies with OR logic."""

    def __init__(self, strategies: list):
        """
        Initialize combined strategy.

        Args:
            strategies: List of ExitStrategy objects
        """
        self.strategies = strategies

    def should_exit(self, position, current_price: float) -> Tuple[bool, str]:
        """Check all strategies, exit on first trigger."""
        for strategy in self.strategies:
            should_exit, reason = strategy.should_exit(position, current_price)
            if should_exit:
                return (True, reason)

        return (False, "")


# Predefined strategy configurations
class AggressiveExitStrategy(CombinedExitStrategy):
    """Aggressive exits: quick profits, tight stops."""

    def __init__(self):
        super().__init__([
            TakeProfitStrategy(profit_target_pct=10.0),  # Exit at +10%
            StopLossStrategy(max_loss_pct=5.0),          # Exit at -5%
            TimeBasedStrategy(max_hold_hours=24),        # Exit after 24h
            TrailingStopStrategy(trail_pct=3.0)          # Trail by 3%
        ])


class ConservativeExitStrategy(CombinedExitStrategy):
    """Conservative exits: larger targets, wider stops."""

    def __init__(self):
        super().__init__([
            TakeProfitStrategy(profit_target_pct=30.0),  # Exit at +30%
            StopLossStrategy(max_loss_pct=15.0),         # Exit at -15%
            TimeBasedStrategy(max_hold_hours=168),       # Exit after 7 days
            TrailingStopStrategy(trail_pct=10.0)         # Trail by 10%
        ])


class BalancedExitStrategy(CombinedExitStrategy):
    """Balanced exits: moderate targets and stops."""

    def __init__(self):
        super().__init__([
            TakeProfitStrategy(profit_target_pct=20.0),  # Exit at +20%
            StopLossStrategy(max_loss_pct=10.0),         # Exit at -10%
            TimeBasedStrategy(max_hold_hours=72),        # Exit after 3 days
            TrailingStopStrategy(trail_pct=5.0)          # Trail by 5%
        ])


# Factory function
def create_exit_strategy(strategy_type: str = "balanced") -> CombinedExitStrategy:
    """
    Create exit strategy by type.

    Args:
        strategy_type: "aggressive", "conservative", or "balanced"

    Returns:
        CombinedExitStrategy object
    """
    strategies = {
        'aggressive': AggressiveExitStrategy,
        'conservative': ConservativeExitStrategy,
        'balanced': BalancedExitStrategy
    }

    strategy_class = strategies.get(strategy_type.lower(), BalancedExitStrategy)
    return strategy_class()


if __name__ == "__main__":
    # Demo different strategies
    from dataclasses import dataclass
    from datetime import datetime, timedelta

    @dataclass
    class MockPosition:
        entry_price: float = 0.50
        highest_price: float = 0.50
        entry_timestamp: str = datetime.now().isoformat()

    position = MockPosition()

    print("Testing Exit Strategies")
    print("=" * 60)

    # Test prices
    test_prices = [0.45, 0.50, 0.55, 0.60, 0.65, 0.58]

    strategies = {
        'Aggressive': AggressiveExitStrategy(),
        'Balanced': BalancedExitStrategy(),
        'Conservative': ConservativeExitStrategy()
    }

    for name, strategy in strategies.items():
        print(f"\n{name} Strategy:")
        for price in test_prices:
            position.highest_price = max(position.highest_price, price)
            should_exit, reason = strategy.should_exit(position, price)
            status = "✅ EXIT" if should_exit else "⏸️ HOLD"
            print(f"  Price ${price:.2f}: {status} - {reason if reason else 'No exit signal'}")
