#!/usr/bin/env python3
"""
Calculate P&L from dry run trades.
Shows hypothetical performance if all trades were executed.
"""

import json
from decimal import Decimal

AI_TRADES_FILE = '/tmp/autonomous_trades.json'
ARB_TRADES_FILE = '/tmp/hybrid_autonomous_trades.json'

print("=" * 70)
print("DRY RUN P&L CALCULATOR")
print("=" * 70)
print()

# Load both trade files
all_trades = []

try:
    with open(AI_TRADES_FILE, 'r') as f:
        ai_trades = json.load(f)
        for trade in ai_trades:
            trade['strategy'] = 'AI_PREDICTION'
        all_trades.extend(ai_trades)
        print(f"📊 Loaded {len(ai_trades)} AI prediction trades")
except FileNotFoundError:
    print("⚠️  No AI trades file found")

try:
    with open(ARB_TRADES_FILE, 'r') as f:
        arb_trades = json.load(f)
        for trade in arb_trades:
            trade['strategy'] = trade.get('strategy', 'ARBITRAGE')
        all_trades.extend(arb_trades)
        print(f"📊 Loaded {len(arb_trades)} arbitrage trades")
except FileNotFoundError:
    print("⚠️  No arbitrage trades file found")

trades = all_trades

if not trades:
    print("📭 No trades found in either file.")
    exit(0)

print(f"📊 Total: {len(trades)} trades")
print()

if not trades:
    print("📭 No trades logged yet.")
    exit(0)

print(f"📊 Analyzing {len(trades)} dry run trades...")
print()

# Track totals
total_invested = Decimal('0')
total_max_profit = Decimal('0')
total_max_loss = Decimal('0')
total_guaranteed_profit = Decimal('0')
trade_count = 0
arb_count = 0
ai_count = 0

# Display each trade
for i, trade in enumerate(trades, 1):
    if not trade.get('dry_run'):
        continue  # Skip live trades

    trade_count += 1
    strategy = trade.get('strategy', 'UNKNOWN')

    print(f"\nTrade #{i} [{strategy}]:")
    print(f"  Market: {trade.get('market_question', 'Unknown')[:60]}")

    size = Decimal(str(trade.get('size_usdc', 0)))
    total_invested += size

    # Handle arbitrage trades (guaranteed profit)
    if 'guaranteed_profit_usd' in trade:
        arb_count += 1
        guaranteed_profit = Decimal(str(trade['guaranteed_profit_usd']))
        roi = float(trade.get('roi_pct', 0))

        print(f"  Type: ARBITRAGE")
        print(f"  Size: ${size:.2f}")
        print(f"  Guaranteed Profit: +${guaranteed_profit:.2f} ({roi:.2f}%)")

        total_guaranteed_profit += guaranteed_profit

    # Handle AI prediction trades (uncertain outcome)
    elif 'max_profit_usd' in trade and 'max_loss_usd' in trade:
        ai_count += 1
        max_profit = Decimal(str(trade['max_profit_usd']))
        max_loss = Decimal(str(trade['max_loss_usd']))

        print(f"  Type: AI PREDICTION")
        print(f"  Outcome: {trade.get('outcome', 'Unknown')}")
        print(f"  Entry: ${trade.get('entry_price', 0):.4f}")
        print(f"  Size: ${size:.2f}")
        print(f"  If WIN: +${max_profit:.2f} ({float(max_profit/size*100):.1f}%)")
        print(f"  If LOSE: -${max_loss:.2f} ({float(max_loss/size*100):.1f}%)")

        total_max_profit += max_profit
        total_max_loss += max_loss

print()
print("=" * 70)
print("PORTFOLIO SUMMARY")
print("=" * 70)
print()

if trade_count == 0:
    print("No dry run trades to analyze.")
else:
    print(f"Total Trades: {trade_count}")
    print(f"  - Arbitrage: {arb_count}")
    print(f"  - AI Prediction: {ai_count}")
    print(f"Total Invested: ${total_invested:.2f}")
    print()

    # ARBITRAGE SECTION (Risk-Free)
    if arb_count > 0:
        print(f"💰 ARBITRAGE (Risk-Free):")
        print(f"   Total Profit: +${total_guaranteed_profit:.2f}")
        arb_roi = float(total_guaranteed_profit / total_invested * 100) if total_invested > 0 else 0
        print(f"   ROI: {arb_roi:.2f}%")
        print()

    # AI PREDICTION SECTION (Uncertain)
    if ai_count > 0:
        print(f"🎲 AI PREDICTION (Uncertain):")
        print()

        print(f"📈 Best Case (all AI trades win):")
        print(f"   Profit: +${total_max_profit:.2f}")
        ai_best_roi = float(total_max_profit / total_invested * 100) if total_invested > 0 else 0
        print(f"   ROI: {ai_best_roi:.1f}%")
        print()

        print(f"📉 Worst Case (all AI trades lose):")
        print(f"   Loss: -${total_max_loss:.2f}")
        ai_worst_roi = float(-total_max_loss / total_invested * 100) if total_invested > 0 else 0
        print(f"   ROI: {ai_worst_roi:.1f}%")
        print()

        # Calculate breakeven win rate for AI trades only
        if total_max_profit > 0 and total_max_loss > 0:
            avg_win = total_max_profit / ai_count
            avg_loss = total_max_loss / ai_count

            # Breakeven: (win_rate * avg_win) - ((1-win_rate) * avg_loss) = 0
            breakeven_rate = float(avg_loss / (avg_win + avg_loss)) * 100

            print(f"⚖️  AI Breakeven Analysis:")
            print(f"   Need win rate: {breakeven_rate:.1f}%")
            print(f"   (For AI trades to break even)")
            print()

            # Expected value at different win rates (AI trades only)
            print(f"📊 AI Expected Value by Win Rate:")
            for win_rate in [40, 50, 55, 60, 70]:
                ev_win = (win_rate / 100) * total_max_profit
                ev_loss = ((100 - win_rate) / 100) * total_max_loss
                ev_total = ev_win - ev_loss
                ev_roi = float(ev_total / total_invested * 100) if total_invested > 0 else 0

                status = "✅" if ev_total > 0 else "❌"
                print(f"   {win_rate}% win rate: {status} ${ev_total:.2f} ({ev_roi:+.1f}%)")
            print()

    # COMBINED PORTFOLIO
    if arb_count > 0 and ai_count > 0:
        print(f"🎯 COMBINED PORTFOLIO:")
        print(f"   Guaranteed (Arb): +${total_guaranteed_profit:.2f}")
        print(f"   Best Case (Arb + AI wins): +${total_guaranteed_profit + total_max_profit:.2f}")
        print(f"   Worst Case (Arb - AI losses): ${total_guaranteed_profit - total_max_loss:+.2f}")
        print()

print()
print("=" * 70)
print()
print("💡 To track actual results:")
print("   1. Wait for markets to resolve")
print("   2. Manually check which outcomes won")
print("   3. Calculate realized P&L")
print()
