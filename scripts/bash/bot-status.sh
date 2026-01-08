#!/bin/bash
# Check Polymarket bot status

echo "📊 POLYMARKET BOT STATUS"
echo "======================================"
echo ""

# Check screen session
if screen -list | grep -q "polymarket-bot"; then
    echo "✅ Screen session: RUNNING"
    echo "   View with: screen -r polymarket-bot"
else
    echo "❌ Screen session: NOT RUNNING"
fi

echo ""

# Check systemd service
if systemctl is-active --quiet polymarket-bot 2>/dev/null; then
    echo "✅ Systemd service: RUNNING"
    echo "   Status: systemctl status polymarket-bot"
    echo "   Logs: journalctl -u polymarket-bot -f"
else
    echo "❌ Systemd service: NOT RUNNING"
fi

echo ""

# Check log file
if [ -f "/tmp/continuous_trader.log" ]; then
    echo "📝 Log file: /tmp/continuous_trader.log"
    echo "   Last 5 entries:"
    tail -5 /tmp/continuous_trader.log | sed 's/^/   /'
else
    echo "⚠️  No log file found"
fi

echo ""

# Check trades
if [ -f "/tmp/hybrid_autonomous_trades.json" ]; then
    trade_count=$(jq '. | length' /tmp/hybrid_autonomous_trades.json 2>/dev/null || echo "0")
    echo "💰 Trades executed: $trade_count"
    echo "   File: /tmp/hybrid_autonomous_trades.json"
fi

if [ -f "/tmp/autonomous_trades.json" ]; then
    trade_count=$(jq '. | length' /tmp/autonomous_trades.json 2>/dev/null || echo "0")
    echo "💰 AI trades: $trade_count"
    echo "   File: /tmp/autonomous_trades.json"
fi

echo ""
echo "======================================"
