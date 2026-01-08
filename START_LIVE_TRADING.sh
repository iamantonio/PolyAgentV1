#!/bin/bash

echo "================================================================================"
echo "🚨 LIVE TRADING MODE - REAL MONEY AT RISK 🚨"
echo "================================================================================"
echo ""
echo "SAFETY LIMITS CONFIGURED:"
echo "  - Max Position Size: \$2.00 per trade"
echo "  - Max Trades/Hour: 3 trades"
echo "  - Daily Loss Limit: \$10.00"
echo "  - Emergency Stop Loss: \$20.00"
echo "  - Min Confidence: 60%"
echo ""
echo "CURRENT STATUS:"
echo "  - Predictions Made: 2 (unvalidated)"
echo "  - Confidence Level: ~60% (bootstrapping)"
echo "  - Target Confidence: 85%"
echo ""
echo "FEATURES ENABLED:"
echo "  ✅ Multi-Agent Reasoning (prevents backwards trades)"
echo "  ✅ Edge Detection (skips unprofitable markets)"
echo "  ✅ Calibration (reduces overconfidence 10-35%)"
echo "  ✅ Kelly Sizing (optimal position sizing)"
echo "  ✅ Discord Alerts (real-time notifications)"
echo ""
echo "RISKS:"
echo "  ⚠️  Only 2 predictions made (no validation yet)"
echo "  ⚠️  Markets haven't resolved (unknown accuracy)"
echo "  ⚠️  Could lose money if predictions wrong"
echo "  ⚠️  Polymarket TOS restrictions apply"
echo ""
echo "================================================================================"
echo "Press Ctrl+C at any time to stop trading"
echo "Scan Interval: 5 minutes"
echo "================================================================================"
echo ""
read -p "Type 'START' to begin live trading: " confirmation

if [ "$confirmation" != "START" ]; then
    echo "❌ Live trading cancelled"
    exit 1
fi

echo ""
echo "🚀 Starting live trading in 3 seconds..."
sleep 1
echo "🚀 Starting live trading in 2 seconds..."
sleep 1
echo "🚀 Starting live trading in 1 second..."
sleep 1
echo ""
echo "💰 LIVE TRADING ACTIVE"
echo "================================================================================"
echo ""

# Run with live trading enabled
cd /home/tony/Dev/agents
.venv/bin/python scripts/python/learning_autonomous_trader.py \
    --live \
    --continuous \
    --interval 300 \
    --max-trades 1
