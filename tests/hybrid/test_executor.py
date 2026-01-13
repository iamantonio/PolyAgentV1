"""Tests for hybrid bot order executor."""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone

from agents.hybrid.execution.executor import (
    OrderExecutor,
    ExecutionResult,
    ExecutionError,
    IdempotencyViolation,
)
from agents.hybrid.strategies.base import StrategyIntent
from agents.hybrid.config import ExecutionConfig


# Helper to run async tests
def run_async(coro):
    """Run async coroutine in sync test."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_successful_result(self):
        """Test successful execution result."""
        result = ExecutionResult(
            success=True,
            order_id="order-123",
            fill_price=Decimal("0.55"),
            fill_size=Decimal("10"),
            error=None,
            dry_run=True,
        )
        assert result.success is True
        assert result.order_id == "order-123"
        assert "DRY-RUN" in repr(result)

    def test_failed_result(self):
        """Test failed execution result."""
        result = ExecutionResult(
            success=False,
            order_id=None,
            fill_price=None,
            fill_size=None,
            error="Connection failed",
        )
        assert result.success is False
        assert "FAILED" in repr(result)


class TestOrderExecutor:
    """Tests for OrderExecutor."""

    @pytest.fixture
    def dry_run_executor(self):
        """Create a dry-run executor."""
        config = ExecutionConfig(
            dry_run=True,
            max_retries=2,
            retry_delay_ms=100,
        )
        return OrderExecutor(config=config)

    @pytest.fixture
    def sample_intent(self):
        """Create a sample trading intent."""
        return StrategyIntent(
            market_id="test-market",
            token_id="token-123",
            outcome="YES",
            side="buy",
            price=Decimal("0.55"),
            size=Decimal("10"),
            reason="Test trade",
            strategy_name="test",
            confidence=Decimal("0.60"),
        )

    def test_dry_run_execution(self, dry_run_executor, sample_intent):
        """Test dry-run execution."""
        result = run_async(dry_run_executor.execute(sample_intent))

        assert result.success is True
        assert result.dry_run is True
        assert result.fill_price == sample_intent.price
        assert result.fill_size == sample_intent.size
        assert result.order_id.startswith("dry-")

    def test_validation_price_too_low(self, dry_run_executor):
        """Test intent rejected for price too low."""
        intent = StrategyIntent(
            market_id="test",
            token_id="token",
            outcome="YES",
            side="buy",
            price=Decimal("0.005"),  # Below 0.01 minimum
            size=Decimal("10"),
            reason="Test",
            strategy_name="test",
        )

        result = run_async(dry_run_executor.execute(intent))
        assert result.success is False
        assert "below minimum" in result.error.lower()

    def test_validation_price_too_high(self, dry_run_executor):
        """Test intent rejected for price too high."""
        intent = StrategyIntent(
            market_id="test",
            token_id="token",
            outcome="YES",
            side="buy",
            price=Decimal("0.995"),  # Above 0.99 maximum
            size=Decimal("10"),
            reason="Test",
            strategy_name="test",
        )

        result = run_async(dry_run_executor.execute(intent))
        assert result.success is False
        assert "above maximum" in result.error.lower()

    def test_validation_invalid_side(self, dry_run_executor):
        """Test intent rejected for invalid side."""
        intent = StrategyIntent(
            market_id="test",
            token_id="token",
            outcome="YES",
            side="invalid",  # Not buy or sell
            price=Decimal("0.50"),
            size=Decimal("10"),
            reason="Test",
            strategy_name="test",
        )

        result = run_async(dry_run_executor.execute(intent))
        assert result.success is False
        assert "invalid side" in result.error.lower()

    def test_idempotency_duplicate_rejected(self, dry_run_executor, sample_intent):
        """Test duplicate intent is rejected."""
        # First execution should succeed
        result1 = run_async(dry_run_executor.execute(sample_intent))
        assert result1.success is True

        # Second execution of same intent should fail
        result2 = run_async(dry_run_executor.execute(sample_intent))
        assert result2.success is False
        assert "duplicate" in result2.error.lower() or "idempotency" in result2.error.lower()

    def test_different_intents_allowed(self, dry_run_executor):
        """Test different intents are allowed."""
        intent1 = StrategyIntent(
            market_id="market1",
            token_id="token1",
            outcome="YES",
            side="buy",
            price=Decimal("0.50"),
            size=Decimal("10"),
            reason="Trade 1",
            strategy_name="test",
        )

        intent2 = StrategyIntent(
            market_id="market2",
            token_id="token2",
            outcome="YES",
            side="buy",
            price=Decimal("0.55"),
            size=Decimal("10"),
            reason="Trade 2",
            strategy_name="test",
        )

        result1 = run_async(dry_run_executor.execute(intent1))
        result2 = run_async(dry_run_executor.execute(intent2))

        assert result1.success is True
        assert result2.success is True

    def test_execute_pair(self, dry_run_executor):
        """Test executing a pair of intents (arbitrage)."""
        yes_intent = StrategyIntent(
            market_id="test",
            token_id="yes-token",
            outcome="YES",
            side="buy",
            price=Decimal("0.45"),
            size=Decimal("10"),
            reason="Arbitrage YES",
            strategy_name="arbitrage",
        )

        no_intent = StrategyIntent(
            market_id="test",
            token_id="no-token",
            outcome="NO",
            side="buy",
            price=Decimal("0.45"),
            size=Decimal("10"),
            reason="Arbitrage NO",
            strategy_name="arbitrage",
        )

        yes_result, no_result = run_async(dry_run_executor.execute_pair(yes_intent, no_intent))

        assert yes_result.success is True
        assert no_result.success is True

    def test_get_status(self, dry_run_executor):
        """Test status reporting."""
        status = dry_run_executor.get_status()
        assert status["dry_run"] is True
        assert "max_retries" in status
        assert "tracked_hashes" in status


class TestOrderExecutorLiveMode:
    """Tests for live mode execution."""

    @pytest.fixture
    def live_executor_no_client(self):
        """Create a live executor without client."""
        config = ExecutionConfig(
            dry_run=False,
            max_retries=1,
        )
        return OrderExecutor(config=config, polymarket_client=None)

    def test_live_without_client_fails(self, live_executor_no_client):
        """Test live execution without client fails gracefully."""
        intent = StrategyIntent(
            market_id="test",
            token_id="token",
            outcome="YES",
            side="buy",
            price=Decimal("0.50"),
            size=Decimal("10"),
            reason="Test",
            strategy_name="test",
        )

        result = run_async(live_executor_no_client.execute(intent))
        assert result.success is False
        assert "no polymarket client" in result.error.lower()
