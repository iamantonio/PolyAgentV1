#!/usr/bin/env python3
"""
Demo: Self-Learning Trading System

Shows how the learning system works:
1. Store predictions with full context
2. Record outcomes when markets resolve
3. Calculate calibration (are we overconfident?)
4. Detect edge (which markets are we good at?)
5. Improve over time

This is the foundation that will make the bot truly intelligent.
"""

import sys
import os

# Setup path
os.chdir('/home/tony/Dev/agents')
sys.path.insert(0, '/home/tony/Dev/agents')

from agents.learning.trade_history import TradeHistoryDB
from agents.learning.calibration import CalibrationTracker

print("=" * 70)
print("SELF-LEARNING TRADING SYSTEM DEMO")
print("=" * 70)
print()

# Initialize learning system
print("📚 Initializing learning system...")
db = TradeHistoryDB(db_path="/tmp/demo_learning.db")
calibration = CalibrationTracker(db)
print("✅ Database initialized")
print()

# Simulate some historical predictions and outcomes
print("=" * 70)
print("SIMULATING HISTORICAL TRADES")
print("=" * 70)
print()

# Market 1: Overconfident prediction (predicted 80%, actually lost)
print("Market 1: Bitcoin reaches $100k?")
pred_id = db.store_prediction(
    market_id="demo_btc_100k",
    question="Will Bitcoin reach $100,000 by end of year?",
    predicted_outcome="Yes",
    predicted_probability=0.80,
    confidence=0.75,
    reasoning="Strong bullish momentum, institutional adoption increasing",
    strategy="AI_PREDICTION",
    market_type="crypto",
    market_prices={"Yes": 0.45, "No": 0.55},
    time_to_close_hours=720,
    features={"sentiment": 0.82, "volume": 1000000}
)
db.record_trade_execution(pred_id, trade_size_usdc=2.0, trade_price=0.45, execution_result="EXECUTED")
print(f"  Predicted: Yes (80% confident)")
print(f"  Trade: Bought YES at $0.45 for $2.00")

# Resolve: Actually NO
db.record_outcome("demo_btc_100k", actual_outcome="No")
print(f"  ❌ RESULT: No (we were WRONG)")
print(f"  P&L: -$2.00")
print()

# Market 2: Well-calibrated prediction (predicted 60%, won)
print("Market 2: Fed cuts rates?")
pred_id = db.store_prediction(
    market_id="demo_fed_rates",
    question="Will the Fed cut rates in December?",
    predicted_outcome="Yes",
    predicted_probability=0.65,
    confidence=0.60,
    reasoning="Inflation cooling, labor market softening",
    strategy="AI_PREDICTION",
    market_type="politics",
    market_prices={"Yes": 0.55, "No": 0.45},
    time_to_close_hours=168,
    features={"sentiment": 0.65, "volume": 500000}
)
db.record_trade_execution(pred_id, trade_size_usdc=1.5, trade_price=0.55, execution_result="EXECUTED")
print(f"  Predicted: Yes (65% probability)")
print(f"  Trade: Bought YES at $0.55 for $1.50")

# Resolve: YES
db.record_outcome("demo_fed_rates", actual_outcome="Yes")
print(f"  ✅ RESULT: Yes (we were RIGHT)")
print(f"  P&L: +$1.23")
print()

# Market 3: Underconfident (predicted 55%, won - should have been more confident)
print("Market 3: Trump wins election?")
pred_id = db.store_prediction(
    market_id="demo_election",
    question="Will Trump win 2024 election?",
    predicted_outcome="Yes",
    predicted_probability=0.55,
    confidence=0.50,
    reasoning="Polling shows tight race",
    strategy="AI_PREDICTION",
    market_type="politics",
    market_prices={"Yes": 0.48, "No": 0.52},
    time_to_close_hours=2400,
    features={"sentiment": 0.60, "volume": 5000000}
)
db.record_trade_execution(pred_id, trade_size_usdc=1.0, trade_price=0.48, execution_result="EXECUTED")
print(f"  Predicted: Yes (55% probability)")
print(f"  Trade: Bought YES at $0.48 for $1.00")

# Resolve: YES
db.record_outcome("demo_election", actual_outcome="Yes")
print(f"  ✅ RESULT: Yes (we were RIGHT, but underconfident)")
print(f"  P&L: +$1.08")
print()

# Market 4: Another overconfident loss
print("Market 4: ETH reaches $5k?")
pred_id = db.store_prediction(
    market_id="demo_eth_5k",
    question="Will Ethereum reach $5,000?",
    predicted_outcome="Yes",
    predicted_probability=0.75,
    confidence=0.70,
    reasoning="Strong technical setup, ETF approval expected",
    strategy="AI_PREDICTION",
    market_type="crypto",
    market_prices={"Yes": 0.40, "No": 0.60},
    time_to_close_hours=480,
    features={"sentiment": 0.78, "volume": 800000}
)
db.record_trade_execution(pred_id, trade_size_usdc=2.0, trade_price=0.40, execution_result="EXECUTED")
print(f"  Predicted: Yes (75% confident)")
print(f"  Trade: Bought YES at $0.40 for $2.00")

# Resolve: NO
db.record_outcome("demo_eth_5k", actual_outcome="No")
print(f"  ❌ RESULT: No (we were WRONG)")
print(f"  P&L: -$2.00")
print()

# Now analyze the results
print("=" * 70)
print("LEARNING SYSTEM ANALYSIS")
print("=" * 70)
print()

# Performance summary
print("📊 PERFORMANCE SUMMARY")
print("-" * 70)
summary = db.get_performance_summary(days=365)
print(f"Total Predictions: {summary['total_predictions']}")
print(f"Trades Executed: {summary['trades_executed']}")
print(f"Resolved Markets: {summary['resolved_markets']}")
print(f"Win Rate: {summary['win_rate']:.1%}")
print(f"Total P&L: ${summary['total_pnl_usdc']:.2f}")
print(f"Brier Score: {summary['brier_score']:.4f}")
print()

# Calibration report
print("📈 " + calibration.generate_report())
print()

# Edge detection by market type
print("🎯 EDGE DETECTION BY MARKET TYPE")
print("-" * 70)
edge_by_type = db.get_edge_by_market_type()
for market_type, stats in edge_by_type.items():
    edge_symbol = "✅" if stats['has_edge'] else "❌"
    print(f"{edge_symbol} {market_type.upper()}:")
    print(f"   Win Rate: {stats['win_rate']:.1%}")
    print(f"   Avg P&L: ${stats['avg_pnl_per_trade']:.2f}")
    print(f"   Total Trades: {stats['total_trades']}")
    print()

# Calibrated confidence example
print("🎓 CONFIDENCE CALIBRATION IN ACTION")
print("-" * 70)
print("If we make a new prediction with 80% confidence...")
raw_confidence = 0.80
calibrated = calibration.calibrate_confidence(raw_confidence, market_type="crypto")
print(f"  Raw Confidence: {raw_confidence:.1%}")
print(f"  Calibrated Confidence: {calibrated:.1%}")
print(f"  Adjustment: {(calibrated - raw_confidence):+.1%}")
print()
print("Why? Because historically when we say 80%, we're often overconfident.")
print("The system learns to adjust based on actual outcomes.")
print()

# Should we trade decision
print("🤔 SHOULD WE TRADE DECISION")
print("-" * 70)
print("New crypto market: 70% confident, 10% estimated edge")
should_trade, reason = calibration.should_trade(
    confidence=0.70,
    edge_estimate=0.10,
    market_type="crypto",
    min_confidence=0.60,
    min_edge=0.05
)
print(f"  Decision: {'SKIP' if not should_trade else 'TRADE'}")
print(f"  Reason: {reason}")
print()

# Kelly position sizing
print("💰 KELLY CRITERION POSITION SIZING")
print("-" * 70)
probability = 0.65
market_price = 0.50
bankroll = 100.0
bet_size = calibration.get_optimal_bet_size(probability, market_price, bankroll, kelly_fraction=0.25)
print(f"  Our Probability: {probability:.1%}")
print(f"  Market Price: ${market_price}")
print(f"  Bankroll: ${bankroll}")
print(f"  Optimal Bet Size: ${bet_size:.2f}")
print(f"  (Using 1/4 Kelly for safety)")
print()

# Key insights
print("=" * 70)
print("KEY INSIGHTS - THIS IS A LEARNING SYSTEM")
print("=" * 70)
print()
print("✅ Tracks every prediction and outcome")
print("✅ Measures calibration (are we overconfident?)")
print("✅ Detects edge by market type (where are we good?)")
print("✅ Adjusts confidence based on historical performance")
print("✅ Sizes positions using Kelly Criterion")
print("✅ Decides when to skip (no edge detected)")
print()
print("🚀 THIS GETS BETTER OVER TIME")
print("   - More trades = better calibration")
print("   - More data = better edge detection")
print("   - Pattern recognition improves")
print("   - System learns its strengths and weaknesses")
print()
print("=" * 70)
print()

# Close database
db.close()

print("Demo complete! Database saved to: /tmp/demo_learning.db")
print("Run this script again to see how the system continues learning.")
print()
