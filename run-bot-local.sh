#!/bin/bash
# Simple local bot runner
# Runs bot and shows live logs in terminal

PROJECT_ROOT="/home/tony/Dev/agents"
LOG_FILE="/tmp/continuous_trader.log"

echo "🚀 Starting Polymarket Bot..."
echo "Log file: $LOG_FILE"
echo ""
echo "Press Ctrl+C to stop the bot"
echo ""

cd "$PROJECT_ROOT"
source .venv/bin/activate
export PYTHONPATH=.

# Clear old log
> "$LOG_FILE"

# Run bot with live log output
python scripts/python/continuous_trader.py 2>&1 | tee "$LOG_FILE"
