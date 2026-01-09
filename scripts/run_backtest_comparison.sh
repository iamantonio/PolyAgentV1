#!/bin/bash
# Comprehensive backtest comparison script
# Tests multiple exit strategies to find the best one

set -e

echo "================================================================================"
echo "POLYMARKET BOT - EXIT STRATEGY COMPARISON"
echo "================================================================================"
echo ""
echo "This script will test the following exit strategies:"
echo "  1. hold-to-resolution (current strategy)"
echo "  2. take-profit-10 (exit at +10% profit)"
echo "  3. take-profit-20 (exit at +20% profit)"
echo "  4. take-profit-30 (exit at +30% profit)"
echo "  5. stop-loss-10 (exit at -10% loss)"
echo "  6. time-24h (exit after 24 hours)"
echo "  7. time-48h (exit after 48 hours)"
echo ""
echo "================================================================================"
echo ""

# Configuration
START_DATE="2025-10-01"
END_DATE="2026-01-01"
INITIAL_CAPITAL=100.0
STRATEGY="ai-prediction"
MIN_CONFIDENCE=0.2
MAX_POSITION=2.0

# Exit strategies to test
EXIT_STRATEGIES=(
    "hold-to-resolution"
    "take-profit-10"
    "take-profit-20"
    "take-profit-30"
    "stop-loss-10"
    "time-24h"
    "time-48h"
)

# Results file
RESULTS_FILE="data/backtest/comparison_results_$(date +%Y%m%d_%H%M%S).txt"
mkdir -p data/backtest

echo "Results will be saved to: $RESULTS_FILE"
echo ""

# Header
echo "Exit Strategy Comparison - $(date)" > "$RESULTS_FILE"
echo "Start Date: $START_DATE" >> "$RESULTS_FILE"
echo "End Date: $END_DATE" >> "$RESULTS_FILE"
echo "Initial Capital: \$$INITIAL_CAPITAL" >> "$RESULTS_FILE"
echo "Strategy: $STRATEGY" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"
echo "================================================================================" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Run each exit strategy
for exit_strategy in "${EXIT_STRATEGIES[@]}"; do
    echo "================================================================================"
    echo "Testing: $exit_strategy"
    echo "================================================================================"
    echo ""

    echo "Exit Strategy: $exit_strategy" >> "$RESULTS_FILE"
    echo "----------------------------------------" >> "$RESULTS_FILE"

    # Run backtest
    source .venv/bin/activate && python3 -m agents.backtesting.backtest_runner \
        --start-date "$START_DATE" \
        --end-date "$END_DATE" \
        --strategy "$STRATEGY" \
        --exit-strategy "$exit_strategy" \
        --initial-capital "$INITIAL_CAPITAL" \
        --min-confidence "$MIN_CONFIDENCE" \
        --max-position-size "$MAX_POSITION" \
        2>&1 | tee -a "$RESULTS_FILE"

    echo "" >> "$RESULTS_FILE"
    echo "================================================================================" >> "$RESULTS_FILE"
    echo "" >> "$RESULTS_FILE"
    echo ""
done

echo "================================================================================"
echo "BACKTEST COMPARISON COMPLETE"
echo "================================================================================"
echo ""
echo "Results saved to: $RESULTS_FILE"
echo ""
echo "Next steps:"
echo "  1. Review the results file"
echo "  2. Identify the best exit strategy (highest Sharpe + positive PnL)"
echo "  3. Update the live bot configuration"
echo "  4. Monitor live performance vs backtest expectations"
echo ""
echo "Remember: Past performance doesn't guarantee future results!"
echo ""
