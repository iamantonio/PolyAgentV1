# Polymarket Trading Bot - Backtesting Framework

## Overview

This comprehensive backtesting framework validates if the trading bot has positive edge before risking real capital. It simulates trading on historical data and calculates rigorous performance metrics.

## 🚨 CRITICAL: Why This Matters

**You don't know if the bot is profitable until you backtest it.**

Without backtesting, you're:
- Flying blind with real money
- Unable to optimize strategy
- Risking capital on unproven logic
- Missing opportunity costs

With backtesting, you can:
- ✅ Validate positive edge on historical data
- ✅ Optimize exit strategies for max profit
- ✅ Understand risk (drawdown, volatility)
- ✅ Calculate expected returns
- ✅ Identify cost inefficiencies

## What's Included

### 1. Historical Data Fetcher (`agents/backtesting/historical_data.py`)
- Fetches resolved markets from Polymarket API
- Stores data efficiently in Parquet format
- Creates synthetic data for testing (until real data available)
- Caches data in SQLite for incremental updates

### 2. Backtest Runner (`agents/backtesting/backtest_runner.py`)
- Main backtesting engine
- Simulates trading bot execution on historical data
- Tests different strategies and exit strategies
- Tracks all positions and PnL

### 3. Performance Metrics (`agents/backtesting/metrics.py`)
- Calculates comprehensive trading metrics:
  - Win rate
  - Sharpe ratio (risk-adjusted returns)
  - Sortino ratio (downside risk)
  - Maximum drawdown
  - Profit factor
  - Total returns
  - Fee analysis

### 4. Report Generator (`agents/backtesting/report_generator.py`)
- Generates beautiful HTML reports
- Exports JSON for programmatic access
- Provides actionable recommendations
- Automated edge detection

## Quick Start

### Installation

```bash
# Install dependencies
pip install pandas pyarrow

# Or install all requirements
pip install -r requirements.txt
```

### Run Your First Backtest

```bash
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 \
  --end-date 2026-01-01 \
  --strategy ai-prediction \
  --exit-strategy hold-to-resolution
```

### Compare Exit Strategies

```bash
# Run automated comparison
./scripts/run_backtest_comparison.sh
```

## Key Metrics Explained

### Win Rate
Percentage of profitable trades. Target: > 55%

### Sharpe Ratio
Risk-adjusted return metric:
- > 2.0 = Excellent
- > 1.0 = Good
- > 0.5 = Acceptable
- < 0.5 = Poor

### Maximum Drawdown
Largest peak-to-trough decline. Target: < 15%

### Profit Factor
Total wins / Total losses. Target: > 1.5

## Exit Strategies

Test these to find the optimal strategy:

1. **hold-to-resolution**: Hold until market resolves (current)
2. **take-profit-X**: Exit when profit reaches X%
3. **stop-loss-X**: Exit when loss reaches X%
4. **time-Xh**: Exit after X hours

## Example Results

```
================================================================================
PERFORMANCE SUMMARY
================================================================================
Win Rate: 60.0%
Total PnL: $+15.50
Net PnL (after fees): $+14.20
Total Return: +15.5%
Annualized Return: +65.2%
Sharpe Ratio: 1.25
Max Drawdown: 8.5%
Profit Factor: 1.80

✅ BOT SHOWS POSITIVE EDGE
```

## Files Created

```
agents/backtesting/
├── __init__.py                  # Module exports
├── historical_data.py           # Data fetching and storage
├── backtest_runner.py           # Main backtesting engine
├── metrics.py                   # Performance calculations
├── report_generator.py          # HTML/JSON report generation
└── README.md                    # Detailed documentation

docs/
└── BACKTESTING_GUIDE.md         # Comprehensive user guide

scripts/
└── run_backtest_comparison.sh   # Automated exit strategy comparison

tests/
└── test_backtesting.py          # Framework validation tests

data/backtest/
├── synthetic_historical_data.parquet  # Test data
├── historical_cache.db                # SQLite cache
└── reports/                           # Generated HTML reports
```

## Usage Examples

### 1. Basic Backtest

```bash
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 \
  --end-date 2026-01-01
```

### 2. Test Specific Strategy

```bash
python -m agents.backtesting.backtest_runner \
  --strategy mean-reversion \
  --exit-strategy take-profit-20
```

### 3. Optimize Position Size

```bash
for size in 1.0 2.0 5.0 10.0; do
  python -m agents.backtesting.backtest_runner \
    --max-position-size $size \
    --exit-strategy take-profit-20
done
```

### 4. Test Confidence Thresholds

```bash
for conf in 0.1 0.2 0.3 0.4 0.5; do
  python -m agents.backtesting.backtest_runner \
    --min-confidence $conf
done
```

## Python API Usage

```python
from agents.backtesting import BacktestRunner, BacktestConfig
from datetime import datetime, timezone

# Create configuration
config = BacktestConfig(
    start_date=datetime(2025, 10, 1, tzinfo=timezone.utc),
    end_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    initial_capital=100.0,
    strategy='ai-prediction',
    exit_strategy='take-profit-20',
    min_confidence=0.2,
    max_position_size=2.0,
    fee_rate=0.02,
    use_llm=False
)

# Run backtest
runner = BacktestRunner(config)
results = runner.run()

# Check results
perf = results['performance']
print(f"Win Rate: {perf.win_rate:.1%}")
print(f"Sharpe: {perf.sharpe_ratio:.2f}")
print(f"PnL: ${perf.net_pnl:+.2f}")
```

## Limitations

### Current Limitations

1. **No Historical Data**: Polymarket doesn't provide historical API
   - Using synthetic data for testing
   - Need to collect real data for accurate backtests

2. **Simplified LLM**: Not using actual LLM predictions
   - Using heuristic approximations
   - Should cache real LLM responses

3. **Perfect Execution**: Assumes fills at mid price
   - Real trading has slippage
   - Need to model market impact

### Future Improvements

1. **Real Historical Data Collection**
   - Scrape Polymarket frontend
   - Use archive.org snapshots
   - Partner with data providers

2. **LLM Response Caching**
   - Cache all LLM predictions
   - Replay in backtest
   - Measure actual accuracy

3. **Advanced Features**
   - Walk-forward optimization
   - Monte Carlo simulation
   - Portfolio optimization
   - Multi-market testing

## Best Practices

### Before Live Trading

1. ✅ Backtest on at least 90 days of data
2. ✅ Test multiple exit strategies
3. ✅ Verify positive edge (Sharpe > 0.5)
4. ✅ Understand maximum drawdown
5. ✅ Validate on out-of-sample data
6. ✅ Check fee impact
7. ✅ Paper trade first

### During Live Trading

1. 📊 Monitor vs backtest expectations
2. 📊 Track live win rate
3. 📊 Watch for strategy degradation
4. 📊 Compare fees
5. 📊 Stop if metrics diverge

### Red Flags

❌ Stop trading immediately if:
- Live win rate < backtest - 10%
- Losses exceed backtest max drawdown
- Consistent losing streak
- Fees higher than expected
- Market conditions change dramatically

## Testing the Framework

```bash
# Run framework tests
source .venv/bin/activate
python3 tests/test_backtesting.py

# Should see:
# ✅ ALL TESTS PASSED
```

## Documentation

- **Detailed Guide**: `docs/BACKTESTING_GUIDE.md`
- **Module README**: `agents/backtesting/README.md`
- **Code Examples**: `tests/test_backtesting.py`

## Support

For issues or questions:
1. Check the documentation files
2. Review test examples
3. Run synthetic tests first
4. Compare results across strategies

## Next Steps

1. **Run backtests** on current strategy
2. **Compare exit strategies** to find optimal
3. **Test parameter sensitivity**
4. **Collect real data** when available
5. **Paper trade** if edge confirmed
6. **Monitor live performance**
7. **Iterate and improve**

## Summary

This backtesting framework is **critical** for validating trading strategy before risking real capital. It provides:

- ✅ Comprehensive performance metrics
- ✅ Exit strategy optimization
- ✅ Risk analysis (drawdown, volatility)
- ✅ Cost analysis (fees, slippage)
- ✅ Beautiful HTML reports
- ✅ Automated edge detection

**Remember**: Past performance doesn't guarantee future results, but it's the best tool we have to validate strategy before trading live.

Good luck and trade responsibly!
