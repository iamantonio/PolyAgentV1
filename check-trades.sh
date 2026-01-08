#!/bin/bash
# Quick trades checker

ARBITRAGE_TRADES="/tmp/hybrid_autonomous_trades.json"
AI_TRADES="/tmp/autonomous_trades.json"
LOG_FILE="/tmp/continuous_trader.log"

echo "═══════════════════════════════════════════════════════"
echo "  POLYMARKET BOT - TRADE SUMMARY"
echo "═══════════════════════════════════════════════════════"
echo ""

# Arbitrage trades
if [ -f "$ARBITRAGE_TRADES" ]; then
    arb_count=$(jq '. | length' "$ARBITRAGE_TRADES" 2>/dev/null || echo "0")
    echo "🔄 Arbitrage Trades: $arb_count"

    if [ "$arb_count" -gt 0 ]; then
        echo ""
        echo "Latest arbitrage trade:"
        jq -r '.[-1] | "  Market: \(.market_question)\n  Type: \(.opportunity_type)\n  Profit: \(.expected_profit_pct)%\n  Size: $\(.size_usdc)\n  Time: \(.timestamp)\n  Status: \(.status)"' "$ARBITRAGE_TRADES" 2>/dev/null
    fi
else
    echo "🔄 Arbitrage Trades: 0 (no file yet)"
fi

echo ""
echo "───────────────────────────────────────────────────────"
echo ""

# AI trades
if [ -f "$AI_TRADES" ]; then
    ai_count=$(jq '. | length' "$AI_TRADES" 2>/dev/null || echo "0")
    echo "🤖 AI Prediction Trades: $ai_count"

    if [ "$ai_count" -gt 0 ]; then
        echo ""
        echo "Latest AI trade:"
        jq -r '.[-1] | "  Market: \(.market_question)\n  Side: \(.side)\n  Confidence: \(.grok_confidence)\n  Size: $\(.size_usdc)\n  Time: \(.timestamp)\n  Status: \(.status)"' "$AI_TRADES" 2>/dev/null
    fi
else
    echo "🤖 AI Prediction Trades: 0 (no file yet)"
fi

echo ""
echo "───────────────────────────────────────────────────────"
echo ""

# Recent log
if [ -f "$LOG_FILE" ]; then
    echo "📋 Last 5 log entries:"
    tail -5 "$LOG_FILE" | sed 's/^/  /'
else
    echo "📋 No log file found"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Commands:"
echo "  View all trades: cat $ARBITRAGE_TRADES | jq '.'"
echo "  View live logs:  tail -f $LOG_FILE"
echo "  Start bot:       ./run-bot-local.sh"
echo ""
