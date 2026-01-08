# Polymarket Trading Bot - START HERE

## 🎯 What This Bot Does

**Fully automated 24/7 Polymarket trading** with two proven strategies:

1. **Arbitrage** (Risk-free) - Buys mispriced markets for guaranteed profit
2. **AI Prediction** (High-reward) - Uses Grok AI + social data to predict outcomes

**Both strategies execute trades automatically!**

---

## ⚡ Quick Start (3 Commands)

### 1. Start the Bot
```bash
./run-bot-local.sh
```

### 2. Check Trades (in another terminal)
```bash
./check-trades.sh
```

### 3. Stop the Bot
Press `Ctrl+C` in the bot terminal

---

## 📚 Full Guides

### Just Want to Run It?
👉 **[RUN_LOCAL.md](RUN_LOCAL.md)** - Simple guide for running locally (RECOMMENDED FOR YOU)

### Want All the Details?
👉 **[QUICKSTART.md](QUICKSTART.md)** - Quick overview of what the bot does

### Need 24/7 Background Operation?
👉 **[24-7-DEPLOYMENT-GUIDE.md](24-7-DEPLOYMENT-GUIDE.md)** - Screen, systemd, Docker options

### Curious About the Implementation?
👉 **[ARBITRAGE_EXECUTION_IMPLEMENTATION.md](ARBITRAGE_EXECUTION_IMPLEMENTATION.md)** - Technical deep dive
👉 **[BOT_IMPROVEMENTS_SUMMARY.md](BOT_IMPROVEMENTS_SUMMARY.md)** - Full research & bug fixes

---

## ⚙️ Before First Run

### 1. Set Dry Run Mode (Recommended)

Test without real money first!

**Edit** `scripts/python/hybrid_autonomous_trader.py`:
```python
DRY_RUN = True  # Line ~33
```

**Edit** `scripts/python/test_autonomous_trader.py`:
```python
DRY_RUN = True  # Line ~39
```

### 2. Check Your .env File

Make sure you have:
```env
POLYGON_WALLET_PRIVATE_KEY=your_key_here
XAI_API_KEY=your_grok_key_here
LUNARCRUSH_API_KEY=your_lunarcrush_key_here
```

### 3. Start Small

In `scripts/python/hybrid_autonomous_trader.py`:
```python
MAX_POSITION_SIZE = Decimal('1.0')   # $1 per trade
MAX_TOTAL_EXPOSURE = Decimal('5.0')  # $5 total
```

---

## 🎓 How It Works

```
Every 30 seconds:
├─ 🔍 Scan for arbitrage
│   ├─ Binary: YES + NO < $0.99? → Buy both!
│   ├─ Multi-outcome: All < $0.99? → Buy all!
│   └─ Asymmetric: Single side < $0.97? → Buy it!
│
Every 5 minutes:
└─ 🤖 Run AI prediction
    ├─ Fetch crypto markets (2026+)
    ├─ Get social data (LunarCrush)
    ├─ Analyze with Grok AI
    └─ Execute if confident
```

---

## 🛡️ Safety Features

✅ **Position Limits** - Max $2 per trade, $10 total (configurable)
✅ **Dry Run Mode** - Test without spending money
✅ **Fill-or-Kill Orders** - Atomic execution (all or nothing)
✅ **Error Handling** - Graceful failure, keeps running
✅ **Trade Logging** - All executions saved to JSON

---

## 📊 What to Expect

### Arbitrage
- **Frequency**: Rare (markets are efficient)
- **Profit**: 1-3% per trade
- **Risk**: Zero (risk-free)

### AI Prediction
- **Frequency**: Evaluates every 5 minutes
- **Profit**: 10-50%+ if correct
- **Risk**: Moderate (needs accuracy)

**Don't expect constant trades!** The bot is patient and only trades when it finds real opportunities.

---

## ❓ Common Questions

### Does the bot buy for me?
**YES!** Both arbitrage and AI prediction execute automatically.

### Will it trade constantly?
**NO.** Arbitrage is rare, AI prediction only trades on 2026+ crypto markets with high confidence.

### Can I lose money?
**YES.** Arbitrage is risk-free but rare. AI prediction can be wrong. Start small!

### How do I stop losing money?
Press `Ctrl+C` to stop the bot immediately.

### Can I test without real money?
**YES!** Set `DRY_RUN = True` in both bot files.

---

## 🚀 Recommended Workflow

1. **Test in dry run for 1 hour**
   ```bash
   # Set DRY_RUN = True in both files
   ./run-bot-local.sh
   ```

2. **Watch what it does**
   ```bash
   # In another terminal
   ./check-trades.sh
   ```

3. **Enable live trading**
   ```bash
   # Set DRY_RUN = False in both files
   ./run-bot-local.sh
   ```

4. **Monitor closely for first 24 hours**
   ```bash
   ./check-trades.sh  # Run every hour
   ```

5. **Scale up when confident**
   ```python
   MAX_POSITION_SIZE = Decimal('5.0')
   MAX_TOTAL_EXPOSURE = Decimal('50.0')
   ```

---

## 🎯 Files You Need

### Run the Bot
- **`run-bot-local.sh`** - Start bot (simple)
- **`check-trades.sh`** - View trades summary
- **`scripts/bash/run-24-7.sh`** - Start bot (background)

### Configure the Bot
- **`scripts/python/hybrid_autonomous_trader.py`** - Arbitrage settings
- **`scripts/python/test_autonomous_trader.py`** - AI prediction settings
- **`scripts/python/continuous_trader.py`** - Scan intervals

### Read the Docs
- **`RUN_LOCAL.md`** - Simple local guide (start here!)
- **`QUICKSTART.md`** - Quick overview
- **`24-7-DEPLOYMENT-GUIDE.md`** - Background deployment
- **`ARBITRAGE_EXECUTION_IMPLEMENTATION.md`** - Technical details

---

## 💡 Pro Tips

1. **Test in dry run first** - See what it would do
2. **Start small** - $1 trades until confident
3. **Be patient** - Arbitrage is rare, that's normal
4. **Check trades daily** - Use `./check-trades.sh`
5. **Monitor logs** - `tail -f /tmp/continuous_trader.log`

---

## 🆘 Need Help?

1. **Read** `RUN_LOCAL.md` - Covers 90% of questions
2. **Check logs** - `tail -f /tmp/continuous_trader.log`
3. **View trades** - `./check-trades.sh`
4. **Check wallet** - Make sure you have USDC + MATIC

---

## ✅ You're Ready!

**Three commands is all you need:**

```bash
./run-bot-local.sh    # Start
./check-trades.sh     # Check
Ctrl+C                # Stop
```

**Start in dry run, then go live when ready. Good luck! 🚀**
