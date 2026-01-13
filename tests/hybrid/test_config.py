"""Tests for hybrid bot configuration."""

import pytest
from decimal import Decimal

from agents.hybrid.config import (
    HybridConfig,
    RiskLimits,
    LearningConfig,
    KellySizingConfig,
    ArbitrageConfig,
    ExecutionConfig,
    get_default_config,
    get_aggressive_config,
    get_conservative_config,
)


class TestRiskLimits:
    """Tests for RiskLimits configuration."""

    def test_default_values(self):
        """Test default risk limits."""
        limits = RiskLimits()
        assert limits.max_position_size == Decimal("50")
        assert limits.max_total_exposure == Decimal("200")
        assert limits.max_daily_loss == Decimal("25")
        assert limits.max_positions == 10
        assert limits.cooldown_after_loss == 300

    def test_validation_positive_values(self):
        """Test that limits must be positive."""
        with pytest.raises(ValueError, match="max_position_size must be positive"):
            RiskLimits(max_position_size=Decimal("-1"))

        with pytest.raises(ValueError, match="max_total_exposure must be positive"):
            RiskLimits(max_total_exposure=Decimal("0"))

    def test_validation_daily_loss(self):
        """Test daily loss must be positive."""
        with pytest.raises(ValueError, match="max_daily_loss must be positive"):
            RiskLimits(max_daily_loss=Decimal("-10"))

    def test_immutability(self):
        """Test that config is frozen."""
        limits = RiskLimits()
        with pytest.raises(Exception):  # FrozenInstanceError
            limits.max_position_size = Decimal("100")


class TestArbitrageConfig:
    """Tests for ArbitrageConfig."""

    def test_default_values(self):
        """Test default arbitrage config."""
        config = ArbitrageConfig()
        assert config.enabled is True
        assert config.min_profit == Decimal("0.005")
        assert config.fee_rate == Decimal("0.02")
        assert config.max_size == Decimal("500")

    def test_validation(self):
        """Test arbitrage validation."""
        with pytest.raises(ValueError, match="min_profit must be non-negative"):
            ArbitrageConfig(min_profit=Decimal("-0.01"))


class TestKellySizingConfig:
    """Tests for KellySizingConfig."""

    def test_default_values(self):
        """Test default Kelly config."""
        config = KellySizingConfig()
        assert config.enabled is True
        assert config.fraction == Decimal("0.25")
        assert config.max_bet_fraction == Decimal("0.10")

    def test_validation_fraction_range(self):
        """Test Kelly fraction must be in (0, 1]."""
        with pytest.raises(ValueError, match="fraction must be 0-1"):
            KellySizingConfig(fraction=Decimal("0"))

        with pytest.raises(ValueError, match="fraction must be 0-1"):
            KellySizingConfig(fraction=Decimal("1.5"))


class TestLearningConfig:
    """Tests for LearningConfig."""

    def test_default_values(self):
        """Test default learning config."""
        config = LearningConfig()
        assert config.min_confidence == Decimal("0.55")
        assert config.use_multi_agent is True

    def test_validation_confidence_range(self):
        """Test confidence must be in [0, 1]."""
        with pytest.raises(ValueError, match="min_confidence must be 0-1"):
            LearningConfig(min_confidence=Decimal("1.5"))

        with pytest.raises(ValueError, match="min_confidence must be 0-1"):
            LearningConfig(min_confidence=Decimal("-0.1"))


class TestExecutionConfig:
    """Tests for ExecutionConfig."""

    def test_default_dry_run(self):
        """Test dry_run defaults to True."""
        config = ExecutionConfig()
        assert config.dry_run is True

    def test_validation(self):
        """Test execution validation."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            ExecutionConfig(max_retries=-1)


class TestConfigPresets:
    """Tests for configuration presets."""

    def test_default_config(self):
        """Test default configuration."""
        config = get_default_config()
        assert config.bankroll == Decimal("100")
        assert config.execution.dry_run is True
        assert config.arbitrage.enabled is True

    def test_aggressive_config(self):
        """Test aggressive configuration."""
        config = get_aggressive_config()
        assert config.bankroll == Decimal("100")
        assert config.risk.max_position_size == Decimal("100")
        assert config.kelly.fraction == Decimal("0.50")

    def test_conservative_config(self):
        """Test conservative configuration."""
        config = get_conservative_config()
        assert config.bankroll == Decimal("100")
        assert config.risk.max_position_size == Decimal("25")
        assert config.learning.min_confidence == Decimal("0.65")


class TestHybridConfig:
    """Tests for main HybridConfig."""

    def test_all_components_present(self):
        """Test all components are initialized."""
        config = HybridConfig()
        assert config.risk is not None
        assert config.learning is not None
        assert config.kelly is not None
        assert config.arbitrage is not None
        assert config.market_making is not None
        assert config.execution is not None
        assert config.alerts is not None

    def test_bankroll_validation(self):
        """Test bankroll must be positive."""
        with pytest.raises(ValueError, match="bankroll must be positive"):
            HybridConfig(bankroll=Decimal("0"))
