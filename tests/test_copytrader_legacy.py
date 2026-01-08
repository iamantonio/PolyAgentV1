"""
Unit tests for CopyTrader module.

Tests the validation firewall and schema validation.
"""

import pytest
from datetime import datetime, timedelta
from agents.copytrader.schema import TradeIntent, TradeIntentMetadata, Side, Outcome
from agents.copytrader.firewall import IntentFirewall, ValidationError
from agents.copytrader.config import CopyTraderConfig


class TestTradeIntentSchema:
    """Test TradeIntent schema validation"""

    def test_valid_buy_intent(self):
        """Test creating a valid BUY intent"""
        intent = TradeIntent(
            source_trader="0x" + "a" * 40,
            market_id="test_market_123",
            outcome=Outcome.YES,
            side=Side.BUY,
            size_usdc=50.0,
            price_limit=0.65,
        )

        assert intent.source_trader == "0x" + "a" * 40
        assert intent.side == Side.BUY
        assert intent.size_usdc == 50.0
        assert intent.size_tokens is None

    def test_valid_sell_intent(self):
        """Test creating a valid SELL intent"""
        intent = TradeIntent(
            source_trader="0x" + "b" * 40,
            market_id="test_market_456",
            outcome=Outcome.NO,
            side=Side.SELL,
            size_tokens=100.0,
            price_limit=0.35,
        )

        assert intent.source_trader == "0x" + "b" * 40
        assert intent.side == Side.SELL
        assert intent.size_tokens == 100.0
        assert intent.size_usdc is None

    def test_invalid_address(self):
        """Test that invalid Ethereum addresses are rejected"""
        with pytest.raises(ValueError, match="must start with 0x"):
            TradeIntent(
                source_trader="invalid_address",
                market_id="test_market",
                outcome=Outcome.YES,
                side=Side.BUY,
                size_usdc=50.0,
            )

    def test_missing_size(self):
        """Test that intents without size are rejected"""
        with pytest.raises(ValueError, match="Must specify either size_usdc or size_tokens"):
            TradeIntent(
                source_trader="0x" + "a" * 40,
                market_id="test_market",
                outcome=Outcome.YES,
                side=Side.BUY,
            )

    def test_both_sizes(self):
        """Test that intents with both sizes are rejected"""
        with pytest.raises(ValueError, match="Cannot specify both"):
            TradeIntent(
                source_trader="0x" + "a" * 40,
                market_id="test_market",
                outcome=Outcome.YES,
                side=Side.BUY,
                size_usdc=50.0,
                size_tokens=100.0,
            )

    def test_buy_with_tokens(self):
        """Test that BUY orders must use size_usdc"""
        with pytest.raises(ValueError, match="BUY orders should specify size_usdc"):
            TradeIntent(
                source_trader="0x" + "a" * 40,
                market_id="test_market",
                outcome=Outcome.YES,
                side=Side.BUY,
                size_tokens=100.0,
            )

    def test_sell_with_usdc(self):
        """Test that SELL orders must use size_tokens"""
        with pytest.raises(ValueError, match="SELL orders should specify size_tokens"):
            TradeIntent(
                source_trader="0x" + "a" * 40,
                market_id="test_market",
                outcome=Outcome.YES,
                side=Side.SELL,
                size_usdc=50.0,
            )

    def test_staleness_check(self):
        """Test staleness detection"""
        old_intent = TradeIntent(
            source_trader="0x" + "a" * 40,
            market_id="test_market",
            outcome=Outcome.YES,
            side=Side.BUY,
            size_usdc=50.0,
            timestamp=datetime.utcnow() - timedelta(seconds=120),
        )

        assert old_intent.is_stale(max_age_seconds=60)
        assert not old_intent.is_stale(max_age_seconds=180)


class TestIntentFirewall:
    """Test intent validation firewall"""

    def create_test_intent(self, **kwargs):
        """Helper to create test intents"""
        defaults = {
            "source_trader": "0x" + "a" * 40,
            "market_id": "test_market",
            "outcome": Outcome.YES,
            "side": Side.BUY,
            "size_usdc": 50.0,
        }
        defaults.update(kwargs)
        return TradeIntent(**defaults)

    def test_trader_allowlist_pass(self):
        """Test that allowed traders pass validation"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
        )
        firewall = IntentFirewall(config)

        intent = self.create_test_intent(source_trader="0x" + "a" * 40)
        firewall.validate(intent)  # Should not raise

    def test_trader_allowlist_fail(self):
        """Test that non-allowed traders are rejected"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
        )
        firewall = IntentFirewall(config)

        intent = self.create_test_intent(source_trader="0x" + "b" * 40)

        with pytest.raises(ValidationError, match="not in allowlist"):
            firewall.validate(intent)

    def test_market_allowlist_pass(self):
        """Test that allowed markets pass validation"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
            allowed_markets={"test_market"},
        )
        firewall = IntentFirewall(config)

        intent = self.create_test_intent(market_id="test_market")
        firewall.validate(intent)  # Should not raise

    def test_market_allowlist_fail(self):
        """Test that non-allowed markets are rejected"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
            allowed_markets={"allowed_market"},
        )
        firewall = IntentFirewall(config)

        intent = self.create_test_intent(market_id="forbidden_market")

        with pytest.raises(ValidationError, match="not in allowlist"):
            firewall.validate(intent)

    def test_size_limit_usdc(self):
        """Test that oversized USDC intents are rejected"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
            max_intent_size_usdc=100.0,
        )
        firewall = IntentFirewall(config)

        intent = self.create_test_intent(size_usdc=150.0)

        with pytest.raises(ValidationError, match="exceeds maximum"):
            firewall.validate(intent)

    def test_size_limit_tokens(self):
        """Test that oversized token intents are rejected"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
            max_intent_size_tokens=500.0,
        )
        firewall = IntentFirewall(config)

        intent = self.create_test_intent(
            side=Side.SELL, size_usdc=None, size_tokens=1000.0
        )

        with pytest.raises(ValidationError, match="exceeds maximum"):
            firewall.validate(intent)

    def test_staleness_rejection(self):
        """Test that stale intents are rejected"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
            max_intent_age_seconds=60,
        )
        firewall = IntentFirewall(config)

        old_intent = self.create_test_intent(
            timestamp=datetime.utcnow() - timedelta(seconds=120)
        )

        with pytest.raises(ValidationError, match="stale"):
            firewall.validate(old_intent)

    def test_deduplication(self):
        """Test that duplicate intents are rejected"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
        )
        firewall = IntentFirewall(config)

        intent = self.create_test_intent(intent_id="test-intent-123")

        # First validation should pass
        firewall.validate(intent)

        # Second validation of same intent should fail
        with pytest.raises(ValidationError, match="Duplicate intent"):
            firewall.validate(intent)

    def test_minimum_size_rejection(self):
        """Test that intents below minimum are rejected"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40},
            min_order_size_usdc=10.0,
        )
        firewall = IntentFirewall(config)

        small_intent = self.create_test_intent(size_usdc=5.0)

        with pytest.raises(ValidationError, match="below Polymarket minimum"):
            firewall.validate(small_intent)

    def test_firewall_stats(self):
        """Test that firewall stats are tracked"""
        config = CopyTraderConfig(
            allowed_traders={"0x" + "a" * 40, "0x" + "b" * 40},
            allowed_markets={"market1", "market2", "market3"},
        )
        firewall = IntentFirewall(config)

        stats = firewall.get_stats()

        assert stats["allowed_traders_count"] == 2
        assert stats["allowed_markets_count"] == 3
        assert stats["max_intent_size_usdc"] == 100.0
        assert stats["seen_intents_count"] == 0


class TestConfigFromEnv:
    """Test configuration loading from environment"""

    def test_config_from_env(self, monkeypatch):
        """Test loading config from environment variables"""
        monkeypatch.setenv("FOLLOW_TRADERS", "0xabc123,0xdef456")
        monkeypatch.setenv("MARKET_ALLOWLIST", "market1,market2")
        monkeypatch.setenv("MAX_INTENT_SIZE_USDC", "200.0")
        monkeypatch.setenv("MAX_INTENT_AGE_SECONDS", "30")

        config = CopyTraderConfig.from_env()

        assert "0xabc123" in config.allowed_traders
        assert "0xdef456" in config.allowed_traders
        assert "market1" in config.allowed_markets
        assert "market2" in config.allowed_markets
        assert config.max_intent_size_usdc == 200.0
        assert config.max_intent_age_seconds == 30
