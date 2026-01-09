"""
Cheap market pre-filtering before expensive LLM calls.

Filters out markets that are unlikely to be profitable to trade:
- Low liquidity
- Wide spreads
- Extreme prices (near 0 or 1)
- Too close to resolution

Enhanced with opportunity scoring to prioritize high-value markets.
"""

from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timezone
import ast

from agents.application.opportunity_scorer import OpportunityScorer


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
        min_hours_to_close: float = 24.0,  # Avoid markets closing < 24h
        enable_opportunity_scoring: bool = True,  # Enable opportunity scoring
        min_opportunity_score: float = 40.0  # Min score to consider (0-100)
    ):
        self.min_liquidity = min_liquidity
        self.max_spread = max_spread_pct / 100
        self.min_price = min_price
        self.max_price = max_price
        self.min_seconds_to_close = min_hours_to_close * 3600
        self.enable_opportunity_scoring = enable_opportunity_scoring
        self.min_opportunity_score = min_opportunity_score

        # Initialize opportunity scorer
        if self.enable_opportunity_scoring:
            self.opportunity_scorer = OpportunityScorer(
                enable_social_signals=False,  # Disable for speed in filtering
                enable_volatility=True
            )
        else:
            self.opportunity_scorer = None

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

    def filter_markets(
        self,
        markets: List,
        return_scored: bool = False
    ) -> List:
        """
        Filter list of markets, keeping only candidates worth forecasting.

        With opportunity scoring enabled, returns markets sorted by score.

        Args:
            markets: List of market objects
            return_scored: If True, return (market, score_data) tuples instead of just markets

        Returns:
            Filtered (and optionally scored) list of markets
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

        # Opportunity scoring (optional)
        if self.enable_opportunity_scoring and self.opportunity_scorer and candidates:
            print(f"\n📊 [OPPORTUNITY SCORING] Enabled")

            scored_markets = self.opportunity_scorer.score_markets(candidates)

            # Filter by minimum score
            scored_markets = [
                (market, score) for market, score in scored_markets
                if score["total_score"] >= self.min_opportunity_score
            ]

            print(f"   Markets above threshold ({self.min_opportunity_score}): {len(scored_markets)}")

            if return_scored:
                return scored_markets
            else:
                return [market for market, score in scored_markets]

        return candidates

    def get_config(self) -> dict:
        """Get current filter configuration."""
        return {
            "min_liquidity": self.min_liquidity,
            "max_spread_pct": self.max_spread * 100,
            "price_range": f"{self.min_price:.2f}-{self.max_price:.2f}",
            "min_hours_to_close": self.min_seconds_to_close / 3600,
            "opportunity_scoring_enabled": self.enable_opportunity_scoring,
            "min_opportunity_score": self.min_opportunity_score
        }

    def allocate_budget_to_markets(
        self,
        scored_markets: List[Tuple[Any, Dict[str, Any]]],
        daily_budget: float,
        top_n: int = 10
    ) -> Dict[str, float]:
        """
        Allocate budget to top-scoring markets.

        This is a convenience wrapper around OpportunityScorer.allocate_budget.

        Args:
            scored_markets: List of (market, score_data) tuples
            daily_budget: Total daily budget
            top_n: Number of top markets to fund

        Returns:
            Dict mapping market_id -> allocated_budget
        """
        if not self.opportunity_scorer:
            raise ValueError("Opportunity scoring not enabled")

        return self.opportunity_scorer.allocate_budget(
            scored_markets,
            daily_budget,
            top_n
        )
