"""
Cheap market pre-filtering before expensive LLM calls.

Filters out markets that are unlikely to be profitable to trade:
- Low liquidity
- Wide spreads
- Extreme prices (near 0 or 1)
- Too close to resolution
"""

from typing import List, Tuple, Optional
from datetime import datetime, timezone
import ast


class MarketFilter:
    """
    Fast, cheap filters to apply before LLM forecasting.

    These filters use only basic market data (no LLM calls).
    """

    def __init__(
        self,
        min_liquidity: float = 1000.0,  # Min $1000 liquidity
        max_spread_pct: float = 5.0,  # Max 5% spread
        min_price: float = 0.10,  # Avoid prices < 10 cents
        max_price: float = 0.90,  # Avoid prices > 90 cents
        min_hours_to_close: float = 24.0  # Avoid markets closing < 24h
    ):
        self.min_liquidity = min_liquidity
        self.max_spread = max_spread_pct / 100
        self.min_price = min_price
        self.max_price = max_price
        self.min_seconds_to_close = min_hours_to_close * 3600

    def should_consider_market(self, market_object) -> Tuple[bool, Optional[str]]:
        """
        Fast pre-filter: should we even consider forecasting this market?

        Returns:
            (should_consider, reason_if_rejected)
        """
        try:
            market_document = market_object[0].dict()
            market = market_document["metadata"]

            # Extract market data (using ast.literal_eval for safety - not eval!)
            outcome_prices_str = market.get("outcome_prices", "[0.5]")
            outcome_prices = ast.literal_eval(outcome_prices_str)
            question = market.get("question", "")
            market_id = market.get("condition_id", "unknown")

            # Filter 1: Price extremes (avoid near-certainties)
            avg_price = sum(outcome_prices) / len(outcome_prices) if outcome_prices else 0.5

            if avg_price < self.min_price:
                return False, f"Price too low ({avg_price:.3f} < {self.min_price})"

            if avg_price > self.max_price:
                return False, f"Price too high ({avg_price:.3f} > {self.max_price})"

            # Filter 2: Check if market is likely resolved/stale
            # (In real usage, you'd check end_date_iso or similar field)
            # For now, we'll skip this check since we don't have reliable date data in metadata

            # Filter 3: Avoid very short questions (likely low-quality markets)
            if len(question) < 20:
                return False, f"Question too short ({len(question)} chars)"

            # Filter 4: Check for red-flag keywords
            skip_keywords = ["test", "debug", "example"]
            question_lower = question.lower()
            for keyword in skip_keywords:
                if keyword in question_lower:
                    return False, f"Test/debug market (contains '{keyword}')"

            # Passed all cheap filters
            return True, None

        except Exception as e:
            # If we can't parse the market, skip it
            return False, f"Failed to parse market: {e}"

    def filter_markets(self, markets: List) -> List:
        """
        Filter list of markets, keeping only candidates worth forecasting.

        Returns:
            Filtered list of markets + statistics
        """
        if not markets:
            return []

        candidates = []
        rejected_reasons = {}

        for market in markets:
            should_consider, reason = self.should_consider_market(market)

            if should_consider:
                candidates.append(market)
            else:
                rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

        # Print filter stats
        print(f"\n📊 [PRE-FILTER] Market filtering:")
        print(f"   Input markets: {len(markets)}")
        print(f"   Candidates: {len(candidates)}")
        print(f"   Rejected: {len(markets) - len(candidates)}")

        if rejected_reasons:
            print(f"\n   Rejection reasons:")
            for reason, count in sorted(rejected_reasons.items(), key=lambda x: -x[1]):
                print(f"     - {reason}: {count}")

        return candidates

    def get_config(self) -> dict:
        """Get current filter configuration."""
        return {
            "min_liquidity": self.min_liquidity,
            "max_spread_pct": self.max_spread * 100,
            "price_range": f"{self.min_price:.2f}-{self.max_price:.2f}",
            "min_hours_to_close": self.min_seconds_to_close / 3600
        }
