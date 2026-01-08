#!/bin/bash
# Run Polymarket bot 24/7 using screen
# Screen allows detaching/reattaching to monitor the bot

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

# Check if screen is installed
if ! command -v screen &> /dev/null; then
    echo "❌ screen is not installed"
    echo "Install with: sudo apt-get install screen"
    exit 1
fi

# Check if already running
if screen -list | grep -q "polymarket-bot"; then
    echo "⚠️  Bot is already running in screen session 'polymarket-bot'"
    echo ""
    echo "To view:   screen -r polymarket-bot"
    echo "To stop:   screen -X -S polymarket-bot quit"
    exit 0
fi

echo "🚀 Starting Polymarket bot in screen session..."
echo ""
echo "Commands:"
echo "  View:    screen -r polymarket-bot"
echo "  Detach:  Ctrl+A, then D"
echo "  Stop:    screen -X -S polymarket-bot quit"
echo ""

# Start in screen session
screen -dmS polymarket-bot bash -c "
    cd $PROJECT_ROOT
    source .venv/bin/activate
    export PYTHONPATH=.
    python scripts/python/continuous_trader.py
"

sleep 2

echo "✅ Bot started successfully!"
echo ""
echo "Monitor with: screen -r polymarket-bot"
echo "Logs: tail -f /tmp/continuous_trader.log"
