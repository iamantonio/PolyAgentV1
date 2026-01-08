# Trading Dashboard - Quick Start

Professional real-time monitoring dashboard for your Polymarket trading bot.

## Features

✅ **Real-Time Statistics**
- Total trades, win rate, P&L, confidence tracking
- Auto-refreshes every 10 seconds

✅ **Safety Limits Monitoring**
- Exposure cap (50% of bankroll) with visual indicators
- Trades per hour tracking
- Daily P&L loss limits

✅ **Live Charts**
- Cumulative P&L over time
- Rolling 10-trade win rate

✅ **Recent Trades Table**
- Last 20 trades with full details
- Color-coded outcomes (WIN/LOSS/OPEN)
- Prediction confidence and position sizes

## Installation

### 1. Install Flask (if not already installed)

```bash
cd /home/tony/Dev/agents
source .venv/bin/activate
pip install flask flask-cors
```

### 2. Ensure Database Exists

The dashboard reads from `/tmp/learning_trader.db`. Make sure your bot has run at least once to create the database:

```bash
python scripts/python/learning_autonomous_trader.py
```

## Usage

### Start the Dashboard Server

In one terminal:

```bash
cd /home/tony/Dev/agents
source .venv/bin/activate
python dashboard_server.py
```

You should see:

```
================================================================================
TRADING DASHBOARD SERVER
================================================================================
Database: /tmp/learning_trader.db
Server: http://localhost:5555
Dashboard: http://localhost:5555
```

### Open Dashboard in Browser

Navigate to:

```
http://localhost:5555
```

The dashboard will automatically:
- Load current stats
- Display safety limit status
- Show P&L and win rate charts
- List recent trades
- Refresh every 10 seconds

## Dashboard Layout

### Header
- System status indicator (animated green dot when active)
- Last update timestamp

### Stats Cards (Top Row)
- **Total Trades**: Number of predictions made + open positions
- **Win Rate**: Percentage with W/L breakdown
- **Total P&L**: Lifetime profit/loss (green if positive, red if negative)
- **Avg Confidence**: Average model confidence across all trades

### Safety Limits (Second Row)

Each limit shows:
- Current value vs limit
- Progress bar (green → amber → red)
- Status badge (SAFE / WARNING / DANGER)

**Exposure Cap**
- Current: Amount deployed in open positions
- Limit: 50% of bankroll ($50 on $100 bankroll)
- Color: Green (<70%), Amber (70-90%), Red (>90%)

**Trades/Hour**
- Current: Trades in last 60 minutes
- Limit: 20 (configurable in dashboard_server.py)

**Daily P&L**
- Current: Today's profit/loss
- Stop: Daily loss limit (-$10.00 default)

### Charts
- **Cumulative P&L**: Total profit/loss over time
- **Win Rate**: Rolling 10-trade average (min 10 trades required)

### Recent Trades Table
- Last 20 trades
- Market question (truncated to 60 chars)
- Prediction (YES/NO badge)
- Confidence percentage
- Position size (USDC)
- Outcome (WIN/LOSS/OPEN)
- P&L per trade
- Timestamp

## Customization

### Change Safety Limits

Edit `dashboard_server.py`:

```python
# Line 84: Bankroll
BANKROLL = 100.0  # Match your actual bankroll

# Line 85: Max exposure percentage
MAX_EXPOSURE_PCT = 0.50  # 50% cap

# Line 101: Trades per hour limit
'limit': 20  # Adjust hourly rate limit

# Line 111: Daily loss limit
'limit': -10.0  # Adjust daily stop-loss
```

### Change Refresh Rate

Edit `dashboard.html` line 840:

```javascript
setInterval(async () => {
    // ...
}, 10000);  // Change from 10000ms (10s) to desired interval
```

## Troubleshooting

### Error: "Database not found"

The database is created when the bot runs. Either:

1. Run the bot once:
   ```bash
   python scripts/python/learning_autonomous_trader.py
   ```

2. Or create an empty database:
   ```bash
   python -c "import sqlite3; sqlite3.connect('/tmp/learning_trader.db').close()"
   ```

### Error: "Failed to fetch status data"

Check that:
1. Dashboard server is running on port 5555
2. No firewall blocking localhost:5555
3. Database file exists and is readable

### Charts Not Showing

Requires at least:
- **P&L Chart**: 1 resolved trade
- **Win Rate Chart**: 10 resolved trades

### Blank Dashboard

If all values show `--`:
- Check database has data: `sqlite3 /tmp/learning_trader.db "SELECT COUNT(*) FROM predictions;"`
- Verify API endpoints: Visit `http://localhost:5555/api/status` in browser
- Check browser console for JavaScript errors (F12)

## Running Both Bot and Dashboard

### Option 1: Two Terminals

Terminal 1 (Bot):
```bash
cd /home/tony/Dev/agents
source .venv/bin/activate
python scripts/python/learning_autonomous_trader.py
```

Terminal 2 (Dashboard):
```bash
cd /home/tony/Dev/agents
source .venv/bin/activate
python dashboard_server.py
```

### Option 2: Background Process

```bash
# Start dashboard in background
cd /home/tony/Dev/agents
source .venv/bin/activate
nohup python dashboard_server.py > dashboard.log 2>&1 &

# Start bot in foreground
python scripts/python/learning_autonomous_trader.py

# To stop dashboard later:
pkill -f dashboard_server.py
```

### Option 3: tmux/screen (Recommended)

```bash
# Start tmux
tmux new -s trading

# Window 1: Dashboard
python dashboard_server.py

# Create new window (Ctrl+B, C)
# Window 2: Bot
python scripts/python/learning_autonomous_trader.py

# Switch windows: Ctrl+B, N (next) or P (previous)
# Detach: Ctrl+B, D
# Reattach: tmux attach -t trading
```

## API Endpoints

The dashboard server exposes these endpoints:

- `GET /` - Serve dashboard HTML
- `GET /api/status` - Overall stats (trades, win rate, P&L, etc.)
- `GET /api/safety_limits` - Safety limit status
- `GET /api/recent_trades` - Last 20 trades
- `GET /api/pnl_history` - Cumulative P&L data for chart
- `GET /api/win_rate_history` - Win rate over time for chart

All endpoints return JSON except `/`.

## Security Notes

⚠️ **Important**: This dashboard is for **LOCAL USE ONLY**

- Server binds to `0.0.0.0` (all interfaces) for flexibility
- **DO NOT** expose port 5555 to the internet
- **DO NOT** run on public servers without authentication
- Contains sensitive trading data

For remote access, use SSH port forwarding:

```bash
# On remote server
python dashboard_server.py

# On local machine
ssh -L 5555:localhost:5555 user@remote-server

# Then open http://localhost:5555 locally
```

## Color Coding

**Green**: Profits, wins, safe limits
**Red**: Losses, danger limits
**Cyan/Blue**: Neutral stats, open positions
**Amber/Yellow**: Warning limits (70-90%)

## Files

- `dashboard_server.py` - Flask backend (REST API)
- `dashboard.html` - Frontend (auto-served by Flask)
- `/tmp/learning_trader.db` - SQLite database (created by bot)

---

**Tip**: Keep the dashboard open while the bot trades to monitor:
1. Exposure approaching 50% cap
2. Any duplicate trade alerts (dedupe system)
3. Win rate trends
4. P&L performance

If you see exposure hit 90%+ (amber/red), trades will be automatically reduced or skipped until positions close.
