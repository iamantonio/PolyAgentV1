"""
Autonomous Trader - Test Run

PHASE 2 LEARNINGS APPLIED:
- BUY works via API (Magic.Link mode)
- SELL requires manual exit via Polymarket UI
- Position tracking for manual close monitoring

SAFETY CONSTRAINTS:
- Max position size: 2.0 USDC per trade
- Max total exposure: 10.0 USDC
- Saves all trades to /tmp/autonomous_trades.json
- Dry run mode available
"""

import os
import sys
import json
from datetime import datetime
from decimal import Decimal

# Navigate to project root
os.chdir('/home/tony/Dev/agents')
sys.path.insert(0, '/home/tony/Dev/agents')

from agents.polymarket.polymarket import Polymarket
from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.application.executor import Executor
from agents.connectors.lunarcrush import LunarCrush

# SAFETY LIMITS
MAX_POSITION_SIZE = Decimal('2.0')  # Max 2 USDC per trade
MAX_TOTAL_EXPOSURE = Decimal('10.0')  # Max 10 USDC total
TRADES_LOG = '/tmp/autonomous_trades.json'

# TRADING CONSTRAINTS
MIN_HOURS_TO_CLOSE = 6  # VERY AGGRESSIVE - Trade markets closing within 6 hours
CRYPTO_ONLY = False  # All market types allowed

# MODE
DRY_RUN = True  # TESTING MODE - NO REAL TRADES


class SafeAutonomousTrader:
    """Autonomous trader with safety constraints and position tracking using Grok."""

    def __init__(self):
        self.polymarket = Polymarket()
        self.gamma = Gamma()
        self.agent = Executor(
            default_model='grok-4-1-fast-reasoning',
            use_grok=True
        )  # Using Grok!
        self.lunarcrush = LunarCrush()  # Social intelligence for crypto markets
        self.trades_history = self.load_trades_history()

    def load_trades_history(self):
        """Load previous trades from disk."""
        try:
            with open(TRADES_LOG, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def pre_trade_logic(self):
        """Clear local RAG databases before trading."""
        import shutil
        try:
            shutil.rmtree("local_db_events")
        except:
            pass
        try:
            shutil.rmtree("local_db_markets")
        except:
            pass

    def get_all_tradeable_events(self):
        """Get active, unclosed events from Polymarket."""
        # Use Gamma API directly with closed=false to get ONLY active markets
        raw_events = self.gamma.get_events(querystring_params={
            "closed": "false",
            "limit": 20  # Get more events to choose from
        })

        print(f"  Active events from API: {len(raw_events)}")

        # Convert to SimpleEvent format
        usable_events = []
        for event_data in raw_events:
            try:
                mapped = self.polymarket.map_api_to_event(event_data)
                from agents.utils.objects import SimpleEvent
                usable_events.append(SimpleEvent(**mapped))
            except Exception as e:
                print(f"  ⚠️ Skipping event: {e}")

        print(f"  Usable events: {len(usable_events)}")
        return usable_events

    def save_trade(self, trade_data):
        """Save trade to disk."""
        self.trades_history.append(trade_data)
        with open(TRADES_LOG, 'w') as f:
            json.dump(self.trades_history, f, indent=2, default=str)

    def get_proxy_usdc_balance(self):
        """Get USDC balance from the proxy wallet (where funds actually are)."""
        import os
        from dotenv import load_dotenv
        load_dotenv(override=True)  # Force reload .env

        proxy_address = os.getenv("POLYMARKET_PROXY_ADDRESS")
        if not proxy_address:
            raise ValueError("POLYMARKET_PROXY_ADDRESS not found in .env")

        # Check USDC balance of proxy wallet
        balance_res = self.polymarket.usdc.functions.balanceOf(proxy_address).call()
        return float(balance_res / 10e5)

    def get_total_exposure(self):
        """Calculate total current exposure from open positions."""
        total = Decimal('0')
        for trade in self.trades_history:
            if trade.get('status') == 'open':
                total += Decimal(str(trade['size_usdc']))
        return total

    def check_safety_limits(self, proposed_size: Decimal):
        """Verify trade doesn't exceed safety limits."""
        current_exposure = self.get_total_exposure()

        print(f"\n{'='*60}")
        print("SAFETY CHECK")
        print(f"{'='*60}")
        print(f"Proposed trade size: {proposed_size} USDC")
        print(f"Current exposure: {current_exposure} USDC")
        print(f"New total exposure: {current_exposure + proposed_size} USDC")
        print()
        print(f"Limits:")
        print(f"  Max position size: {MAX_POSITION_SIZE} USDC")
        print(f"  Max total exposure: {MAX_TOTAL_EXPOSURE} USDC")
        print()

        if proposed_size > MAX_POSITION_SIZE:
            print(f"❌ REJECTED: Trade size {proposed_size} > max {MAX_POSITION_SIZE}")
            return False

        if current_exposure + proposed_size > MAX_TOTAL_EXPOSURE:
            print(f"❌ REJECTED: Total exposure would exceed {MAX_TOTAL_EXPOSURE}")
            return False

        print("✅ PASSED: Within safety limits")
        return True

    def execute_safe_trade(self):
        """Execute one trade with safety constraints."""
        try:
            print(f"\n{'='*60}")
            print("AUTONOMOUS TRADER - SAFE MODE")
            print(f"{'='*60}")
            print(f"Dry run: {DRY_RUN}")
            print(f"Max position: {MAX_POSITION_SIZE} USDC")
            print(f"Max exposure: {MAX_TOTAL_EXPOSURE} USDC")
            print(f"Crypto only: {CRYPTO_ONLY}")
            print(f"Min time to close: {MIN_HOURS_TO_CLOSE} hours")
            print()

            # Run pre-trade logic (clear local DBs)
            self.pre_trade_logic()

            # Step 1: Get all events
            events = self.get_all_tradeable_events()  # Use our custom method
            print(f"1. FOUND {len(events)} EVENTS")

            # Step 2: Skip RAG, use all events (Grok has 2M context!)
            # RAG requires OpenAI API for embeddings - we're using Grok instead
            filtered_events = events[:10]  # Take first 10 to start
            print(f"2. SELECTED {len(filtered_events)} EVENTS (bypassing RAG)")

            if not filtered_events:
                print("\n❌ No relevant events found. Exiting.")
                return

            # Step 3: Map events to markets (manual, bypassing RAG wrapper)
            markets = []
            for event in filtered_events:
                # Get market IDs from event
                market_ids_str = event.markets if hasattr(event, 'markets') and event.markets else ""
                if market_ids_str:
                    market_ids = market_ids_str.split(",")
                    for market_id in market_ids:
                        try:
                            market_data = self.gamma.get_market(market_id.strip())
                            formatted_market = self.polymarket.map_api_to_market(market_data)
                            markets.append(formatted_market)
                        except Exception as e:
                            print(f"  ⚠️ Skipping market {market_id}: {e}")
            print(f"\n3. FOUND {len(markets)} MARKETS")

            if not markets:
                print("\n❌ No markets found. Exiting.")
                return

            # Step 4: Skip market RAG filtering (also needs OpenAI)
            # Grok will analyze and pick the best one
            # Sort markets by creation date - newest first
            from datetime import datetime
            def get_market_creation_date(market):
                """Extract creation date for sorting, defaulting to epoch if missing."""
                created_at_str = market.get('created_at') or market.get('createdAt', '')
                if created_at_str:
                    try:
                        # Handle ISO format with timezone
                        return datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    except:
                        pass
                return datetime(1970, 1, 1)  # Default to epoch for markets without dates

            filtered_markets = sorted(markets, key=get_market_creation_date, reverse=True)
            print(f"4. ANALYZING UP TO {len(filtered_markets)} MARKETS with Grok (newest created first)")

            if not filtered_markets:
                print("\n❌ No good markets found. Exiting.")
                return

            # Step 5: Loop through markets to find one that's not resolved
            from langchain_core.documents import Document

            best_trade = None
            market_dict = None
            market_wrapped = None

            for idx, candidate_market in enumerate(filtered_markets):
                print(f"\n  Analyzing market {idx+1}/{len(filtered_markets)}: {candidate_market.get('question', 'Unknown')[:80]}...")

                # Skip markets where we already have an open position
                market_id = candidate_market.get('id')
                if market_id and any(trade.get('status') == 'open' and trade.get('market_id') == market_id for trade in self.trades_history):
                    print(f"  ⏭️  Skipping - already have open position in this market")
                    continue

                # CRYPTO-ONLY FILTER: Skip non-crypto markets
                question = candidate_market.get('question', '')
                description = candidate_market.get('description', '')
                crypto_token = self.lunarcrush.detect_crypto_token(question, description)

                if CRYPTO_ONLY and not crypto_token:
                    print(f"  ⏭️  Skipping - not a crypto market")
                    continue

                # TIME HORIZON FILTER: Skip markets closing too soon or with missing dates
                from datetime import datetime, timedelta
                end_date_str = candidate_market.get('end') or candidate_market.get('end_date_iso') or candidate_market.get('end_date', '')

                if not end_date_str:
                    print(f"  ⏭️  Skipping - no end date (risky)")
                    continue

                try:
                    if 'T' in end_date_str:
                        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    else:
                        end_date = datetime.fromisoformat(end_date_str)

                    # TIME FILTER: Only use MIN_HOURS_TO_CLOSE (48h minimum)
                    hours_until_close = (end_date - datetime.now(end_date.tzinfo or None)).total_seconds() / 3600

                    if hours_until_close < MIN_HOURS_TO_CLOSE:
                        print(f"  ⏭️  Skipping - closes in {hours_until_close:.1f}h (min: {MIN_HOURS_TO_CLOSE}h)")
                        continue

                    print(f"  ✅ Time check passed: closes in {hours_until_close:.1f}h ({end_date.strftime('%Y-%m-%d')})")
                except Exception as e:
                    print(f"  ⏭️  Skipping - invalid end date format: {end_date_str}")
                    continue

                # Fetch LunarCrush data for crypto market
                lunarcrush_context = None

                if crypto_token:
                    print(f"  🌙 Detected crypto market: {crypto_token}")
                    lc_data = self.lunarcrush.get_topic_data(crypto_token)
                    if lc_data:
                        lunarcrush_context = self.lunarcrush.format_for_prompt(crypto_token, lc_data)

                # Wrap market in RAG format (tuple with Document)
                market_doc = Document(
                    page_content=description,
                    metadata=candidate_market  # Store all market data in metadata
                )
                market_wrapped_temp = (market_doc, 1.0)  # Tuple format: (Document, score)

                # Get Grok's analysis (with LunarCrush context if crypto)
                trade_result = self.agent.source_best_trade(market_wrapped_temp, lunarcrush_context)

                # Check if Grok skipped this market (already resolved)
                if "SKIP:" in trade_result:
                    print(f"  ⏭️  Skipped (resolved market)")
                    continue

                # Found an active market!
                print(f"  ✅ Found active market!")
                best_trade = trade_result
                market_dict = candidate_market
                market_wrapped = market_wrapped_temp
                break

            if not best_trade:
                print("\n❌ All markets are resolved. No active markets to trade.")
                return None

            print(f"\n5. CALCULATED TRADE: {best_trade}")

            # Step 6: Parse Grok's trade output
            # Format: "outcome:Yes,\nprice:0.19,\nsize:0.2,"
            trade_parts = {}
            for line in best_trade.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    trade_parts[key.strip()] = value.strip().rstrip(',').strip("'\"")

            # Extract trade parameters
            trade_outcome = trade_parts.get('outcome', 'Yes')  # Which outcome to buy
            size_fraction = float(trade_parts.get('size', '0.1'))  # Fraction of total funds
            trade_price = float(trade_parts.get('price', '0.5'))

            # Calculate USDC amount from PROXY wallet (where funds actually are)
            usdc_balance = self.get_proxy_usdc_balance()
            raw_amount = size_fraction * usdc_balance

            # Polymarket minimum order size is $1 USDC
            MIN_ORDER_SIZE = Decimal('1.0')

            # Apply minimum, then cap at max
            if Decimal(str(raw_amount)) < MIN_ORDER_SIZE:
                proposed_size = MIN_ORDER_SIZE
                print(f"   ⚠️ Trade size {raw_amount:.2f} below $1 minimum - using $1")
            else:
                proposed_size = min(Decimal(str(raw_amount)), MAX_POSITION_SIZE)

            print(f"   Trade outcome: {trade_outcome}")
            print(f"   Trade price: {trade_price}")
            print(f"   Size fraction: {size_fraction} ({size_fraction*100}%)")
            print(f"   Proxy USDC balance: {usdc_balance}")

            print(f"\n6. FORMATTED:")
            print(f"   Raw calculation: {raw_amount} USDC")
            print(f"   Capped amount: {proposed_size} USDC")

            # Step 7: Safety check
            if not self.check_safety_limits(proposed_size):
                print("\n❌ Trade rejected by safety limits")
                return

            # Step 8: Create trade record with full details
            trade_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "market_question": market_dict.get("question"),
                "market_id": market_dict.get("id"),
                "outcome": trade_outcome,
                "price": trade_price,
                "size_fraction": size_fraction,
                "analysis": best_trade,
                "size_usdc": float(proposed_size),
                "dry_run": DRY_RUN,
                "status": "open"
            }

            # Step 9: Execute or simulate
            if DRY_RUN:
                print(f"\n{'='*60}")
                print("DRY RUN - NO REAL TRADE EXECUTED")
                print(f"{'='*60}")
                print(f"Would execute:")
                print(f"  Market: {trade_record['market_question']}")
                print(f"  Outcome: {trade_outcome}")
                print(f"  Entry Price: ${trade_price:.4f}")
                print(f"  Size: {trade_record['size_usdc']} USDC")
                print(f"  Shares: {float(trade_record['size_usdc']) / trade_price:.2f}")
                print()

                # Calculate hypothetical P&L
                shares = float(trade_record['size_usdc']) / trade_price
                max_profit = (1.0 - trade_price) * shares  # If outcome wins
                max_loss = trade_price * shares  # If outcome loses

                print(f"  📊 Hypothetical P&L:")
                print(f"     If {trade_outcome} wins: +${max_profit:.2f} ({(max_profit/float(trade_record['size_usdc'])*100):.1f}%)")
                print(f"     If {trade_outcome} loses: -${max_loss:.2f} ({(max_loss/float(trade_record['size_usdc'])*100):.1f}%)")
                print(f"  Analysis: {best_trade}")
                print()

                trade_record["execution_result"] = "DRY_RUN_SIMULATED"
                trade_record["entry_price"] = trade_price
                trade_record["shares"] = shares
                trade_record["max_profit_usd"] = max_profit
                trade_record["max_loss_usd"] = max_loss
            else:
                print(f"\n{'='*60}")
                print("EXECUTING LIVE TRADE")
                print(f"{'='*60}")

                # Execute order directly using py-clob-client
                import ast
                from py_clob_client.clob_types import MarketOrderArgs, OrderType

                # Get token IDs from market and map outcome to token
                clob_token_ids = ast.literal_eval(market_dict["clob_token_ids"])
                outcomes_list = ast.literal_eval(market_dict["outcomes"])

                # Map the chosen outcome to the correct token ID
                if trade_outcome in outcomes_list:
                    token_index = outcomes_list.index(trade_outcome)
                    token_id = clob_token_ids[token_index]
                else:
                    # Fallback: try case-insensitive match
                    trade_outcome_lower = trade_outcome.lower()
                    for i, outcome in enumerate(outcomes_list):
                        if outcome.lower() == trade_outcome_lower:
                            token_id = clob_token_ids[i]
                            break
                    else:
                        # Default to first outcome if no match
                        print(f"  ⚠️ Could not match outcome '{trade_outcome}' to {outcomes_list}, using first outcome")
                        token_id = clob_token_ids[0]

                print(f"Creating order:")
                print(f"  Outcome: {trade_outcome}")
                print(f"  Token ID: {token_id[:20]}...")
                print(f"  Amount: {float(proposed_size)} USDC")
                print()

                # Create market order (always BUY the chosen outcome)
                order_args = MarketOrderArgs(
                    token_id=token_id,
                    amount=float(proposed_size),
                    side="BUY"
                )

                # Sign and post order
                signed_order = self.polymarket.client.create_market_order(order_args)
                result = self.polymarket.client.post_order(signed_order, OrderType.FOK)

                print(f"✅ TRADE EXECUTED!")
                print(f"  Response: {result}")

                trade_record["execution_result"] = str(result)
                trade_record["execution_id"] = result.get('orderID') if isinstance(result, dict) else None

            # Step 10: Save trade
            self.save_trade(trade_record)

            print(f"\n{'='*60}")
            print("TRADE COMPLETE")
            print(f"{'='*60}")
            print(f"Saved to: {TRADES_LOG}")
            print()

            # Remind about manual exit
            if not DRY_RUN and trade_record.get("execution_id"):
                print("⚠️  REMINDER: SELL operations require manual exit")
                print("   Go to https://polymarket.com to close position when ready")
                print()

            return trade_record

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Run autonomous trader test."""
    print(f"\n{'='*60}")
    print("AUTONOMOUS TRADER TEST")
    print(f"{'='*60}\n")

    trader = SafeAutonomousTrader()

    # Show current exposure
    current_exposure = trader.get_total_exposure()
    print(f"Current open exposure: {current_exposure} USDC")
    print(f"Available capacity: {MAX_TOTAL_EXPOSURE - current_exposure} USDC")
    print()

    if current_exposure >= MAX_TOTAL_EXPOSURE:
        print("⚠️  Max exposure reached. Close positions before trading.")
        print(f"   View trades: cat {TRADES_LOG}")
        return

    # Execute one trade
    result = trader.execute_safe_trade()

    if result:
        print("\n✅ Test complete!")
        print(f"\nView all trades: cat {TRADES_LOG}")
    else:
        print("\n❌ Test failed or no trade executed")


if __name__ == "__main__":
    main()
