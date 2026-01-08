#!/bin/bash

echo "================================================================================"
echo "🖥️  STARTING TRADING DASHBOARD"
echo "================================================================================"
echo ""
echo "Dashboard will be available at:"
echo "  http://localhost:5555"
echo ""
echo "Features:"
echo "  ✅ Real-time stats (total trades, win rate, P&L)"
echo "  ✅ Live charts (P&L timeline, win rate tracker)"
echo "  ✅ Recent trades table"
echo "  ✅ Safety limits monitoring"
echo "  ✅ Edge detection by market type"
echo "  ✅ Auto-refresh every 10 seconds"
echo ""
echo "================================================================================"
echo ""

cd /home/tony/Dev/agents

# Install Flask if needed
.venv/bin/pip install -q flask flask-cors

# Start dashboard API
echo "🚀 Starting dashboard server..."
.venv/bin/python dashboard_api.py
