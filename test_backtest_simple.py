#!/usr/bin/env python3
"""
Simple backtest test to verify the framework works
"""
import sys
sys.path.insert(0, '/home/tony/Dev/agents')

from agents.backtesting.backtest_runner import BacktestRunner, BacktestConfig
from datetime import datetime

# Create config with relaxed mean-reversion threshold
config = BacktestConfig(
    start_date=datetime(2025, 10, 1),
    end_date=datetime(2026, 1, 1),
    strategy='mean-reversion',
    exit_strategy='take-profit-20',
    initial_capital=1000.0,
    min_confidence=0.40,  # Lower threshold
    max_position_size=50.0
)

# Monkey-patch the mean-reversion strategy to use lower threshold
def _mean_reversion_strategy_relaxed(self, snapshot):
    """Mean reversion with lower threshold (0.08 instead of 0.2)"""
    mid_price = snapshot['mid_price']
    deviation = abs(mid_price - 0.5)

    if deviation > 0.08:  # LOWERED from 0.2
        confidence = 0.5 + deviation
        return True, confidence

    return False, 0.0

# Run backtest
runner = BacktestRunner(config)

# Patch the strategy
runner._mean_reversion_strategy = lambda s: _mean_reversion_strategy_relaxed(runner, s)

# Run
print("\n" + "=" * 80)
print("RUNNING BACKTEST WITH RELAXED MEAN-REVERSION THRESHOLD")
print("=" * 80 + "\n")

result = runner.run()

print("\n" + "=" * 80)
print("RESULTS")
print("=" * 80)
print(f"Trades: {result['total_trades']}")
print(f"Win Rate: {result['win_rate']:.1f}%")
print(f"Total PnL: ${result['total_pnl']:.2f}")
print(f"Total Return: {result['total_return_pct']:.2f}%")
print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {result['max_drawdown_pct']:.2f}%")
print(f"\nReport: {result['report_path']}")
