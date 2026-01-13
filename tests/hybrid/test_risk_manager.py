"""Tests for hybrid bot risk manager."""

import pytest
from decimal import Decimal

from agents.hybrid.risk.manager import RiskManager, RiskCheckResult
from agents.hybrid.config import RiskLimits


class TestRiskCheckResult:
    """Tests for RiskCheckResult dataclass."""

    def test_approved_result(self):
        """Test approved result."""
        result = RiskCheckResult(approved=True, reason="Trade allowed")
        assert result.approved is True
        assert result.adjusted_size is None

    def test_rejected_result(self):
        """Test rejected result."""
        result = RiskCheckResult(approved=False, reason="Position limit exceeded")
        assert result.approved is False

    def test_adjusted_size(self):
        """Test result with adjusted size."""
        result = RiskCheckResult(
            approved=True,
            reason="Size reduced",
            adjusted_size=Decimal("25"),
        )
        assert result.approved is True
        assert result.adjusted_size == Decimal("25")


class TestRiskManager:
    """Tests for RiskManager."""

    @pytest.fixture
    def risk_manager(self):
        """Create a risk manager for testing."""
        limits = RiskLimits(
            max_position_size=Decimal("50"),
            max_total_exposure=Decimal("200"),
            max_daily_loss=Decimal("25"),
            max_positions=10,
            cooldown_after_loss=300,
        )
        return RiskManager(
            limits=limits,
            get_daily_pnl=lambda: Decimal("0"),
            get_open_positions=lambda: [],
            get_position_value=lambda m: Decimal("0"),
        )

    def test_can_trade_normal(self, risk_manager):
        """Test normal trading allowed."""
        can_trade, reason = risk_manager.can_trade(Decimal("100"))
        assert can_trade is True

    def test_can_trade_low_balance(self, risk_manager):
        """Test trading blocked on low balance."""
        can_trade, reason = risk_manager.can_trade(Decimal("5"))
        assert can_trade is False
        assert "below minimum" in reason.lower()

    def test_can_trade_daily_loss_limit(self):
        """Test trading blocked after daily loss limit."""
        limits = RiskLimits(max_daily_loss=Decimal("25"))
        manager = RiskManager(
            limits=limits,
            get_daily_pnl=lambda: Decimal("-30"),  # Lost $30 today
            get_open_positions=lambda: [],
            get_position_value=lambda m: Decimal("0"),
        )

        can_trade, reason = manager.can_trade(Decimal("100"))
        assert can_trade is False
        assert "loss limit" in reason.lower()

    def test_validate_intent_approved(self, risk_manager):
        """Test valid intent is approved."""
        result = risk_manager.validate_intent(
            market_id="test-market",
            market_type="other",
            side="buy",
            price=Decimal("0.55"),
            size=Decimal("10"),
            balance=Decimal("100"),
            confidence=Decimal("0.60"),
        )
        assert result.approved is True

    def test_validate_intent_exceeds_position_limit(self, risk_manager):
        """Test intent adjusted for exceeding position limit."""
        result = risk_manager.validate_intent(
            market_id="test-market",
            market_type="other",
            side="buy",
            price=Decimal("0.55"),
            size=Decimal("100"),  # $100 > $50 limit
            balance=Decimal("500"),
            confidence=Decimal("0.60"),
        )
        # Should be approved with adjusted size
        assert result.approved is True

    def test_validate_intent_too_small(self, risk_manager):
        """Test intent rejected for being too small."""
        result = risk_manager.validate_intent(
            market_id="test-market",
            market_type="other",
            side="buy",
            price=Decimal("0.55"),
            size=Decimal("0.5"),  # Below minimum
            balance=Decimal("100"),
            confidence=Decimal("0.60"),
        )
        assert result.approved is False
        assert "min" in result.reason.lower()

    def test_validate_arbitrage_approved(self, risk_manager):
        """Test valid arbitrage is approved."""
        result = risk_manager.validate_arbitrage(
            market_id="test-market",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.45"),
            size=Decimal("50"),
            balance=Decimal("100"),
        )
        assert result.approved is True

    def test_validate_arbitrage_small_size(self, risk_manager):
        """Test arbitrage rejected for small size."""
        result = risk_manager.validate_arbitrage(
            market_id="test-market",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.45"),
            size=Decimal("10"),  # Below MIN_ARB_SIZE of 25
            balance=Decimal("100"),
        )
        assert result.approved is False
        assert "minimum" in result.reason.lower()

    def test_edge_based_filtering(self, risk_manager):
        """Test edge-based market filtering."""
        # Update edge data
        risk_manager.update_edge_data({
            "crypto": Decimal("5.0"),
            "sports": Decimal("-3.0"),  # Negative edge
        })

        # Crypto should pass
        has_edge, reason = risk_manager.check_market_edge("crypto")
        assert has_edge is True

        # Sports should fail
        has_edge, reason = risk_manager.check_market_edge("sports")
        assert has_edge is False
        assert "negative edge" in reason.lower()

    def test_cooldown_after_loss(self):
        """Test cooldown period after recording loss."""
        import time

        limits = RiskLimits(
            max_daily_loss=Decimal("25"),
            cooldown_after_loss=300,
        )
        manager = RiskManager(
            limits=limits,
            get_daily_pnl=lambda: Decimal("0"),
            get_open_positions=lambda: [],
            get_position_value=lambda m: Decimal("0"),
        )

        # Set last loss time to now
        manager.set_last_loss_time(time.time())

        # Should be in cooldown
        can_trade, reason = manager.can_trade(Decimal("100"))
        assert can_trade is False
        assert "cooldown" in reason.lower()

    def test_get_status(self, risk_manager):
        """Test status reporting."""
        status = risk_manager.get_status()
        assert "daily_pnl" in status
        assert "daily_loss_limit" in status
        assert "open_positions" in status
        assert "max_positions" in status
        assert "in_cooldown" in status


class TestRiskManagerWithPositions:
    """Tests for RiskManager with existing positions."""

    def test_max_positions_check(self):
        """Test max positions enforcement."""
        limits = RiskLimits(
            max_position_size=Decimal("50"),
            max_total_exposure=Decimal("200"),
            max_positions=2,  # Low limit for testing
        )

        # Simulate existing positions
        positions = [
            {"market_id": "market1", "size": 10, "entry_price": 0.5},
            {"market_id": "market2", "size": 10, "entry_price": 0.5},
        ]

        manager = RiskManager(
            limits=limits,
            get_daily_pnl=lambda: Decimal("0"),
            get_open_positions=lambda: positions,
            get_position_value=lambda m: Decimal("0"),
        )

        # New trade should be rejected due to max positions
        result = manager.validate_intent(
            market_id="market3",
            market_type="other",
            side="buy",
            price=Decimal("0.50"),
            size=Decimal("10"),
            balance=Decimal("200"),
            confidence=Decimal("0.60"),
        )
        assert result.approved is False
        assert "max positions" in result.reason.lower()

    def test_total_exposure_check(self):
        """Test total exposure calculation."""
        limits = RiskLimits(
            max_position_size=Decimal("50"),
            max_total_exposure=Decimal("50"),  # Very low for testing
        )

        # Simulate high exposure (total = 50 + 45 = 95)
        positions = [
            {"market_id": "market1", "size": 50, "entry_price": 1.0},
            {"market_id": "market2", "size": 45, "entry_price": 1.0},
        ]

        manager = RiskManager(
            limits=limits,
            get_daily_pnl=lambda: Decimal("0"),
            get_open_positions=lambda: positions,
            get_position_value=lambda m: Decimal("40"),
        )

        # New trade would exceed total exposure (95 existing + 20 new > 50)
        result = manager.validate_intent(
            market_id="market3",
            market_type="other",
            side="buy",
            price=Decimal("0.50"),
            size=Decimal("20"),
            balance=Decimal("200"),
            confidence=Decimal("0.60"),
        )
        # Should be rejected since we already exceed limit
        assert result.approved is False
