"""
Tests for Position Manager and Exit Strategies.

Tests:
- Position tracking
- Exit strategy logic
- Performance metrics
- Persistence
"""

import unittest
import os
import sys
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/home/tony/Dev/agents')

from agents.application.position_manager import Position, PositionManager
from agents.application.exit_strategies import (
    TakeProfitStrategy,
    StopLossStrategy,
    TimeBasedStrategy,
    TrailingStopStrategy,
    AggressiveExitStrategy,
    ConservativeExitStrategy
)


class TestPosition(unittest.TestCase):
    """Test Position class."""

    def test_position_creation(self):
        """Test creating a position."""
        pos = Position(
            market_id="test_1",
            market_question="Test market?",
            outcome="YES",
            entry_price=0.50,
            quantity=100,
            entry_timestamp=datetime.now().isoformat()
        )

        self.assertEqual(pos.market_id, "test_1")
        self.assertEqual(pos.entry_price, 0.50)
        self.assertEqual(pos.quantity, 100)
        self.assertFalse(pos.is_closed())

    def test_position_update_profit(self):
        """Test position update with profit."""
        pos = Position(
            market_id="test_1",
            market_question="Test market?",
            outcome="YES",
            entry_price=0.50,
            quantity=100,
            entry_timestamp=datetime.now().isoformat()
        )

        pos.update_price(0.60)

        self.assertEqual(pos.current_price, 0.60)
        self.assertAlmostEqual(pos.unrealized_pnl, 10.0, places=2)  # (0.60 - 0.50) * 100
        self.assertAlmostEqual(pos.unrealized_pnl_pct, 20.0, places=1)  # 20% profit

    def test_position_update_loss(self):
        """Test position update with loss."""
        pos = Position(
            market_id="test_1",
            market_question="Test market?",
            outcome="YES",
            entry_price=0.50,
            quantity=100,
            entry_timestamp=datetime.now().isoformat()
        )

        pos.update_price(0.40)

        self.assertEqual(pos.current_price, 0.40)
        self.assertAlmostEqual(pos.unrealized_pnl, -10.0, places=2)  # (0.40 - 0.50) * 100
        self.assertAlmostEqual(pos.unrealized_pnl_pct, -20.0, places=1)  # -20% loss

    def test_position_close(self):
        """Test closing a position."""
        pos = Position(
            market_id="test_1",
            market_question="Test market?",
            outcome="YES",
            entry_price=0.50,
            quantity=100,
            entry_timestamp=datetime.now().isoformat()
        )

        pos.close_position(0.60, "Take Profit")

        self.assertTrue(pos.is_closed())
        self.assertEqual(pos.exit_price, 0.60)
        self.assertEqual(pos.exit_reason, "Take Profit")
        self.assertAlmostEqual(pos.realized_pnl, 10.0, places=2)
        self.assertAlmostEqual(pos.realized_pnl_pct, 20.0, places=1)


class TestExitStrategies(unittest.TestCase):
    """Test exit strategy logic."""

    def setUp(self):
        """Create test position."""
        self.position = Position(
            market_id="test_1",
            market_question="Test market?",
            outcome="YES",
            entry_price=0.50,
            quantity=100,
            entry_timestamp=datetime.now().isoformat()
        )

    def test_take_profit_triggered(self):
        """Test take profit strategy triggers."""
        strategy = TakeProfitStrategy(profit_target_pct=20.0)

        # Should not trigger at +10%
        should_exit, reason = strategy.should_exit(self.position, 0.55)
        self.assertFalse(should_exit)

        # Should trigger at +20%
        should_exit, reason = strategy.should_exit(self.position, 0.60)
        self.assertTrue(should_exit)
        self.assertIn("Take Profit", reason)

    def test_stop_loss_triggered(self):
        """Test stop loss strategy triggers."""
        strategy = StopLossStrategy(max_loss_pct=10.0)

        # Should not trigger at -5%
        should_exit, reason = strategy.should_exit(self.position, 0.475)
        self.assertFalse(should_exit)

        # Should trigger at -10%
        should_exit, reason = strategy.should_exit(self.position, 0.45)
        self.assertTrue(should_exit)
        self.assertIn("Stop Loss", reason)

    def test_time_based_triggered(self):
        """Test time-based strategy triggers."""
        strategy = TimeBasedStrategy(max_hold_hours=24)

        # Position just opened - should not trigger
        should_exit, reason = strategy.should_exit(self.position, 0.50)
        self.assertFalse(should_exit)

        # Create old position (25 hours ago)
        old_position = Position(
            market_id="test_1",
            market_question="Test market?",
            outcome="YES",
            entry_price=0.50,
            quantity=100,
            entry_timestamp=(datetime.now() - timedelta(hours=25)).isoformat()
        )

        should_exit, reason = strategy.should_exit(old_position, 0.50)
        self.assertTrue(should_exit)
        self.assertIn("Time Limit", reason)

    def test_trailing_stop_triggered(self):
        """Test trailing stop strategy triggers."""
        strategy = TrailingStopStrategy(trail_pct=5.0)

        # Update to profit (highest = 0.60)
        self.position.update_price(0.60)

        # Drop 3% from peak - should not trigger
        should_exit, reason = strategy.should_exit(self.position, 0.582)
        self.assertFalse(should_exit)

        # Drop 5% from peak - should trigger
        should_exit, reason = strategy.should_exit(self.position, 0.57)
        self.assertTrue(should_exit)
        self.assertIn("Trailing Stop", reason)

    def test_trailing_stop_no_profit(self):
        """Test trailing stop doesn't trigger without profit."""
        strategy = TrailingStopStrategy(trail_pct=5.0)

        # Position at break-even
        should_exit, reason = strategy.should_exit(self.position, 0.50)
        self.assertFalse(should_exit)

        # Position at loss
        should_exit, reason = strategy.should_exit(self.position, 0.45)
        self.assertFalse(should_exit)


class TestPositionManager(unittest.TestCase):
    """Test PositionManager class."""

    def setUp(self):
        """Create temporary storage for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.temp_dir, "positions.json")

        # Mock environment variables
        os.environ['TAKE_PROFIT_PCT'] = '20.0'
        os.environ['STOP_LOSS_PCT'] = '10.0'
        os.environ['MAX_HOLD_HOURS'] = '72'
        os.environ['TRAILING_STOP_PCT'] = '5.0'
        os.environ['ENABLE_AUTO_EXIT'] = 'false'  # Disable auto-exit for tests

        self.manager = PositionManager(storage_path=self.storage_path)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_open_position(self):
        """Test opening a position."""
        pos = self.manager.open_position(
            market_id="market_1",
            market_question="Will Bitcoin reach $100k?",
            outcome="YES",
            entry_price=0.65,
            quantity=100
        )

        self.assertEqual(len(self.manager.get_open_positions()), 1)
        self.assertEqual(pos.market_id, "market_1")
        self.assertEqual(pos.entry_price, 0.65)

    def test_update_position_take_profit(self):
        """Test position update triggers take profit."""
        self.manager.open_position(
            market_id="market_1",
            market_question="Will Bitcoin reach $100k?",
            outcome="YES",
            entry_price=0.50,
            quantity=100
        )

        # Update to +20% profit (should trigger)
        exit_signal = self.manager.update_position("market_1", 0.60)

        self.assertIsNotNone(exit_signal)
        self.assertTrue(exit_signal[0])
        self.assertIn("Take Profit", exit_signal[1])

    def test_update_position_stop_loss(self):
        """Test position update triggers stop loss."""
        self.manager.open_position(
            market_id="market_1",
            market_question="Will Bitcoin reach $100k?",
            outcome="YES",
            entry_price=0.50,
            quantity=100
        )

        # Update to -10% loss (should trigger)
        exit_signal = self.manager.update_position("market_1", 0.45)

        self.assertIsNotNone(exit_signal)
        self.assertTrue(exit_signal[0])
        self.assertIn("Stop Loss", exit_signal[1])

    def test_execute_exit(self):
        """Test executing an exit."""
        pos = self.manager.open_position(
            market_id="market_1",
            market_question="Will Bitcoin reach $100k?",
            outcome="YES",
            entry_price=0.50,
            quantity=100
        )

        success = self.manager.execute_exit(pos, 0.60, "Take Profit")

        self.assertTrue(success)
        self.assertEqual(len(self.manager.get_open_positions()), 0)
        self.assertEqual(len(self.manager.get_closed_positions()), 1)

        closed = self.manager.get_closed_positions()[0]
        self.assertTrue(closed.is_closed())
        self.assertEqual(closed.exit_price, 0.60)
        self.assertEqual(closed.exit_reason, "Take Profit")

    def test_performance_metrics_empty(self):
        """Test performance metrics with no closed positions."""
        metrics = self.manager.get_performance_metrics()

        self.assertEqual(metrics['total_positions'], 0)
        self.assertEqual(metrics['win_rate'], 0.0)
        self.assertEqual(metrics['total_pnl'], 0.0)

    def test_performance_metrics_with_trades(self):
        """Test performance metrics with closed positions."""
        # Open and close 3 positions
        for i in range(3):
            pos = self.manager.open_position(
                market_id=f"market_{i}",
                market_question=f"Test market {i}?",
                outcome="YES",
                entry_price=0.50,
                quantity=100
            )

            # 2 winners, 1 loser
            exit_price = 0.60 if i < 2 else 0.45
            self.manager.execute_exit(pos, exit_price, "Test exit")

        metrics = self.manager.get_performance_metrics()

        self.assertEqual(metrics['total_positions'], 3)
        self.assertEqual(metrics['winning_positions'], 2)
        self.assertEqual(metrics['losing_positions'], 1)
        self.assertAlmostEqual(metrics['win_rate'], 66.67, places=1)
        self.assertAlmostEqual(metrics['total_pnl'], 15.0, places=1)  # (10 + 10 - 5)

    def test_persistence(self):
        """Test saving and loading positions."""
        # Open position
        self.manager.open_position(
            market_id="market_1",
            market_question="Test market?",
            outcome="YES",
            entry_price=0.50,
            quantity=100
        )

        # Create new manager instance (should load from disk)
        new_manager = PositionManager(storage_path=self.storage_path)

        self.assertEqual(len(new_manager.get_open_positions()), 1)
        pos = new_manager.get_position("market_1")
        self.assertIsNotNone(pos)
        self.assertEqual(pos.entry_price, 0.50)


class TestExitStrategyPresets(unittest.TestCase):
    """Test preset exit strategy configurations."""

    def setUp(self):
        """Create test position."""
        self.position = Position(
            market_id="test_1",
            market_question="Test market?",
            outcome="YES",
            entry_price=0.50,
            quantity=100,
            entry_timestamp=datetime.now().isoformat()
        )

    def test_aggressive_strategy(self):
        """Test aggressive strategy preset."""
        strategy = AggressiveExitStrategy()

        # Should trigger at +10% profit
        should_exit, reason = strategy.should_exit(self.position, 0.55)
        self.assertTrue(should_exit)
        self.assertIn("Take Profit", reason)

    def test_conservative_strategy(self):
        """Test conservative strategy preset."""
        strategy = ConservativeExitStrategy()

        # Should NOT trigger at +10% profit (target is +30%)
        should_exit, reason = strategy.should_exit(self.position, 0.55)
        self.assertFalse(should_exit)

        # Should trigger at +30% profit
        should_exit, reason = strategy.should_exit(self.position, 0.65)
        self.assertTrue(should_exit)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], exit=False, verbosity=2)


if __name__ == "__main__":
    run_tests()
