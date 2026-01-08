# 24/7 Polymarket Bot Deployment Guide

## Overview

Your Polymarket bot can now run 24/7 with **automated strategy selection**:

- **Arbitrage scanning**: Every 30 seconds (fast, risk-free)
- **AI prediction**: Every 5 minutes (slower, higher returns)
- **Auto-restart**: On errors with cooldown
- **Graceful shutdown**: Ctrl+C or kill signal
- **Full logging**: All trades and errors tracked

## Quick Start (Recommended: Screen)

### Start the Bot
```bash
./scripts/bash/run-24-7.sh
```

### Monitor the Bot
```bash
# Attach to screen session (view live output)
screen -r polymarket-bot

# Detach from screen (bot keeps running)
# Press: Ctrl+A, then D

# View logs
tail -f /tmp/continuous_trader.log

# Check status
./scripts/bash/bot-status.sh
```

### Stop the Bot
```bash
./scripts/bash/stop-bot.sh

# Or manually
screen -X -S polymarket-bot quit
```

## Deployment Options

### Option 1: Screen (Easiest)

**Pros:**
- Easy to monitor (attach/detach)
- No special permissions needed
- Quick setup

**Cons:**
- Stops if you log out (unless using tmux)
- No automatic restart on reboot

**Setup:**
```bash
# Start
./scripts/bash/run-24-7.sh

# View live
screen -r polymarket-bot

# Detach (keep running)
Ctrl+A, then D

# Stop
./scripts/bash/stop-bot.sh
```

### Option 2: Systemd (Production)

**Pros:**
- Auto-restart on crashes
- Starts on system boot
- Resource limits (CPU, memory)
- Professional logging

**Cons:**
- Requires sudo for setup
- More complex management

**Setup:**
```bash
# Install service file
sudo cp scripts/systemd/polymarket-bot.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable (start on boot)
sudo systemctl enable polymarket-bot

# Start now
sudo systemctl start polymarket-bot

# Check status
sudo systemctl status polymarket-bot

# View logs
sudo journalctl -u polymarket-bot -f

# Stop
sudo systemctl stop polymarket-bot

# Disable auto-start
sudo systemctl disable polymarket-bot
```

### Option 3: Nohup (Simple Background)

**Pros:**
- Very simple
- No dependencies

**Cons:**
- Hard to monitor
- No auto-restart

**Setup:**
```bash
cd /home/tony/Dev/agents
source .venv/bin/activate
export PYTHONPATH=.

# Start in background
nohup python scripts/python/continuous_trader.py > /tmp/bot-output.log 2>&1 &

# Save PID
echo $! > /tmp/bot.pid

# Stop
kill $(cat /tmp/bot.pid)

# View logs
tail -f /tmp/bot-output.log
```

### Option 4: Docker (Isolation)

**Pros:**
- Completely isolated
- Easy deployment anywhere
- Reproducible environment

**Cons:**
- Requires Docker knowledge
- More setup

**Dockerfile** (create this):
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy project
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run bot
CMD ["python", "scripts/python/continuous_trader.py"]
```

**Run:**
```bash
# Build
docker build -t polymarket-bot .

# Run
docker run -d \
  --name polymarket-bot \
  --restart unless-stopped \
  -v $(pwd)/.env:/app/.env \
  -v /tmp:/tmp \
  polymarket-bot

# View logs
docker logs -f polymarket-bot

# Stop
docker stop polymarket-bot
```

## Monitoring & Management

### Check Bot Status
```bash
./scripts/bash/bot-status.sh
```

Output shows:
- Screen session status
- Systemd service status
- Recent log entries
- Trade count

### View Live Logs
```bash
# Continuous trader log
tail -f /tmp/continuous_trader.log

# Systemd logs (if using systemd)
sudo journalctl -u polymarket-bot -f

# Screen session (if using screen)
screen -r polymarket-bot
```

### Check Trades
```bash
# Arbitrage trades
cat /tmp/hybrid_autonomous_trades.json | jq '.'

# AI prediction trades
cat /tmp/autonomous_trades.json | jq '.'

# Count trades
jq '. | length' /tmp/hybrid_autonomous_trades.json
```

### Monitor Performance
```bash
# Watch logs in real-time
watch -n 5 './scripts/bash/bot-status.sh'

# Grep for trades
grep "TRADE" /tmp/continuous_trader.log

# Grep for errors
grep "ERROR" /tmp/continuous_trader.log
```

## Configuration

### Adjust Scan Intervals

Edit `scripts/python/continuous_trader.py`:

```python
# Default settings
ARBITRAGE_SCAN_INTERVAL = 30  # Every 30 seconds
AI_PREDICTION_INTERVAL = 300  # Every 5 minutes

# More aggressive (faster, more API calls)
ARBITRAGE_SCAN_INTERVAL = 10  # Every 10 seconds
AI_PREDICTION_INTERVAL = 180  # Every 3 minutes

# Conservative (slower, fewer API calls)
ARBITRAGE_SCAN_INTERVAL = 60  # Every 1 minute
AI_PREDICTION_INTERVAL = 600  # Every 10 minutes
```

### Safety Limits

Both strategies share limits from:
- `scripts/python/hybrid_autonomous_trader.py`
- `scripts/python/test_autonomous_trader.py`

```python
MAX_POSITION_SIZE = Decimal('2.0')  # Max per trade
MAX_TOTAL_EXPOSURE = Decimal('10.0')  # Max total
```

### Enable/Disable Strategies

In `continuous_trader.py`, comment out strategies:

```python
# Disable AI prediction (arbitrage only)
def _run_ai_prediction(self):
    return False  # Skip AI

# Disable arbitrage (AI only)
def _scan_arbitrage(self):
    return False  # Skip arbitrage
```

## Error Handling

### Automatic Recovery

The bot automatically:
1. **Catches errors**: Logs traceback, continues running
2. **Cooldown period**: Waits 60s after errors
3. **Max consecutive errors**: Shuts down after 5 in a row
4. **Systemd restart**: Auto-restarts if enabled

### Manual Recovery

If bot stops unexpectedly:

```bash
# Check what happened
tail -100 /tmp/continuous_trader.log

# Check for Python errors
grep -A 10 "ERROR" /tmp/continuous_trader.log

# Restart
./scripts/bash/run-24-7.sh
```

### Common Issues

**Issue: "Bot already running"**
```bash
# Stop existing instance
./scripts/bash/stop-bot.sh

# Then start
./scripts/bash/run-24-7.sh
```

**Issue: "screen: command not found"**
```bash
# Install screen
sudo apt-get install screen
```

**Issue: API rate limits**
```bash
# Increase scan intervals in continuous_trader.py
ARBITRAGE_SCAN_INTERVAL = 60  # Slower
```

**Issue: Out of USDC**
```bash
# Check exposure
./scripts/bash/bot-status.sh

# Close positions manually on Polymarket
# Or increase MAX_TOTAL_EXPOSURE in config
```

## Performance Optimization

### For Speed (More Opportunities)
- Decrease `ARBITRAGE_SCAN_INTERVAL` to 10-15 seconds
- Use systemd with high CPU quota
- Consider WebSocket integration (future)

### For Stability (Fewer Errors)
- Increase scan intervals
- Enable only arbitrage (disable AI)
- Use systemd with resource limits

### For Profitability
- Enable both strategies (arbitrage + AI)
- Tune `MIN_ARBITRAGE_PROFIT_PCT` threshold
- Monitor which strategy performs better

## Production Checklist

Before running 24/7 in production:

- [ ] Test in dry run mode (`DRY_RUN = True`)
- [ ] Verify API keys in `.env`
- [ ] Check USDC balance in wallet
- [ ] Set appropriate position/exposure limits
- [ ] Choose deployment method (screen/systemd)
- [ ] Setup monitoring (logs, alerts)
- [ ] Test graceful shutdown (Ctrl+C)
- [ ] Verify auto-restart works
- [ ] Monitor first 24 hours closely
- [ ] Set up log rotation (if needed)

## Advanced: Log Rotation

Prevent logs from growing indefinitely:

```bash
# Create logrotate config
sudo tee /etc/logrotate.d/polymarket-bot << EOF
/tmp/continuous_trader.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

## Scaling Up

### Multiple Strategies
Run different bots with different configs:

```bash
# Bot 1: Arbitrage only (fast)
screen -dmS arbitrage-bot python scripts/python/hybrid_autonomous_trader.py

# Bot 2: AI only (slow, 2026+)
screen -dmS ai-bot python scripts/python/test_autonomous_trader.py
```

### Multiple Markets
Modify to scan different market categories:

```python
# In hybrid_autonomous_trader.py
markets = self.gamma.get_events(querystring_params={
    "tag": "crypto",  # Focus on crypto
    # or "tag": "politics", "tag": "sports", etc.
})
```

## Summary

**Recommended for beginners:**
```bash
./scripts/bash/run-24-7.sh  # Start
screen -r polymarket-bot     # Monitor
Ctrl+A, D                    # Detach
./scripts/bash/stop-bot.sh   # Stop
```

**Recommended for production:**
```bash
sudo systemctl enable polymarket-bot  # Auto-start
sudo systemctl start polymarket-bot   # Start
sudo journalctl -u polymarket-bot -f  # Monitor
sudo systemctl stop polymarket-bot    # Stop
```

Your bot is now ready to run 24/7! 🚀
