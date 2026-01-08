# Run Bot Locally - Simple Guide

## Quick Start

### 1. Start the Bot
```bash
./run-bot-local.sh
```

That's it! The bot will start and show live logs in your terminal.

**Press `Ctrl+C` to stop the bot**

---

## What You'll See

```
🚀 Starting Polymarket Bot...
Log file: /tmp/continuous_trader.log

Press Ctrl+C to stop the bot

============================================================
CONTINUOUS POLYMARKET TRADER
============================================================
...
```

The bot will:
- Scan for arbitrage every **30 seconds**
- Run AI prediction every **5 minutes**
- Show all activity in the terminal

---

## View Trades

While the bot is running, open a new terminal:

```bash
# Quick summary (recommended)
./check-trades.sh

# Or manually:
# View all trades
cat /tmp/hybrid_autonomous_trades.json | jq '.'

# View latest trade
cat /tmp/hybrid_autonomous_trades.json | jq '.[-1]'

# Count total trades
cat /tmp/hybrid_autonomous_trades.json | jq '. | length'
```

---

## Configuration

Before running live, edit these settings:

### Safety Limits

**File**: `scripts/python/hybrid_autonomous_trader.py`

```python
MAX_POSITION_SIZE = Decimal('2.0')    # Max $2 per trade
MAX_TOTAL_EXPOSURE = Decimal('10.0')  # Max $10 total
DRY_RUN = False                        # Set True to test without real trades
```

### Scan Intervals

**File**: `scripts/python/continuous_trader.py`

```python
ARBITRAGE_SCAN_INTERVAL = 30   # Every 30 seconds
AI_PREDICTION_INTERVAL = 300   # Every 5 minutes
```

---

## Test First (Recommended)

### 1. Enable Dry Run

Edit `scripts/python/hybrid_autonomous_trader.py`:
```python
DRY_RUN = True  # Line ~33
```

Edit `scripts/python/test_autonomous_trader.py`:
```python
DRY_RUN = True  # Line ~39
```

### 2. Run for 1 Hour
```bash
./run-bot-local.sh
```

Watch the output to see what it would do without spending real money.

### 3. Enable Live Trading

When ready, set both files back to:
```python
DRY_RUN = False
```

Then run again:
```bash
./run-bot-local.sh
```

---

## Logs

All output goes to:
- **Terminal** (live)
- **Log file**: `/tmp/continuous_trader.log`

View log file anytime:
```bash
tail -f /tmp/continuous_trader.log
```

---

## Stop the Bot

**Press `Ctrl+C` in the terminal**

The bot will shut down gracefully:
```
🛑 Shutdown signal received, stopping gracefully...
✅ Continuous trader stopped
```

---

## Troubleshooting

### Bot not finding arbitrage
- This is normal! Arbitrage is rare.
- Markets are efficient - most opportunities taken by faster bots.
- Try lowering `MIN_ARBITRAGE_PROFIT_PCT` to 1.0% to see more opportunities.

### AI prediction not executing
- Check: Are there crypto markets ending in 2026+?
- Most markets end in 2025 (filtered out).
- To test, lower `MIN_MARKET_YEAR` to 2025.

### "Max exposure reached"
- Bot tracks open positions.
- Close some positions on Polymarket to free up capital.
- Or increase `MAX_TOTAL_EXPOSURE`.

### Errors in output
- **LunarCrush rate limit**: Increase scan intervals
- **Grok API errors**: Check `XAI_API_KEY` in `.env`
- **Polymarket errors**: Check wallet has USDC + MATIC for gas

---

## Summary

**Start bot**:
```bash
./run-bot-local.sh
```

**Check trades** (in another terminal):
```bash
./check-trades.sh
```

**Stop bot**:
Press `Ctrl+C`

**That's all you need!** Three simple commands, no screen, no systemd.

---

**Pro tip**: Test in dry run first, then enable live trading when confident.
