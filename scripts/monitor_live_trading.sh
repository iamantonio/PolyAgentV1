#!/bin/bash
# Live Trading Health Check Monitor
# Run this daily (or set up as cron job) to monitor bot health

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  🤖 POLYMARKET BOT - LIVE TRADING HEALTH CHECK"
echo "════════════════════════════════════════════════════════════════"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if bot is running
echo "─────────────────────────────────────────────────────────────────"
echo "📊 BOT STATUS"
echo "─────────────────────────────────────────────────────────────────"
if pgrep -f learning_autonomous_trader.py > /dev/null; then
    echo -e "${GREEN}✅ Bot is RUNNING${NC}"
    PID=$(pgrep -f learning_autonomous_trader.py)
    echo "   Process ID: $PID"
    echo "   Uptime: $(ps -p $PID -o etime= | xargs)"
else
    echo -e "${RED}❌ Bot is NOT RUNNING${NC}"
    echo "   Start with: .venv/bin/python scripts/python/learning_autonomous_trader.py"
fi
echo

# Check trade log
echo "─────────────────────────────────────────────────────────────────"
echo "📈 RECENT TRADING ACTIVITY"
echo "─────────────────────────────────────────────────────────────────"

TRADE_LOG="data/trades/trade_log.json"
if [ -f "$TRADE_LOG" ]; then
    TRADE_COUNT=$(wc -l < "$TRADE_LOG")
    echo "Total trades executed: $TRADE_COUNT"

    if [ $TRADE_COUNT -gt 0 ]; then
        echo
        echo "Last 5 trades:"
        tail -5 "$TRADE_LOG" | python3 -c '
import sys
import json
for line in sys.stdin:
    try:
        trade = json.loads(line.strip())
        outcome = trade.get("outcome", "?")
        pnl = trade.get("pnl", 0)
        win = trade.get("win", False)
        status = "✅ WIN" if win else "❌ LOSS"
        print(f"  {status} | {outcome} | PnL: ${pnl:.2f}")
    except:
        continue
' || echo "  (Error parsing trade log)"
    fi
else
    echo -e "${YELLOW}⚠️  No trades executed yet${NC}"
    echo "   Trade log will be created at: $TRADE_LOG"
fi
echo

# Calculate win rate (if enough trades)
echo "─────────────────────────────────────────────────────────────────"
echo "🎯 PERFORMANCE METRICS"
echo "─────────────────────────────────────────────────────────────────"

if [ -f "$TRADE_LOG" ] && [ $(wc -l < "$TRADE_LOG") -ge 5 ]; then
    python3 << 'PYEOF'
import json
import sys

trades = []
try:
    with open("data/trades/trade_log.json", "r") as f:
        for line in f:
            try:
                trades.append(json.loads(line.strip()))
            except:
                continue
except:
    print("Error reading trade log")
    sys.exit(0)

if len(trades) == 0:
    print("No trades to analyze")
    sys.exit(0)

# Calculate metrics
total_trades = len(trades)
winning_trades = sum(1 for t in trades if t.get("win", False))
losing_trades = total_trades - winning_trades
win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

total_pnl = sum(t.get("pnl", 0) for t in trades)
avg_win = sum(t.get("pnl", 0) for t in trades if t.get("win", False)) / winning_trades if winning_trades > 0 else 0
avg_loss = sum(t.get("pnl", 0) for t in trades if not t.get("win", False)) / losing_trades if losing_trades > 0 else 0

print(f"Total Trades: {total_trades}")
print(f"Win Rate: {win_rate:.1f}% ({winning_trades}W / {losing_trades}L)")
print(f"Total PnL: ${total_pnl:.2f}")
print(f"Avg Win: ${avg_win:.2f}")
print(f"Avg Loss: ${avg_loss:.2f}")

# Health assessment
print()
if win_rate >= 55 and total_pnl > 0:
    print("🟢 Status: HEALTHY - Strategy showing positive edge")
elif win_rate >= 45 and total_pnl >= -10:
    print("🟡 Status: BORDERLINE - Monitor closely")
else:
    print("🔴 Status: WARNING - Consider stopping")
PYEOF
else
    echo -e "${YELLOW}⚠️  Not enough trades yet (need 5+ for stats)${NC}"
fi
echo

# Check error logs
echo "─────────────────────────────────────────────────────────────────"
echo "🚨 ERROR LOG (last 10 errors)"
echo "─────────────────────────────────────────────────────────────────"

ERROR_LOG="logs/bot_errors.log"
if [ -f "$ERROR_LOG" ]; then
    ERROR_COUNT=$(wc -l < "$ERROR_LOG")
    if [ $ERROR_COUNT -gt 0 ]; then
        echo "Total errors: $ERROR_COUNT"
        echo
        tail -10 "$ERROR_LOG" | head -10 || echo "(No recent errors)"
    else
        echo -e "${GREEN}✅ No errors logged${NC}"
    fi
else
    echo -e "${GREEN}✅ No error log (clean run)${NC}"
fi
echo

# Budget check
echo "─────────────────────────────────────────────────────────────────"
echo "💸 BUDGET STATUS"
echo "─────────────────────────────────────────────────────────────────"
source .env 2>/dev/null || true
echo "Daily limit: $DAILY_BUDGET_USD"
echo "Hourly limit: $HOURLY_BUDGET_USD"
echo "Max calls/hour: $MAX_CALLS_PER_HOUR"
echo
echo "(Add budget tracking to see actual spend)"
echo

# Risk controls
echo "─────────────────────────────────────────────────────────────────"
echo "🛡️  RISK CONTROLS"
echo "─────────────────────────────────────────────────────────────────"
echo "Max position size: $MAX_POSITION_SIZE_USD"
echo "Min confidence: ${MIN_CONFIDENCE}%"
echo "Max daily trades: $MAX_DAILY_TRADES"
echo "Min liquidity: \$$MIN_LIQUIDITY"
echo

# Kill switch instructions
echo "─────────────────────────────────────────────────────────────────"
echo "🚨 EMERGENCY STOP"
echo "─────────────────────────────────────────────────────────────────"
echo "To stop trading immediately:"
echo "  pkill -f learning_autonomous_trader.py"
echo
echo "To view live logs:"
echo "  tail -f logs/live_trading.log"
echo

echo "════════════════════════════════════════════════════════════════"
echo "  End of health check - $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════════"
