#!/bin/bash
# Stop Polymarket bot (all methods)

echo "🛑 Stopping Polymarket bot..."
echo ""

# Stop screen session
if screen -list | grep -q "polymarket-bot"; then
    echo "Stopping screen session..."
    screen -X -S polymarket-bot quit
    echo "✅ Screen session stopped"
else
    echo "⏭️  No screen session running"
fi

# Stop systemd service
if systemctl is-active --quiet polymarket-bot 2>/dev/null; then
    echo "Stopping systemd service..."
    sudo systemctl stop polymarket-bot
    echo "✅ Systemd service stopped"
else
    echo "⏭️  No systemd service running"
fi

echo ""
echo "✅ Bot stopped"
