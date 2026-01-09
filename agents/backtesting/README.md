# Polymarket Trading Bot - Backtesting Framework

This backtesting framework validates if the trading bot has positive edge before risking real capital.

## Overview

**CRITICAL**: You should NEVER trade live without backtesting first. This framework helps you answer:
- Does the bot actually make money?
- What's the win rate on historical data?
- How much risk am I taking (drawdown)?
- What's the best exit strategy?
- Are fees eating all the profits?

## Installation

```bash
# Install required dependencies
pip install pandas pyarrow requests

# The framework is already integrated into the project
cd /home/tony/Dev/agents
```

## Quick Start

### 1. Run Basic Backtest

```bash
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 \
  --end-date 2026-01-01 \
  --strategy ai-prediction \
  --exit-strategy hold-to-resolution
```

### 2. Test Different Exit Strategies

```bash
# Hold to resolution (current strategy)
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 \
  --end-date 2026-01-01 \
  --exit-strategy hold-to-resolution

# Take profit at 20%
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 \
  --end-date 2026-01-01 \
  --exit-strategy take-profit-20

# Stop loss at 10%
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 \
  --end-date 2026-01-01 \
  --exit-strategy stop-loss-10

# Exit after 24 hours
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 \
  --end-date 2026-01-01 \
  --exit-strategy time-24h
```

### 3. Test Different Strategies

```bash
# AI prediction strategy
python -m agents.backtesting.backtest_runner \
  --strategy ai-prediction

# Simple momentum
python -m agents.backtesting.backtest_runner \
  --strategy simple-momentum

# Mean reversion
python -m agents.backtesting.backtest_runner \
  --strategy mean-reversion
```

## Components

### 1. Historical Data Fetcher (`historical_data.py`)

Fetches and stores historical market data:

```python
from agents.backtesting import HistoricalDataFetcher

fetcher = HistoricalDataFetcher()

# Fetch resolved markets
markets = fetcher.fetch_resolved_markets(
    start_date=datetime(2025, 10, 1),
    end_date=datetime(2026, 1, 1)
)

# Create synthetic data (for testing)
df = fetcher.create_synthetic_data(num_markets=20, days=180)
```

**Note**: Polymarket doesn't provide historical API data, so we use:
1. Synthetic data for testing
2. Manual data collection (coming soon)
3. Third-party data providers (coming soon)

### 2. Performance Metrics (`metrics.py`)

Calculates comprehensive performance metrics:

```python
from agents.backtesting import PerformanceMetrics

metrics = PerformanceMetrics(initial_capital=100.0)
report = metrics.calculate_metrics(trades, total_days=90)

print(f"Win Rate: {report.win_rate:.1%}")
print(f"Sharpe Ratio: {report.sharpe_ratio:.2f}")
print(f"Max Drawdown: {report.max_drawdown_pct:.1f}%")
```

Key metrics:
- **Win Rate**: % of profitable trades
- **Sharpe Ratio**: Risk-adjusted returns (>1.0 is good)
- **Sortino Ratio**: Like Sharpe but only penalizes downside
- **Max Drawdown**: Largest peak-to-trough decline
- **Profit Factor**: Total wins / Total losses (>1.5 is good)

### 3. Backtest Runner (`backtest_runner.py`)

Main backtesting engine that simulates trading:

```python
from agents.backtesting import BacktestRunner, BacktestConfig

config = BacktestConfig(
    start_date=datetime(2025, 10, 1),
    end_date=datetime(2026, 1, 1),
    initial_capital=100.0,
    strategy='ai-prediction',
    exit_strategy='hold-to-resolution',
    min_confidence=0.2,
    max_position_size=2.0,
    fee_rate=0.02,
    use_llm=False
)

runner = BacktestRunner(config)
results = runner.run()
```

### 4. Report Generator (`report_generator.py`)

Generates HTML and JSON reports:

```python
from agents.backtesting import ReportGenerator

generator = ReportGenerator()
report_path = generator.generate_html_report(performance, trades, config)
```

Reports include:
- Performance summary
- Trade history
- Equity curve
- Recommendations
- Edge detection verdict

## Understanding Results

### Positive Edge Indicators

✅ Bot shows positive edge if:
- **Net PnL > 0**: Making money after fees
- **Win Rate > 50%**: More winners than losers
- **Sharpe Ratio > 0.5**: Decent risk-adjusted returns
- **Profit Factor > 1.5**: Wins are bigger than losses

### Red Flags

❌ Do NOT trade live if:
- **Net PnL < 0**: Losing money
- **Win Rate < 45%**: Too many losers
- **Sharpe Ratio < 0**: Risk-adjusted returns are negative
- **Max Drawdown > 30%**: Too much volatility

## Limitations

### Current Limitations

1. **No Historical Data**: Polymarket doesn't provide historical API access
   - Using synthetic data for testing
   - Need to collect real historical data

2. **Simplified LLM Simulation**: Not using actual LLM predictions
   - Using heuristic approximations
   - Should cache real LLM responses for accurate backtests

3. **Market Impact**: Not simulating slippage or liquidity constraints
   - Assumes perfect fills at mid price
   - Real trading will have worse execution

4. **Limited Market Types**: Only testing on synthetic binary markets
   - Need to test on real market categories
   - Different market types may have different edge

### Future Improvements

1. **Real Historical Data**
   - Scrape data from Polymarket frontend
   - Use archive.org snapshots
   - Partner with data providers

2. **LLM Response Caching**
   - Cache real LLM predictions
   - Replay cached responses in backtest
   - Measure actual LLM performance

3. **Advanced Features**
   - Walk-forward optimization
   - Monte Carlo simulation
   - Strategy optimization
   - Multi-market portfolio testing

## Example Output

```
================================================================================
POLYMARKET BOT BACKTESTING
================================================================================
Strategy: ai-prediction
Exit Strategy: hold-to-resolution
Date Range: 2025-10-01 to 2026-01-01
Initial Capital: $100.00
================================================================================

Loading historical data...
Loaded 7200 market snapshots
Date range: 2025-10-01 to 2026-01-01

Running backtest simulation...
[ENTER] will-trump-win-2024 @ $0.650 size=$2.00 conf=65.0%
[EXIT] will-trump-win-2024 @ $1.000 PnL=$+0.68 (+34.0%) reason=market_resolved
...

================================================================================
BACKTEST COMPLETE
================================================================================
Opportunities Found: 150
Trades Executed: 75
Final Capital: $115.50

PERFORMANCE SUMMARY
================================================================================
Win Rate: 60.0%
Total PnL: $+15.50
Total Return: +15.5%
Sharpe Ratio: 1.25
Max Drawdown: 8.5%
Profit Factor: 1.80

✅ BOT SHOWS POSITIVE EDGE

Report generated: data/backtest/reports/backtest_report_20260108_120000.html
```

## Best Practices

1. **Always backtest** before live trading
2. **Test multiple strategies** to find the best
3. **Compare exit strategies** to optimize
4. **Check for overfitting** by testing on different time periods
5. **Account for costs** - fees can kill profitability
6. **Validate with real data** once available
7. **Monitor live performance** against backtest expectations

## Next Steps

1. Run backtests on current strategy
2. Analyze results and identify edge
3. Test different exit strategies
4. Optimize parameters
5. Validate on out-of-sample data
6. Start live trading (if edge confirmed)
7. Monitor live vs backtest performance

## Support

For issues or questions:
- Check the code comments
- Review the example usage
- Test with synthetic data first
- Compare results across strategies

Remember: **Past performance doesn't guarantee future results**, but it's the best tool we have to validate strategy before risking real capital.
