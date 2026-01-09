"""
Tests for Market Opportunity Scoring System
"""

import pytest
from typing import List, Dict, Any
from datetime import datetime, timedelta
from agents.application.opportunity_scorer import OpportunityScorer
from agents.connectors.volatility import VolatilityCalculator


class TestVolatilityCalculator:
    """Test volatility calculation components."""

    def test_calculate_volatility_flat_prices(self):
        """Test volatility calculation with flat prices."""
        calc = VolatilityCalculator()

        # Flat prices = zero volatility
        history = [{"timestamp": datetime.now().isoformat(), "price": 0.5} for _ in range(10)]
        volatility = calc.calculate_volatility(history)

        assert volatility == 0.0

    def test_calculate_volatility_varying_prices(self):
        """Test volatility calculation with varying prices."""
        calc = VolatilityCalculator()

        # Prices that vary
        history = [
            {"timestamp": datetime.now().isoformat(), "price": 0.5},
            {"timestamp": datetime.now().isoformat(), "price": 0.6},
            {"timestamp": datetime.now().isoformat(), "price": 0.4},
            {"timestamp": datetime.now().isoformat(), "price": 0.55},
        ]
        volatility = calc.calculate_volatility(history)

        assert volatility > 0.0
        assert volatility < 1.0

    def test_detect_price_spike(self):
        """Test price spike detection."""
        calc = VolatilityCalculator()

        # Normal prices then a spike
        history = [
            {"timestamp": datetime.now().isoformat(), "price": 0.50},
            {"timestamp": datetime.now().isoformat(), "price": 0.51},
            {"timestamp": datetime.now().isoformat(), "price": 0.49},
            {"timestamp": datetime.now().isoformat(), "price": 0.50},
            {"timestamp": datetime.now().isoformat(), "price": 0.80},  # Spike!
        ]

        has_spike = calc.detect_price_spike(history)
        assert has_spike is True

    def test_calculate_trend_strength_upward(self):
        """Test trend detection for upward trend."""
        calc = VolatilityCalculator()

        # Upward trend
        history = [
            {"timestamp": datetime.now().isoformat(), "price": 0.40},
            {"timestamp": datetime.now().isoformat(), "price": 0.50},
            {"timestamp": datetime.now().isoformat(), "price": 0.60},
            {"timestamp": datetime.now().isoformat(), "price": 0.70},
        ]

        trend = calc.calculate_trend_strength(history)
        assert trend > 0.0  # Positive trend

    def test_calculate_trend_strength_downward(self):
        """Test trend detection for downward trend."""
        calc = VolatilityCalculator()

        # Downward trend
        history = [
            {"timestamp": datetime.now().isoformat(), "price": 0.70},
            {"timestamp": datetime.now().isoformat(), "price": 0.60},
            {"timestamp": datetime.now().isoformat(), "price": 0.50},
            {"timestamp": datetime.now().isoformat(), "price": 0.40},
        ]

        trend = calc.calculate_trend_strength(history)
        assert trend < 0.0  # Negative trend

    def test_simulate_price_history(self):
        """Test price history simulation."""
        calc = VolatilityCalculator()

        history = calc.simulate_price_history(
            current_price=0.5,
            volatility=0.05,
            num_points=24
        )

        assert len(history) == 24
        assert all(0.0 < p["price"] < 1.0 for p in history)
        assert all("timestamp" in p for p in history)


class TestOpportunityScorer:
    """Test opportunity scoring system."""

    def create_mock_market(
        self,
        question: str = "Test market",
        outcome_prices: List[float] = None,
        description: str = ""
    ):
        """Create mock market object for testing."""
        if outcome_prices is None:
            outcome_prices = [0.5, 0.5]

        class MockDocument:
            def dict(self):
                return {
                    "metadata": {
                        "question": question,
                        "description": description,
                        "outcome_prices": str(outcome_prices),
                        "condition_id": "test_market_123"
                    }
                }

        return [MockDocument()]

    def test_scorer_initialization(self):
        """Test scorer initialization."""
        scorer = OpportunityScorer(
            enable_social_signals=False,
            enable_volatility=True
        )

        assert scorer.enable_volatility is True
        assert scorer.enable_social_signals is False

    def test_score_liquidity(self):
        """Test liquidity scoring."""
        scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=False)

        # High liquidity = max points
        assert scorer._score_liquidity(150_000) == 25.0
        assert scorer._score_liquidity(60_000) == 20.0
        assert scorer._score_liquidity(15_000) == 15.0
        assert scorer._score_liquidity(500) == 2.0

    def test_score_volatility(self):
        """Test volatility scoring."""
        scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=True)

        # High volatility with spike = max points
        metrics = {
            "volatility": 0.20,
            "spike_detected": True
        }
        score = scorer._score_volatility(metrics)
        assert score == 25.0

        # Low volatility, no spike
        metrics = {
            "volatility": 0.02,
            "spike_detected": False
        }
        score = scorer._score_volatility(metrics)
        assert 0.0 < score < 10.0

    def test_score_time_to_close(self):
        """Test time-to-close scoring."""
        scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=False)

        # Sweet spot: 2-7 days
        assert scorer._score_time_to_close(5) == 15.0
        assert scorer._score_time_to_close(10) == 10.0
        assert scorer._score_time_to_close(1.5) == 8.0

    def test_score_spread(self):
        """Test spread scoring."""
        scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=False)

        # Wide spread = high points
        assert scorer._score_spread(0.15) == 15.0
        assert scorer._score_spread(0.06) == 12.0
        assert scorer._score_spread(0.01) == 2.0

    def test_calculate_opportunity_score_basic(self):
        """Test full opportunity score calculation."""
        scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=True)

        market = self.create_mock_market(
            question="Will Bitcoin reach $100k by end of 2026?",
            outcome_prices=[0.3, 0.7],
            description="Bitcoin price prediction market"
        )

        score_data = scorer.calculate_opportunity_score(market)

        # Check structure
        assert "total_score" in score_data
        assert "liquidity_score" in score_data
        assert "volatility_score" in score_data
        assert "social_score" in score_data
        assert "time_score" in score_data
        assert "spread_score" in score_data

        # Score should be in valid range
        assert 0.0 <= score_data["total_score"] <= 100.0

        # Should have wide spread (0.7 - 0.3 = 0.4)
        assert score_data["spread_score"] > 10.0

    def test_score_markets_sorting(self):
        """Test that markets are sorted by score."""
        scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=True)

        markets = [
            self.create_mock_market(
                question="Low quality short market",
                outcome_prices=[0.95, 0.05]  # Extreme prices = lower score
            ),
            self.create_mock_market(
                question="High quality market with good spread and interesting question about an upcoming event",
                outcome_prices=[0.4, 0.6]  # Good spread
            ),
        ]

        scored_markets = scorer.score_markets(markets)

        assert len(scored_markets) == 2
        # First market should have higher score
        assert scored_markets[0][1]["total_score"] >= scored_markets[1][1]["total_score"]

    def test_allocate_budget(self):
        """Test budget allocation."""
        scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=True)

        # Create scored markets (simulate already scored)
        scored_markets = [
            (None, {"market_id": "market_1", "total_score": 90.0, "question": "Market 1"}),
            (None, {"market_id": "market_2", "total_score": 70.0, "question": "Market 2"}),
            (None, {"market_id": "market_3", "total_score": 50.0, "question": "Market 3"}),
        ]

        allocations = scorer.allocate_budget(scored_markets, daily_budget=100.0, top_n=3)

        # Check that all markets get budget
        assert len(allocations) == 3

        # Top market should get most budget
        assert allocations["market_1"] > allocations["market_2"]
        assert allocations["market_2"] > allocations["market_3"]

        # Total should roughly equal budget (within rounding)
        total_allocated = sum(allocations.values())
        assert abs(total_allocated - 100.0) < 0.01

    def test_crypto_detection_scoring(self):
        """Test that crypto markets get social scoring."""
        scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=False)

        market = self.create_mock_market(
            question="Will Bitcoin reach $100k?",
            description="Bitcoin price prediction"
        )

        # Should detect crypto even without social signals enabled
        if scorer.lunar_crush:
            crypto_token = scorer.lunar_crush.detect_crypto_token(
                "Will Bitcoin reach $100k?",
                "Bitcoin price prediction"
            )
            assert crypto_token == "bitcoin"


def test_integration_scorer_with_volatility():
    """Integration test: scorer + volatility calculator."""
    scorer = OpportunityScorer(enable_social_signals=False, enable_volatility=True)
    calc = VolatilityCalculator()

    # Create market with proper mock
    class MockDocument:
        def dict(self):
            return {
                "metadata": {
                    "question": "Test market with volatility",
                    "description": "",
                    "outcome_prices": "[0.4, 0.6]",
                    "condition_id": "test_market"
                }
            }

    market_obj = [MockDocument()]

    # Simulate volatile price history
    price_history = calc.simulate_price_history(
        current_price=0.5,
        volatility=0.10,  # High volatility
        num_points=24
    )

    # Score with history
    score_data = scorer.calculate_opportunity_score(market_obj, price_history)

    # Should get volatility score
    assert score_data["volatility_score"] > 0.0
    assert "volatility_metrics" in score_data["details"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
