"""
Hybrid Autonomous Polymarket Trading Bot

Combines multiple proven strategies for maximum profitability.
Based on research showing $40M+ extracted via arbitrage in 2024-2025.
"""

import os
import sys
import json
import ast
from datetime import datetime
from decimal import Decimal

os.chdir('/home/tony/Dev/agents')
sys.path.insert(0, '/home/tony/Dev/agents')

from agents.polymarket.polymarket import Polymarket
from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.application.executor import Executor
from agents.connectors.lunarcrush import LunarCrush
from agents.strategies.arbitrage import ArbitrageDetector

# SAFETY LIMITS
MAX_POSITION_SIZE = Decimal('2.0')
MAX_TOTAL_EXPOSURE = Decimal('10.0')
TRADES_LOG = '/tmp/hybrid_autonomous_trades.json'

# STRATEGY CONFIGURATION
ENABLE_ARBITRAGE = True
MIN_ARBITRAGE_PROFIT_PCT = 1.5

DRY_RUN = True  # TESTING MODE - NO REAL TRADES


class HybridAutonomousTrader:
    """Hybrid trading bot with arbitrage priority."""

    def __init__(self):
        self.polymarket = Polymarket()
        self.gamma = Gamma()
        self.arbitrage_detector = ArbitrageDetector(
            min_profit_pct=MIN_ARBITRAGE_PROFIT_PCT
        )
        self.trades_history = self.load_trades_history()

    def load_trades_history(self):
        try:
            with open(TRADES_LOG, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_trade(self, trade_data):
        self.trades_history.append(trade_data)
        with open(TRADES_LOG, 'w') as f:
            json.dump(self.trades_history, f, indent=2, default=str)

    def get_total_exposure(self):
        total = Decimal('0')
        for trade in self.trades_history:
            if trade.get('status') == 'open':
                total += Decimal(str(trade['size_usdc']))
        return total

    def _get_token_id_for_outcome(self, market, outcome_name):
        """Get token ID for a specific outcome from market data."""
        try:
            outcomes_raw = market.get('outcomes', '[]')
            token_ids_raw = market.get('clobTokenIds', '[]')

            outcomes_list = ast.literal_eval(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
            token_ids_list = ast.literal_eval(token_ids_raw) if isinstance(token_ids_raw, str) else token_ids_raw

            # Find index of outcome
            for i, outcome in enumerate(outcomes_list):
                if outcome.lower() == outcome_name.lower() or outcome == outcome_name:
                    return token_ids_list[i]

            # Fallback: if outcome is "YES" or "NO", use index
            if outcome_name.upper() == "YES":
                return token_ids_list[0]
            elif outcome_name.upper() == "NO":
                return token_ids_list[1]

            return None
        except Exception as e:
            print(f"Error getting token ID: {e}")
            return None

    def _execute_binary_arbitrage(self, opp, market):
        """Execute binary arbitrage: buy YES and NO simultaneously."""
        print(f"\n🔄 Executing BINARY arbitrage...")

        # Get token IDs for YES and NO
        yes_token = self._get_token_id_for_outcome(market, "YES")
        no_token = self._get_token_id_for_outcome(market, "NO")

        if not yes_token or not no_token:
            print("❌ Could not find token IDs for YES/NO outcomes")
            return None

        # Calculate position size (respecting limits)
        current_exposure = self.get_total_exposure()
        available = float(MAX_TOTAL_EXPOSURE - current_exposure)

        # For binary arbitrage, we need to buy both YES and NO
        # Total cost is sum of both prices
        position_size = min(float(opp.total_cost), available, float(MAX_POSITION_SIZE))

        if position_size < 0.01:
            print(f"⚠️ Position size too small: ${position_size:.2f}")
            return None

        print(f"Position size: ${position_size:.2f}")
        print(f"YES token: {yes_token}")
        print(f"NO token: {no_token}")

        results = []

        # Execute YES order
        try:
            yes_trade = opp.trades[0]  # First trade is YES
            yes_price = yes_trade['price']
            yes_amount = position_size / (yes_price + opp.trades[1]['price'])  # Proportional split

            if not DRY_RUN:
                from py_clob_client.clob_types import MarketOrderArgs, OrderType

                print(f"🔵 Buying YES @ ${yes_price:.4f} for {yes_amount:.2f} shares")
                order_args = MarketOrderArgs(
                    token_id=yes_token,
                    amount=yes_amount,
                    side="BUY"
                )
                signed_order = self.polymarket.client.create_market_order(order_args)
                result = self.polymarket.client.post_order(signed_order, OrderType.FOK)
                results.append({"outcome": "YES", "result": result})
                print(f"✅ YES order executed: {result.get('orderID', 'unknown')}")
            else:
                results.append({"outcome": "YES", "result": "DRY_RUN"})
                print(f"🔵 DRY RUN: Would buy YES @ ${yes_price:.4f} for {yes_amount:.2f} shares")

        except Exception as e:
            print(f"❌ YES order failed: {e}")
            return None

        # Execute NO order
        try:
            no_trade = opp.trades[1]  # Second trade is NO
            no_price = no_trade['price']
            no_amount = position_size / (yes_price + no_price)  # Same shares for both

            if not DRY_RUN:
                from py_clob_client.clob_types import MarketOrderArgs, OrderType

                print(f"🔴 Buying NO @ ${no_price:.4f} for {no_amount:.2f} shares")
                order_args = MarketOrderArgs(
                    token_id=no_token,
                    amount=no_amount,
                    side="BUY"
                )
                signed_order = self.polymarket.client.create_market_order(order_args)
                result = self.polymarket.client.post_order(signed_order, OrderType.FOK)
                results.append({"outcome": "NO", "result": result})
                print(f"✅ NO order executed: {result.get('orderID', 'unknown')}")
            else:
                results.append({"outcome": "NO", "result": "DRY_RUN"})
                print(f"🔴 DRY RUN: Would buy NO @ ${no_price:.4f} for {no_amount:.2f} shares")

        except Exception as e:
            print(f"❌ NO order failed: {e}")
            # TODO: Should we try to reverse YES order here?
            return None

        # Calculate arbitrage P&L (guaranteed profit)
        total_cost = yes_price + no_price
        guaranteed_payout = 1.0
        profit = (guaranteed_payout - total_cost) * yes_amount
        roi_pct = (profit / position_size) * 100

        if DRY_RUN:
            print()
            print(f"  📊 ARBITRAGE P&L:")
            print(f"     Cost: ${total_cost:.4f} per share × {yes_amount:.2f} shares = ${position_size:.2f}")
            print(f"     Payout: $1.00 per share × {yes_amount:.2f} shares = ${yes_amount:.2f}")
            print(f"     Guaranteed Profit: +${profit:.2f} ({roi_pct:.2f}%)")
            print()

        return {
            "execution_results": results,
            "total_shares": yes_amount,
            "total_cost_usd": position_size,
            "guaranteed_profit_usd": profit,
            "roi_pct": roi_pct
        }

    def _execute_multi_outcome_arbitrage(self, opp, market):
        """Execute multi-outcome arbitrage: buy all outcomes simultaneously."""
        print(f"\n🔄 Executing MULTI-OUTCOME arbitrage ({len(opp.trades)} outcomes)...")

        # Calculate position size
        current_exposure = self.get_total_exposure()
        available = float(MAX_TOTAL_EXPOSURE - current_exposure)
        position_size = min(float(opp.total_cost), available, float(MAX_POSITION_SIZE))

        if position_size < 0.01:
            print(f"⚠️ Position size too small: ${position_size:.2f}")
            return None

        print(f"Position size: ${position_size:.2f}")

        results = []
        total_spent = 0.0

        # Execute each outcome
        for i, trade in enumerate(opp.trades):
            outcome = trade['outcome']
            price = trade['price']

            # Get token ID for this outcome
            token_id = self._get_token_id_for_outcome(market, outcome)
            if not token_id:
                print(f"❌ Could not find token ID for outcome: {outcome}")
                return None

            # Calculate shares proportional to price
            shares = position_size / float(opp.total_cost) / len(opp.trades)

            try:
                if not DRY_RUN:
                    from py_clob_client.clob_types import MarketOrderArgs, OrderType

                    print(f"🟢 Buying {outcome} @ ${price:.4f} for {shares:.2f} shares")
                    order_args = MarketOrderArgs(
                        token_id=token_id,
                        amount=shares,
                        side="BUY"
                    )
                    signed_order = self.polymarket.client.create_market_order(order_args)
                    result = self.polymarket.client.post_order(signed_order, OrderType.FOK)
                    results.append({"outcome": outcome, "result": result})
                    total_spent += shares * price
                    print(f"✅ {outcome} order executed: {result.get('orderID', 'unknown')}")
                else:
                    results.append({"outcome": outcome, "result": "DRY_RUN"})
                    total_spent += shares * price
                    print(f"🟢 DRY RUN: Would buy {outcome} @ ${price:.4f}")

            except Exception as e:
                print(f"❌ {outcome} order failed: {e}")
                # TODO: Should we try to reverse previous orders?
                return None

        return {
            "execution_results": results,
            "total_shares": shares,
            "total_cost_usd": total_spent
        }

    def _execute_asymmetric_arbitrage(self, opp, market):
        """Execute asymmetric arbitrage: buy single mispriced outcome."""
        print(f"\n🔄 Executing ASYMMETRIC arbitrage...")

        trade = opp.trades[0]  # Only one trade for asymmetric
        outcome = trade['outcome']
        price = trade['price']

        # Get token ID
        token_id = self._get_token_id_for_outcome(market, outcome)
        if not token_id:
            print(f"❌ Could not find token ID for outcome: {outcome}")
            return None

        # Calculate position size
        current_exposure = self.get_total_exposure()
        available = float(MAX_TOTAL_EXPOSURE - current_exposure)
        position_size = min(float(opp.total_cost), available, float(MAX_POSITION_SIZE))

        if position_size < 0.01:
            print(f"⚠️ Position size too small: ${position_size:.2f}")
            return None

        shares = position_size / price

        print(f"Position size: ${position_size:.2f}")
        print(f"Token: {token_id}")

        try:
            if not DRY_RUN:
                from py_clob_client.clob_types import MarketOrderArgs, OrderType

                print(f"🟡 Buying {outcome} @ ${price:.4f} for {shares:.2f} shares")
                order_args = MarketOrderArgs(
                    token_id=token_id,
                    amount=shares,
                    side="BUY"
                )
                signed_order = self.polymarket.client.create_market_order(order_args)
                result = self.polymarket.client.post_order(signed_order, OrderType.FOK)
                print(f"✅ Order executed: {result.get('orderID', 'unknown')}")

                return {
                    "execution_results": [{"outcome": outcome, "result": result}],
                    "total_shares": shares,
                    "total_cost_usd": position_size
                }
            else:
                print(f"🟡 DRY RUN: Would buy {outcome} @ ${price:.4f}")
                return {
                    "execution_results": [{"outcome": outcome, "result": "DRY_RUN"}],
                    "total_shares": shares,
                    "total_cost_usd": position_size
                }

        except Exception as e:
            print(f"❌ Order failed: {e}")
            return None

    def _execute_arbitrage(self, opp, market_id, question, market):
        """Route arbitrage execution based on opportunity type."""

        # Check exposure limits
        current_exposure = self.get_total_exposure()
        if current_exposure >= MAX_TOTAL_EXPOSURE:
            print(f"⚠️ Max exposure reached: ${current_exposure:.2f} / ${MAX_TOTAL_EXPOSURE}")
            return None

        # Execute based on type
        if opp.opportunity_type == "binary":
            execution_result = self._execute_binary_arbitrage(opp, market)
        elif opp.opportunity_type == "multi_outcome":
            execution_result = self._execute_multi_outcome_arbitrage(opp, market)
        elif opp.opportunity_type == "asymmetric":
            execution_result = self._execute_asymmetric_arbitrage(opp, market)
        else:
            print(f"❌ Unknown opportunity type: {opp.opportunity_type}")
            return None

        if not execution_result:
            return None

        # Create trade record
        trade_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "strategy": "arbitrage",
            "market_id": market_id,
            "market_question": question,
            "opportunity_type": opp.opportunity_type,
            "expected_profit_pct": opp.expected_profit_pct,
            "size_usdc": execution_result['total_cost_usd'],
            "shares": execution_result['total_shares'],
            "dry_run": DRY_RUN,
            "execution_results": execution_result['execution_results'],
            "status": "open"
        }

        self.save_trade(trade_record)
        print(f"\n✅ Arbitrage executed and logged!")

        return trade_record

    def scan_for_arbitrage(self):
        print(f"\n{'='*60}")
        print("SCANNING FOR ARBITRAGE OPPORTUNITIES")
        print(f"{'='*60}")
        
        markets = self.gamma.get_current_markets()
        print(f"Scanning {len(markets)} markets...")
        
        found_count = 0
        
        for market in markets:
            market_id = str(market.get('id'))
            question = market.get('question', 'Unknown')
            
            # Skip if already have position
            if any(t.get('market_id') == market_id and t.get('status') == 'open' 
                   for t in self.trades_history):
                continue
            
            try:
                # Parse prices safely
                outcome_prices_raw = market.get('outcomePrices', '[]')
                outcomes_raw = market.get('outcomes', '[]')
                
                prices_list = ast.literal_eval(outcome_prices_raw) if isinstance(outcome_prices_raw, str) else outcome_prices_raw
                outcomes_list = ast.literal_eval(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                
                outcome_prices = {
                    outcome: float(price) 
                    for outcome, price in zip(outcomes_list, prices_list)
                }
                
                opportunities = self.arbitrage_detector.scan_market(
                    market_id, question, outcome_prices
                )
                
                if opportunities:
                    found_count += len(opportunities)
                    opp = opportunities[0]
                    
                    print(f"\n✨ ARBITRAGE FOUND!")
                    print(f"Market: {question[:60]}")
                    print(f"Type: {opp.opportunity_type}")
                    print(f"Profit: {opp.expected_profit_pct:.2f}%")
                    print(f"Cost: ${opp.total_cost}")
                    print(f"Risk: {opp.risk_level}")
                    
                    # Execute arbitrage trade
                    trade_record = self._execute_arbitrage(opp, market_id, question, market)
                    if trade_record:
                        return trade_record
                    
            except Exception as e:
                continue
        
        print(f"\n📊 Scan complete: {found_count} opportunities found")
        return None


def main():
    print(f"\n{'='*60}")
    print("HYBRID AUTONOMOUS TRADER")
    print(f"{'='*60}\n")
    
    trader = HybridAutonomousTrader()
    result = trader.scan_for_arbitrage()
    
    if result:
        print(f"\n✅ Arbitrage opportunity logged!")
        print(f"Profit: {result['expected_profit_pct']:.2f}%")
    else:
        print(f"\n❌ No arbitrage found")


if __name__ == "__main__":
    main()
