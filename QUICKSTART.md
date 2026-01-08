# Polymarket Bot - Quick Start Guide

## 🎯 What You Have Now

A **production-ready 24/7 Polymarket trading bot** that combines:

1. **Arbitrage** (risk-free, every 30s) - Like the $40M+ winning bots
2. **AI Prediction** (Grok + LunarCrush, every 5min) - Your original strategy, now fixed

## ⚡ Quick Start (3 Steps)

### 1. Test It First
```bash
# Test arbitrage detection (quick)
python scripts/python/hybrid_autonomous_trader.py

# Test AI prediction (slower, needs Grok)
python scripts/python/test_autonomous_trader.py
```

### 2. Run 24/7
```bash
# Start continuous trading
./scripts/bash/run-24-7.sh

# Monitor live (attach to screen)
screen -r polymarket-bot

# Detach but keep running
# Press: Ctrl+A, then D
```

### 3. Check Status
```bash
# Quick status check
./scripts/bash/bot-status.sh

# View logs
tail -f /tmp/continuous_trader.log

# Stop bot
./scripts/bash/stop-bot.sh
```

## 📊 How It Works

```
Every 30 seconds:
├─ 🔍 Scan for arbitrage
│   ├─ YES + NO < $0.99? → Execute immediately!
│   └─ Multi-outcome < $0.99? → Execute!
│
Every 5 minutes:
└─ 🤖 Run AI prediction
    ├─ Fetch crypto markets (2026+)
    ├─ Get LunarCrush social data
    ├─ Analyze with Grok
    └─ Execute if confident
```

## 🛠️ Files You Need to Know

### Core Bot Files
- **`continuous_trader.py`** - 24/7 main loop (arbitrage + AI)
- **`hybrid_autonomous_trader.py`** - Arbitrage-only bot
- **`test_autonomous_trader.py`** - AI prediction-only bot (fixed)

### Strategy Modules
- **`agents/strategies/arbitrage.py`** - Binary + multi-outcome detection
- **`agents/connectors/websocket_monitor.py`** - Real-time price monitoring (future)
- **`agents/connectors/lunarcrush.py`** - Social intelligence (working!)

### Management Scripts
- **`scripts/bash/run-24-7.sh`** - Start bot in screen
- **`scripts/bash/bot-status.sh`** - Check if running
- **`scripts/bash/stop-bot.sh`** - Stop bot gracefully

### Documentation
- **`BOT_IMPROVEMENTS_SUMMARY.md`** - Full research & implementation details
- **`24-7-DEPLOYMENT-GUIDE.md`** - Complete deployment options
- **`QUICKSTART.md`** - This file

## 🔧 Configuration

### Safety Limits (Edit before running)

In `hybrid_autonomous_trader.py` and `test_autonomous_trader.py`:

```python
MAX_POSITION_SIZE = Decimal('2.0')   # Max $2 per trade
MAX_TOTAL_EXPOSURE = Decimal('10.0') # Max $10 total

DRY_RUN = False  # Set True to test without real trades
```

### Scan Intervals

In `continuous_trader.py`:

```python
ARBITRAGE_SCAN_INTERVAL = 30   # Every 30 seconds
AI_PREDICTION_INTERVAL = 300   # Every 5 minutes
```

### Strategy Filters

In `test_autonomous_trader.py` (AI prediction):

```python
CRYPTO_ONLY = True         # Only crypto markets
MIN_MARKET_YEAR = 2026     # Only 2026+ markets
MIN_HOURS_TO_CLOSE = 48    # Minimum 48 hours until close
```

## 📈 Monitoring

### Check Trades
```bash
# Arbitrage trades
cat /tmp/hybrid_autonomous_trades.json | jq '.'

# AI prediction trades
cat /tmp/autonomous_trades.json | jq '.'
```

### Watch Performance
```bash
# Live log stream
tail -f /tmp/continuous_trader.log

# Errors only
grep "ERROR" /tmp/continuous_trader.log

# Trades only
grep "TRADE" /tmp/continuous_trader.log

# Statistics
grep "STATISTICS" /tmp/continuous_trader.log -A 10
```

## 🚨 Important Notes

### Before Running Live

1. **Test in dry run mode first**
   ```python
   DRY_RUN = True  # In both bot files
   ```

2. **Check your wallet has USDC**
   ```bash
   # The bot needs USDC in your Polymarket proxy wallet
   ```

3. **Verify environment variables**
   ```bash
   cat .env | grep -E "XAI_API_KEY|LUNARCRUSH_API_KEY|POLYMARKET"
   ```

4. **Start small**
   ```python
   MAX_POSITION_SIZE = Decimal('1.0')  # Start with $1 trades
   ```

### What Each Strategy Does

**Arbitrage (Layer 1):**
- Scans all markets every 30s
- Executes when YES + NO < $0.99
- Risk-free profit, ~1-3% per trade
- **FULLY AUTOMATED**: Detects AND executes trades

**AI Prediction (Layer 2):**
- Analyzes crypto markets every 5 min
- Uses Grok (2M context) + LunarCrush (71M+ interactions)
- Only 2026+ markets, 48+ hours to close
- Fully working with all bugs fixed

## 🎓 Learn More

- **Full details**: Read `BOT_IMPROVEMENTS_SUMMARY.md`
- **Deployment options**: Read `24-7-DEPLOYMENT-GUIDE.md`
- **Research sources**: Listed in `BOT_IMPROVEMENTS_SUMMARY.md`

## ❓ Troubleshooting

**Bot not finding arbitrage:**
- Markets are efficient - arbitrage is rare
- Try lowering `MIN_ARBITRAGE_PROFIT_PCT` to 1.0%
- Most arbitrage taken by WebSocket bots (faster)

**AI prediction not executing:**
- Check: Are there crypto markets ending in 2026+?
- Most markets end in 2025 (filtered out by design)
- Lower `MIN_MARKET_YEAR` to 2025 to test

**"Already have position" messages:**
- Bot tracks open positions in JSON files
- Close positions on Polymarket to free up exposure
- Or increase `MAX_TOTAL_EXPOSURE`

**Errors in logs:**
- LunarCrush rate limit: Increase scan intervals
- Grok API errors: Check `XAI_API_KEY` in `.env`
- Polymarket errors: Check wallet has USDC + gas (MATIC)

## 🚀 Next Steps

1. **Test everything in dry run**
   ```bash
   # Set DRY_RUN = True in both bots
   python scripts/python/continuous_trader.py
   ```

2. **Run for 1 hour, monitor closely**
   ```bash
   ./scripts/bash/run-24-7.sh
   screen -r polymarket-bot  # Watch it run
   ```

3. **Check results, adjust config**
   ```bash
   ./scripts/bash/bot-status.sh
   cat /tmp/continuous_trader.log
   ```

4. **Scale up when confident**
   ```python
   MAX_TOTAL_EXPOSURE = Decimal('50.0')  # Increase limit
   ```

## 💡 Pro Tips

- **Arbitrage is rare** - Don't expect constant trades
- **AI prediction is slow** - Needs time for edge to play out
- **Start conservative** - Small positions, monitor closely
- **Check logs daily** - Watch for errors or issues
- **Both strategies can coexist** - Arbitrage doesn't block AI

---

**You're ready to go! Start with dry run, then go live.** 🎯

Questions? Check the full guides or the code comments.
