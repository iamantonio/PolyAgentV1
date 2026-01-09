#!/usr/bin/env python3
"""
Run backtest on REAL Polymarket data
"""
import sys
import os
sys.path.insert(0, '/home/tony/Dev/agents')

from agents.backtesting.backtest_runner import BacktestRunner, BacktestConfig
from datetime import datetime

# Override data file to use real data
import agents.backtesting.backtest_runner as runner_module

# Monkey-patch to use real data
original_load = runner_module.BacktestRunner._load_historical_data

def load_real_data(self):
    import pandas as pd
    from pathlib import Path
    print("Loading REAL Polymarket data...")
    data_file = Path("data/backtest") / "real_polymarket_data.parquet"
    df = pd.read_parquet(data_file)

    # Convert string dates to datetime if needed
    if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Tags are already comma-separated strings, don't need to parse as JSON

    print(f"Loaded {len(df)} snapshots from REAL Polymarket data")
    return df

runner_module.BacktestRunner._load_historical_data = load_real_data

# Create config
config = BacktestConfig(
    start_date=datetime(2021, 1, 1),
    end_date=datetime(2023, 12, 31),
    strategy='ai-prediction',
    exit_strategy='take-profit-20',
    initial_capital=1000.0,
    min_confidence=0.55,  # 55% confidence threshold
    max_position_size=50.0,
    fee_rate=0.02,  # 2% on winnings
    use_llm=False  # Use simplified strategy (not real LLM)
)

# Run backtest
runner = BacktestRunner(config)
result = runner.run()

print("\n" + "=" * 80)
print("FINAL RESULTS")
print("=" * 80)
print(f"Total Trades: {result['total_trades']}")
print(f"Win Rate: {result['win_rate']:.1f}%")
print(f"Total PnL: ${result['total_pnl']:.2f}")
print(f"Total Return: {result['total_return_pct']:.2f}%")
print(f"Sharpe Ratio: {result['sharpe_ratio']:.2f}")
print(f"Max Drawdown: {result['max_drawdown_pct']:.2f}%")
print(f"Profit Factor: {result['profit_factor']:.2f}")

# Edge detection
if result['win_rate'] > 55 and result['sharpe_ratio'] > 1.0:
    print("\n✅ BOT SHOWS POSITIVE EDGE!")
    print("   Win rate > 55% AND Sharpe > 1.0")
    print("   RECOMMENDED: Deploy with small capital")
elif result['win_rate'] > 52 and result['sharpe_ratio'] > 0.5:
    print("\n⚠️  BOT SHOWS BORDERLINE EDGE")
    print("   Further optimization needed")
elif result['total_trades'] == 0:
    print("\n⚠️  NO TRADES EXECUTED")
    print("   Strategy didn't trigger on this data")
else:
    print("\n❌ BOT DOES NOT SHOW POSITIVE EDGE")
    print("   DO NOT deploy with real money")

print(f"\nReport: {result['report_path']}")
