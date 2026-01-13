#!/usr/bin/env python3
"""
Hybrid Learning Trader v2 - Best of Both Worlds

Combines:
1. Learning Autonomous Trader: Full execution, position management, safety
2. Hybrid Framework: Arbitrage, multi-signal crypto edge

STRATEGY PRIORITY:
1. ARBITRAGE - Risk-free profit when YES+NO < 1.0 after fees
2. CRYPTO EDGE - Trade when 2+ signals agree (funding, OBI, sentiment)
3. AI PREDICTION - Use XAI for markets where we can learn

CHANGES FROM V1:
- Removed edge requirement (we learn by trading)
- Proper trade execution copied from learning trader
- Position management (stop-loss/take-profit)
- Simpler, cleaner code
"""

import os
import sys
import time
import ast
import re
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List
from decimal import Decimal, ROUND_DOWN

os.chdir('/home/tony/Dev/agents')
sys.path.insert(0, '/home/tony/Dev/agents')

from dotenv import load_dotenv
load_dotenv()

from py_clob_client.order_builder.constants import BUY, SELL
from py_clob_client.clob_types import OrderArgs, OrderType

from agents.polymarket.polymarket import Polymarket
from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.learning.trade_history import TradeHistoryDB
from agents.utils.discord_alerts import DiscordAlerter

# Optional imports
try:
    from agents.connectors.crypto_edge import CryptoEdgeDetector
    CRYPTO_EDGE_AVAILABLE = True
except ImportError:
    CRYPTO_EDGE_AVAILABLE = False

try:
    from agents.polymarket.position_sync import PositionSync
    POSITION_SYNC_AVAILABLE = True
except ImportError:
    POSITION_SYNC_AVAILABLE = False

try:
    from agents.polymarket.outcome_sync import OutcomeSync
    OUTCOME_SYNC_AVAILABLE = True
except ImportError:
    OUTCOME_SYNC_AVAILABLE = False

try:
    from openai import OpenAI
    XAI_AVAILABLE = True
except ImportError:
    XAI_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

DB_DIR = os.path.expanduser("~/.polymarket")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "learning_trader.db")

# Trading Mode
DRY_RUN = False  # LIVE TRADING

# Capital
BANKROLL = 100.0
MIN_POSITION = 5.0   # Polymarket minimum
MAX_POSITION = 10.0  # Max per trade

# Strategy Thresholds
ARBITRAGE_MIN_PROFIT = 0.005     # 0.5% minimum arb profit
CRYPTO_MIN_SIGNALS = 2           # Need 2+ signals to agree (relaxed from 3)
AI_MIN_CONFIDENCE = 0.55         # 55% confidence minimum

# Risk Management
MAX_OPEN_POSITIONS = 20
STOP_LOSS_PCT = -0.50            # Sell if down 50%
TAKE_PROFIT_PCT = 0.30           # Sell if up 30%


# =============================================================================
# HYBRID TRADER
# =============================================================================

class HybridLearningTrader:
    """
    Hybrid trader that combines arbitrage, crypto signals, and AI predictions.
    Uses proper execution and position management from learning trader.
    """

    def __init__(self):
        print("=" * 70)
        print("HYBRID LEARNING TRADER v2")
        print("=" * 70)

        # Core
        self.polymarket = Polymarket()
        self.gamma = Gamma()
        self.db = TradeHistoryDB(DB_PATH)
        self.discord = DiscordAlerter()

        # Crypto edge
        self.crypto_edge = None
        if CRYPTO_EDGE_AVAILABLE:
            try:
                self.crypto_edge = CryptoEdgeDetector()
                print("  + CryptoEdgeDetector")
            except Exception as e:
                print(f"  - CryptoEdge: {e}")

        # Position sync
        self.position_sync = None
        if POSITION_SYNC_AVAILABLE:
            try:
                self.position_sync = PositionSync(DB_PATH)
                print("  + PositionSync")
            except Exception as e:
                print(f"  - PositionSync: {e}")

        # Outcome sync
        self.outcome_sync = None
        if OUTCOME_SYNC_AVAILABLE:
            try:
                self.outcome_sync = OutcomeSync(DB_PATH)
                print("  + OutcomeSync")
            except Exception as e:
                print(f"  - OutcomeSync: {e}")

        # XAI client
        self.xai_client = None
        if XAI_AVAILABLE and os.getenv("XAI_API_KEY"):
            self.xai_client = OpenAI(
                api_key=os.getenv("XAI_API_KEY"),
                base_url="https://api.x.ai/v1"
            )
            print("  + XAI (Grok)")

        # State
        self.traded_markets = set()
        self.last_sync = 0

        # Stats
        self.stats = {
            "scanned": 0,
            "arbitrage": 0,
            "crypto_edge": 0,
            "ai_trades": 0,
            "skipped": 0,
            "executed": 0,
        }

        # Initial sync
        self._sync_all()

        print()
        print(f"Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
        print(f"Bankroll: ${BANKROLL}")
        print("=" * 70)

    def _sync_all(self):
        """Sync positions and outcomes."""
        if self.position_sync:
            try:
                self.position_sync.reconcile_positions(verbose=False)
            except Exception as e:
                print(f"Position sync: {e}")

        if self.outcome_sync:
            try:
                self.outcome_sync.sync_outcomes(verbose=False)
            except Exception as e:
                print(f"Outcome sync: {e}")

        self.last_sync = time.time()

    # =========================================================================
    # STRATEGY 1: ARBITRAGE
    # =========================================================================

    def check_arbitrage(self, market: Dict) -> Optional[Dict]:
        """Check for arbitrage opportunity."""
        try:
            tokens = market.get("clobTokenIds", [])
            if isinstance(tokens, str):
                tokens = ast.literal_eval(tokens)
            if len(tokens) != 2:
                return None

            yes_token, no_token = tokens[0], tokens[1]

            # Get orderbooks
            yes_book = self.polymarket.get_orderbook(yes_token)
            no_book = self.polymarket.get_orderbook(no_token)

            if not yes_book.get("asks") or not no_book.get("asks"):
                return None

            yes_ask = float(yes_book["asks"][0]["price"])
            no_ask = float(no_book["asks"][0]["price"])
            yes_size = float(yes_book["asks"][0]["size"])
            no_size = float(no_book["asks"][0]["size"])

            # Arbitrage check: buy both for < $1
            total_cost = yes_ask + no_ask
            fee_adjusted = total_cost + 0.02  # 2% fees

            if fee_adjusted < 1.0:
                profit_margin = 1.0 - fee_adjusted

                if profit_margin >= ARBITRAGE_MIN_PROFIT:
                    size = min(yes_size, no_size, MAX_POSITION)
                    size = max(size, MIN_POSITION)

                    return {
                        "type": "ARBITRAGE",
                        "market": market,
                        "yes_token": yes_token,
                        "no_token": no_token,
                        "yes_price": yes_ask,
                        "no_price": no_ask,
                        "profit_margin": profit_margin,
                        "size": size,
                    }

        except Exception:
            pass

        return None

    # =========================================================================
    # STRATEGY 2: CRYPTO EDGE
    # =========================================================================

    def check_crypto_edge(self, market: Dict) -> Optional[Dict]:
        """Check for crypto signal alignment."""
        if not self.crypto_edge:
            return None

        question = market.get("question", "").lower()

        # Detect crypto symbol
        token = self.crypto_edge.detect_token_from_question(question)
        if not token:
            return None

        # Get current price
        price = float(market.get("price", 0.5))

        # Get combined edge
        edge = self.crypto_edge.get_combined_edge(token, price)

        if not edge.get("should_trade"):
            return None

        # Check signal count (relaxed to 2)
        up = edge.get("up_signals", 0)
        down = edge.get("down_signals", 0)
        max_signals = max(up, down)

        if max_signals < CRYPTO_MIN_SIGNALS:
            return None

        direction = "YES" if up > down else "NO"  # YES = up, NO = down
        confidence = edge.get("combined_confidence", 0.6)

        return {
            "type": "CRYPTO_EDGE",
            "market": market,
            "token": token,
            "direction": direction,
            "confidence": confidence,
            "signals": edge.get("signals", {}),
            "reasoning": edge.get("reasoning", []),
        }

    # =========================================================================
    # STRATEGY 3: AI PREDICTION
    # =========================================================================

    def check_ai_prediction(self, market: Dict) -> Optional[Dict]:
        """Use XAI for prediction on non-crypto markets."""
        if not self.xai_client:
            return None

        question = market.get("question", "")
        market_id = market.get("condition_id") or market.get("id", "")

        # Skip crypto (handled by crypto_edge)
        crypto_words = ["bitcoin", "ethereum", "solana", "crypto", "btc", "eth", "xrp"]
        if any(w in question.lower() for w in crypto_words):
            return None

        # Check cache - skip AI call if we analyzed this market recently (24h)
        cached = self.db.get_cached_prediction(market_id, hours=24)
        if cached:
            if cached["confidence"] >= AI_MIN_CONFIDENCE:
                return {
                    "type": "AI_PREDICTION",
                    "market": market,
                    "direction": cached["outcome"],
                    "confidence": cached["confidence"],
                    "reasoning": f"[CACHED] {cached['reasoning'][:80]}" if cached['reasoning'] else "[CACHED]",
                }
            return None  # Previously skipped due to low confidence

        try:
            prompt = f"""Analyze this prediction market:

Question: {question}

Predict the outcome (YES or NO) and your confidence (0.5-0.9).
Be brief. Format:
PREDICTION: YES or NO
CONFIDENCE: 0.XX
REASONING: One sentence"""

            response = self.xai_client.chat.completions.create(
                model="grok-4-1-fast-reasoning",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=100
            )

            content = response.choices[0].message.content

            # Parse
            outcome = "YES" if "YES" in content.upper().split("CONFIDENCE")[0] else "NO"

            conf_match = re.search(r'CONFIDENCE[:\s]*([0-9.]+)', content, re.I)
            confidence = float(conf_match.group(1)) if conf_match else 0.6

            reasoning = content.split("REASONING:")[-1].strip()[:100] if "REASONING:" in content else ""

            # Cache the prediction (even if we skip due to low confidence)
            self.db.store_prediction(
                market_id=market_id,
                question=question[:100],
                predicted_outcome=outcome,
                predicted_probability=confidence,
                confidence=confidence,
                reasoning=reasoning,
                strategy="ai_prediction",
                market_type="ai_prediction",
            )

            if confidence < AI_MIN_CONFIDENCE:
                return None

            return {
                "type": "AI_PREDICTION",
                "market": market,
                "direction": outcome,
                "confidence": confidence,
                "reasoning": reasoning,
            }

        except Exception:
            return None

    # =========================================================================
    # EXECUTION
    # =========================================================================

    def execute_trade(self, opportunity: Dict) -> bool:
        """Execute a trade opportunity."""
        opp_type = opportunity["type"]
        market = opportunity["market"]

        if DRY_RUN:
            print(f"  [DRY RUN] {opp_type}")
            self.stats["executed"] += 1
            return True

        try:
            if opp_type == "ARBITRAGE":
                return self._execute_arbitrage(opportunity)
            else:
                return self._execute_directional(opportunity)

        except Exception as e:
            print(f"  Execution error: {e}")
            return False

    def _execute_arbitrage(self, opp: Dict) -> bool:
        """Execute arbitrage (buy both YES and NO)."""
        yes_token = opp["yes_token"]
        no_token = opp["no_token"]
        size = opp["size"]

        print(f"  ARBITRAGE: YES@{opp['yes_price']:.3f} + NO@{opp['no_price']:.3f}")

        # Buy YES
        yes_shares = size / opp["yes_price"]
        yes_order = OrderArgs(
            token_id=yes_token,
            price=float(Decimal(str(opp["yes_price"] * 1.01)).quantize(Decimal('0.0001'))),
            size=float(Decimal(str(yes_shares)).quantize(Decimal('0.01'))),
            side=BUY,
        )

        # Buy NO
        no_shares = size / opp["no_price"]
        no_order = OrderArgs(
            token_id=no_token,
            price=float(Decimal(str(opp["no_price"] * 1.01)).quantize(Decimal('0.0001'))),
            size=float(Decimal(str(no_shares)).quantize(Decimal('0.01'))),
            side=BUY,
        )

        # Execute both
        signed_yes = self.polymarket.client.create_order(yes_order)
        signed_no = self.polymarket.client.create_order(no_order)

        self.polymarket.client.post_order(signed_yes, orderType=OrderType.GTC)
        self.polymarket.client.post_order(signed_no, orderType=OrderType.GTC)

        print(f"  Arbitrage executed")
        self.stats["arbitrage"] += 1
        self.stats["executed"] += 1
        return True

    def _execute_directional(self, opp: Dict) -> bool:
        """Execute directional trade (crypto edge or AI)."""
        market = opp["market"]
        direction = opp["direction"]
        confidence = opp.get("confidence", 0.6)

        # Get token IDs
        tokens = market.get("clobTokenIds", [])
        if isinstance(tokens, str):
            tokens = ast.literal_eval(tokens)
        if len(tokens) != 2:
            return False

        token_id = tokens[0] if direction == "YES" else tokens[1]

        # Get price
        price = float(market.get("bestAsk") or market.get("price", 0.5))
        limit_price = min(price * 1.01, 0.99)
        limit_price = float(Decimal(str(limit_price)).quantize(Decimal('0.0001')))

        # Size
        size = MIN_POSITION
        shares = size / limit_price
        shares = float(Decimal(str(shares)).quantize(Decimal('0.01')))

        print(f"  {opp['type']}: {direction} @ ${limit_price:.4f} ({shares:.2f} shares)")

        # Execute
        order_args = OrderArgs(
            token_id=token_id,
            price=limit_price,
            size=shares,
            side=BUY,
        )

        signed_order = self.polymarket.client.create_order(order_args)
        self.polymarket.client.post_order(signed_order, orderType=OrderType.GTC)

        # Record in DB
        market_id = market.get("condition_id") or market.get("id")
        question = market.get("question", "")[:100]

        # Store prediction and record trade execution
        prediction_id = self.db.store_prediction(
            market_id=market_id,
            question=question,
            predicted_outcome=direction,
            predicted_probability=confidence,
            confidence=confidence,
            reasoning=opp.get("reasoning", ""),
            strategy=opp["type"].lower(),
            market_type=opp["type"].lower(),
        )
        self.db.update_prediction_execution(
            prediction_id=prediction_id,
            trade_size_usdc=size,
            trade_price=limit_price,
            token_id=token_id,
        )

        print(f"  Order placed")

        if opp["type"] == "CRYPTO_EDGE":
            self.stats["crypto_edge"] += 1
        else:
            self.stats["ai_trades"] += 1

        self.stats["executed"] += 1
        return True

    # =========================================================================
    # POSITION MANAGEMENT
    # =========================================================================

    def manage_positions(self):
        """Check open positions for stop-loss/take-profit."""
        positions = self.db.get_open_positions()
        if not positions:
            return

        print(f"\nChecking {len(positions)} positions...")

        for pos in positions:
            try:
                market_id = pos.get("market_id")
                token_id = pos.get("token_id")
                entry_price = pos.get("entry_price") or pos.get("trade_price")
                size = pos.get("size") or pos.get("trade_size_usdc")

                if not all([market_id, token_id, entry_price]):
                    continue

                # Get current price
                orderbook = self.polymarket.client.get_order_book(token_id)
                bids = orderbook.get("bids", [])
                if not bids:
                    continue

                current_price = float(bids[0]["price"])
                pnl_pct = (current_price - entry_price) / entry_price

                question = (pos.get("question") or "")[:40]
                print(f"  {question}... P&L: {pnl_pct:+.1%}")

                # Stop loss
                if pnl_pct <= STOP_LOSS_PCT:
                    print(f"    STOP LOSS")
                    self._close_position(pos, current_price, "stop_loss")

                # Take profit
                elif pnl_pct >= TAKE_PROFIT_PCT:
                    print(f"    TAKE PROFIT")
                    self._close_position(pos, current_price, "take_profit")

            except Exception:
                continue

    def _close_position(self, pos: Dict, price: float, reason: str):
        """Close a position by selling."""
        if DRY_RUN:
            print(f"    [DRY RUN] Would close position")
            return

        try:
            token_id = pos.get("token_id")
            size = pos.get("size") or pos.get("trade_size_usdc") or MIN_POSITION

            shares = size / price
            shares = float(Decimal(str(shares)).quantize(Decimal('0.01')))
            price = float(Decimal(str(price)).quantize(Decimal('0.0001')))

            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=shares,
                side=SELL,
            )

            signed_order = self.polymarket.client.create_order(order_args)
            self.polymarket.client.post_order(signed_order, orderType=OrderType.GTC)

            # Update DB
            market_id = pos.get("market_id")
            self.db.close_position(market_id, price, reason)

            print(f"    Position closed")

        except Exception as e:
            print(f"    Close failed: {e}")

    # =========================================================================
    # MAIN LOOP
    # =========================================================================

    def scan_markets(self) -> List[Dict]:
        """Scan markets for opportunities."""
        opportunities = []

        markets = self.gamma.get_markets(querystring_params={
            "active": True,
            "closed": False,
            "archived": False,
            "limit": 100
        })

        # Filter out markets with past end dates
        now = datetime.now(timezone.utc)
        valid_markets = []
        for m in markets:
            end_date_str = m.get("endDate") or m.get("end_date_iso")
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    if end_date > now:
                        valid_markets.append(m)
                except:
                    valid_markets.append(m)  # Keep if can't parse
            else:
                valid_markets.append(m)  # Keep if no end date

        markets = valid_markets
        print(f"\nScanning {len(markets)} markets (filtered for future resolve dates)...")
        self.stats["scanned"] += len(markets)

        for market in markets:
            market_id = market.get("condition_id") or market.get("id")

            if market_id in self.traded_markets:
                continue

            # Strategy 1: Arbitrage
            arb = self.check_arbitrage(market)
            if arb:
                print(f"  ARB: {market.get('question', '')[:50]}...")
                opportunities.append(arb)
                self.traded_markets.add(market_id)
                continue

            # Strategy 2: Crypto Edge
            crypto = self.check_crypto_edge(market)
            if crypto:
                print(f"  CRYPTO: {crypto['token']} {crypto['direction']} ({crypto['confidence']:.0%})")
                opportunities.append(crypto)
                self.traded_markets.add(market_id)
                continue

            # Strategy 3: AI Prediction
            ai = self.check_ai_prediction(market)
            if ai:
                print(f"  AI: {ai['direction']} ({ai['confidence']:.0%}) - {market.get('question', '')[:40]}...")
                opportunities.append(ai)
                self.traded_markets.add(market_id)
                continue

            self.stats["skipped"] += 1

        return opportunities

    def run(self, scan_interval: int = 60):
        """Main trading loop."""
        print(f"\n{'=' * 70}")
        print("STARTING HYBRID TRADING")
        print(f"{'=' * 70}\n")

        while True:
            try:
                # Sync periodically
                if time.time() - self.last_sync > 1800:
                    self._sync_all()

                # Manage existing positions
                self.manage_positions()

                # Scan for opportunities
                opportunities = self.scan_markets()

                print(f"\nFound {len(opportunities)} opportunities")

                # Execute trades
                for opp in opportunities[:5]:  # Max 5 per scan
                    print(f"\n{'='*50}")
                    print(f"EXECUTING: {opp['type']}")

                    if self.execute_trade(opp):
                        time.sleep(1)  # Rate limit

                # Stats
                print(f"\nSTATS: scanned={self.stats['scanned']}, "
                      f"arb={self.stats['arbitrage']}, crypto={self.stats['crypto_edge']}, "
                      f"ai={self.stats['ai_trades']}, executed={self.stats['executed']}")

                # Clear traded markets for next scan (allows new time windows)
                self.traded_markets.clear()

                print(f"\nSleeping {scan_interval}s...")
                time.sleep(scan_interval)

            except KeyboardInterrupt:
                print("\nStopping...")
                break
            except Exception as e:
                print(f"\nError: {e}")
                time.sleep(60)

        print(f"\nFINAL STATS: {self.stats}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    trader = HybridLearningTrader()
    trader.run(scan_interval=60)
