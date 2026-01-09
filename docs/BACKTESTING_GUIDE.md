# Comprehensive Backtesting Guide

## Why Backtest?

**CRITICAL**: Never trade live without backtesting first. This trading bot may be burning money, not making it. Backtesting helps you:

1. **Validate Edge**: Does the bot actually make money on historical data?
2. **Optimize Strategy**: Which exit strategy works best?
3. **Understand Risk**: What's the maximum drawdown? Sharpe ratio?
4. **Cost Analysis**: Are fees eating all the profits?
5. **Build Confidence**: Know what to expect before risking real capital

## Quick Start

### 1. Install Dependencies

```bash
pip install pandas pyarrow
```

### 2. Run Your First Backtest

```bash
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 \
  --end-date 2026-01-01 \
  --strategy ai-prediction \
  --exit-strategy hold-to-resolution \
  --initial-capital 100.0 \
  --min-confidence 0.2 \
  --max-position-size 2.0
```

### 3. Check Results

The backtest will:
- Generate an HTML report in `data/backtest/reports/`
- Print performance summary to console
- Tell you if the bot has positive edge

## Exit Strategy Comparison

The best way to use backtesting is to test multiple exit strategies:

```bash
# Test different exit strategies
strategies=(
    "hold-to-resolution"
    "take-profit-10"
    "take-profit-20"
    "take-profit-30"
    "stop-loss-10"
    "stop-loss-20"
    "time-24h"
    "time-48h"
    "time-168h"  # 1 week
)

for exit_strategy in "${strategies[@]}"; do
    echo "Testing: $exit_strategy"
    python -m agents.backtesting.backtest_runner \
        --start-date 2025-10-01 \
        --end-date 2026-01-01 \
        --exit-strategy "$exit_strategy" \
        --strategy ai-prediction
done
```

## Understanding Results

### Key Metrics

#### Win Rate
```
Win Rate: 60.0%
```
- Percentage of profitable trades
- Target: > 55% for consistent edge
- Warning: < 50% means more losers than winners

#### Sharpe Ratio
```
Sharpe Ratio: 1.25
```
- Risk-adjusted return metric
- > 1.0 = Good
- > 2.0 = Excellent
- < 0.5 = Poor (too much risk for the return)

#### Max Drawdown
```
Max Drawdown: 8.5%
```
- Largest peak-to-trough decline
- Critical risk metric
- Target: < 15%
- Warning: > 30% means high volatility

#### Profit Factor
```
Profit Factor: 1.80
```
- Total wins / Total losses
- > 1.5 = Good edge
- > 2.0 = Strong edge
- < 1.2 = Weak edge

#### Total Return
```
Total Return: +15.5%
Total PnL: $+15.50
```
- Raw profit/loss
- Must be positive for profitable strategy
- Compare to buy-and-hold alternatives

### Edge Detection

The framework automatically determines if you have positive edge:

✅ **POSITIVE EDGE** if:
- Net PnL > 0 (making money)
- Sharpe Ratio > 0.5 (good risk-adjusted returns)
- Win Rate > 50% (more winners than losers)
- Profit Factor > 1.5 (wins bigger than losses)

❌ **NO EDGE** if:
- Net PnL < 0 (losing money)
- Sharpe Ratio < 0 (negative risk-adjusted returns)
- Win Rate < 45% (too many losers)
- Profit Factor < 1.2 (weak edge)

## Example Output

```
================================================================================
POLYMARKET BOT BACKTESTING
================================================================================
Strategy: ai-prediction
Exit Strategy: take-profit-20
Date Range: 2025-10-01 to 2026-01-01
Initial Capital: $100.00
================================================================================

Loading historical data...
Loaded 7200 market snapshots
Date range: 2025-10-01 to 2026-01-01

Running backtest simulation...
[ENTER] will-trump-win-2024 @ $0.650 size=$2.00 conf=65.0%
[EXIT] will-trump-win-2024 @ $0.780 PnL=$+0.38 (+19.5%) reason=take_profit_20%
[ENTER] bitcoin-50k-by-eoy @ $0.420 size=$1.50 conf=58.0%
[EXIT] bitcoin-50k-by-eoy @ $0.504 PnL=$+0.28 (+18.7%) reason=take_profit_20%
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
Net PnL (after fees): $+14.20
Total Return: +15.5%
Annualized Return: +65.2%
Sharpe Ratio: 1.25
Sortino Ratio: 1.45
Max Drawdown: 8.5%
Profit Factor: 1.80
Avg Trade: $+0.21
Total Fees: $1.30

✅ BOT SHOWS POSITIVE EDGE

Report generated: data/backtest/reports/backtest_report_20260108_120000.html
```

## Advanced Usage

### 1. Test Different Strategies

```bash
# AI prediction (default)
python -m agents.backtesting.backtest_runner \
  --strategy ai-prediction

# Simple momentum
python -m agents.backtesting.backtest_runner \
  --strategy simple-momentum

# Mean reversion
python -m agents.backtesting.backtest_runner \
  --strategy mean-reversion
```

### 2. Optimize Parameters

```bash
# Test different confidence thresholds
for min_conf in 0.1 0.2 0.3 0.4 0.5; do
    python -m agents.backtesting.backtest_runner \
        --min-confidence $min_conf \
        --exit-strategy take-profit-20
done

# Test different position sizes
for max_size in 1.0 2.0 5.0 10.0; do
    python -m agents.backtesting.backtest_runner \
        --max-position-size $max_size \
        --exit-strategy take-profit-20
done
```

### 3. Walk-Forward Analysis

```bash
# Test on different time periods to avoid overfitting
python -m agents.backtesting.backtest_runner \
  --start-date 2025-10-01 --end-date 2025-11-01  # October

python -m agents.backtesting.backtest_runner \
  --start-date 2025-11-01 --end-date 2025-12-01  # November

python -m agents.backtesting.backtest_runner \
  --start-date 2025-12-01 --end-date 2026-01-01  # December
```

## Interpreting Reports

### HTML Report Sections

1. **Configuration**: Settings used for backtest
2. **Edge Verdict**: Clear YES/NO on whether bot has edge
3. **Performance Metrics**: All key metrics organized by category
4. **Trade History**: Complete list of all trades
5. **Recommendations**: Actionable advice based on results

### What to Look For

#### Good Signs ✅
- Win rate > 55%
- Sharpe ratio > 1.0
- Profit factor > 1.5
- Max drawdown < 15%
- Consistent performance across time periods
- Fees < 20% of total profits

#### Warning Signs ⚠️
- Win rate < 50%
- Sharpe ratio < 0.5
- Profit factor < 1.2
- Max drawdown > 25%
- Performance varies wildly across time periods
- Fees > 30% of total profits

#### Red Flags ❌
- Negative total PnL
- Win rate < 45%
- Negative Sharpe ratio
- Max drawdown > 40%
- Very few trades (< 10)
- Fees > 50% of total profits

## Limitations

### Current Framework Limitations

1. **No Historical Data**: Polymarket doesn't provide historical API
   - Using synthetic data for testing
   - Need to collect real historical data for accurate backtests

2. **Simplified LLM**: Not using actual LLM predictions
   - Using heuristic approximations
   - Real bot performance may differ

3. **Perfect Execution**: Assumes fills at mid price
   - Real trading has slippage
   - Large positions may move the market

4. **Limited Market Types**: Synthetic data only
   - Need to test on real market categories
   - Different markets may have different characteristics

### How to Improve Backtests

1. **Collect Real Data**
   - Scrape Polymarket frontend
   - Use archive.org snapshots
   - Partner with data providers

2. **Cache LLM Responses**
   - Store all LLM predictions
   - Replay in backtest
   - Measure actual LLM accuracy

3. **Add Slippage Model**
   - Simulate realistic fills
   - Account for liquidity
   - Model market impact

4. **Test on Real Markets**
   - Use actual resolved markets
   - Test across categories
   - Validate assumptions

## Best Practices

### Before Live Trading

1. ✅ Run backtests on at least 90 days of data
2. ✅ Test multiple exit strategies
3. ✅ Verify positive edge (Sharpe > 0.5, PnL > 0)
4. ✅ Understand maximum drawdown
5. ✅ Check win rate is consistent
6. ✅ Analyze fee impact
7. ✅ Test on out-of-sample data

### During Live Trading

1. 📊 Monitor live performance vs backtest expectations
2. 📊 Track actual win rate vs backtested
3. 📊 Watch for strategy degradation
4. 📊 Compare fees in live vs backtest
5. 📊 Stop trading if metrics diverge significantly

### Red Flags to Stop Trading

❌ Stop immediately if:
- Live win rate < backtest win rate - 10%
- Live losses exceed backtest max drawdown
- Strategy starts losing money consistently
- Fees are higher than expected
- Market conditions change dramatically

## Troubleshooting

### "No opportunities found"
- Lower min-confidence threshold
- Check strategy logic
- Verify data has markets in price range

### "All trades are losers"
- Strategy logic may be inverted
- Check exit strategy is appropriate
- Verify synthetic data is realistic

### "Fees eating all profits"
- Increase position sizes
- Reduce trading frequency
- Consider different markets

### "High volatility / drawdown"
- Reduce position sizes
- Tighten stop losses
- Lower confidence threshold

## Next Steps

1. **Run backtests** on current strategy
2. **Compare exit strategies** to find optimal
3. **Test parameter sensitivity** to avoid overfitting
4. **Collect real data** once available
5. **Start paper trading** if edge confirmed
6. **Monitor live performance** closely
7. **Iterate and improve** based on results

Remember: **Backtesting doesn't guarantee future profits**, but it's the best tool to validate strategy before risking real capital.

## Support

For questions or issues:
- Review `/home/tony/Dev/agents/agents/backtesting/README.md`
- Check example code in test files
- Run synthetic tests first
- Compare results across strategies

Good luck and trade responsibly!
