"""
Order Executor for Hybrid Bot

Bridges StrategyIntents to actual Polymarket orders.

Features:
- Dry-run mode for safe testing
- Idempotency (duplicate prevention)
- Retry logic with backoff
- Full audit logging
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
import logging
import hashlib
import time
import uuid

from agents.hybrid.strategies.base import StrategyIntent
from agents.hybrid.config import ExecutionConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """
    Result of an order execution attempt.
    """
    success: bool
    order_id: Optional[str]
    fill_price: Optional[Decimal]
    fill_size: Optional[Decimal]
    error: Optional[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    dry_run: bool = False
    intent_hash: Optional[str] = None

    def __repr__(self) -> str:
        if self.success:
            mode = "DRY-RUN" if self.dry_run else "LIVE"
            return f"ExecutionResult({mode}: {self.fill_size}@{self.fill_price}, order={self.order_id})"
        return f"ExecutionResult(FAILED: {self.error})"


class ExecutionError(Exception):
    """Raised when execution fails."""
    pass


class IdempotencyViolation(ExecutionError):
    """Raised when a duplicate trade is detected."""
    pass


class OrderExecutor:
    """
    Order executor with safety features.

    Responsibilities:
    - Validate intents before execution
    - Prevent duplicate orders (idempotency)
    - Execute via Polymarket API (or dry-run)
    - Log all execution attempts
    """

    # Polymarket price constraints
    MIN_PRICE = Decimal("0.01")
    MAX_PRICE = Decimal("0.99")
    MIN_SIZE = Decimal("0.01")

    def __init__(
        self,
        config: ExecutionConfig,
        polymarket_client: Optional[Any] = None,
        db: Optional[Any] = None,
    ):
        """
        Initialize executor.

        Args:
            config: Execution configuration
            polymarket_client: Polymarket API client
            db: Database for logging/idempotency
        """
        self._config = config
        self._client = polymarket_client
        self._db = db

        # Idempotency tracking
        self._executed_hashes: Dict[str, float] = {}  # hash -> timestamp
        self._idempotency_window = config.idempotency_window_hours * 3600

        mode = "DRY-RUN" if config.dry_run else "LIVE"
        logger.info(f"OrderExecutor initialized in {mode} mode")

    @property
    def dry_run(self) -> bool:
        return self._config.dry_run

    def _generate_intent_hash(self, intent: StrategyIntent) -> str:
        """
        Generate unique hash for an intent.

        Used for idempotency checking.
        """
        data = (
            f"{intent.market_id}|{intent.token_id}|{intent.outcome}|"
            f"{intent.side}|{intent.price}|{intent.size}|"
            f"{intent.strategy_name}|{intent.timestamp.isoformat()[:19]}"
        )
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _check_idempotency(self, intent_hash: str) -> bool:
        """
        Check if this intent was already executed.

        Returns True if safe to execute, False if duplicate.
        """
        now = time.time()

        # Clean old entries
        self._executed_hashes = {
            h: ts for h, ts in self._executed_hashes.items()
            if (now - ts) < self._idempotency_window
        }

        # Check for duplicate
        if intent_hash in self._executed_hashes:
            return False

        return True

    def _record_execution(self, intent_hash: str) -> None:
        """Record an intent hash as executed."""
        self._executed_hashes[intent_hash] = time.time()

    def _validate_intent(self, intent: StrategyIntent) -> None:
        """
        Validate intent parameters.

        Raises:
            ExecutionError: If validation fails
        """
        # Price validation
        if intent.price < self.MIN_PRICE:
            raise ExecutionError(f"Price {intent.price} below minimum {self.MIN_PRICE}")
        if intent.price > self.MAX_PRICE:
            raise ExecutionError(f"Price {intent.price} above maximum {self.MAX_PRICE}")

        # Size validation
        if intent.size < self.MIN_SIZE:
            raise ExecutionError(f"Size {intent.size} below minimum {self.MIN_SIZE}")

        # Side validation
        if intent.side not in ("buy", "sell"):
            raise ExecutionError(f"Invalid side: {intent.side}")

        # Market ID validation
        if not intent.market_id or not intent.token_id:
            raise ExecutionError("Market ID and Token ID required")

    async def execute(self, intent: StrategyIntent) -> ExecutionResult:
        """
        Execute a trading intent.

        Steps:
        1. Validate intent
        2. Check idempotency
        3. Execute (or dry-run)
        4. Record result

        Args:
            intent: Strategy intent to execute

        Returns:
            ExecutionResult with outcome
        """
        now = datetime.now(timezone.utc)
        intent_hash = self._generate_intent_hash(intent)

        # Step 1: Validate
        try:
            self._validate_intent(intent)
        except ExecutionError as e:
            logger.warning(f"Intent validation failed: {e}")
            return ExecutionResult(
                success=False,
                order_id=None,
                fill_price=None,
                fill_size=None,
                error=str(e),
                timestamp=now,
                dry_run=self._config.dry_run,
                intent_hash=intent_hash,
            )

        # Step 2: Idempotency check
        if not self._check_idempotency(intent_hash):
            logger.warning(f"Duplicate intent detected: {intent_hash}")
            return ExecutionResult(
                success=False,
                order_id=None,
                fill_price=None,
                fill_size=None,
                error="Duplicate intent (idempotency violation)",
                timestamp=now,
                dry_run=self._config.dry_run,
                intent_hash=intent_hash,
            )

        # Step 3: Execute
        if self._config.dry_run:
            result = await self._execute_dry_run(intent, intent_hash)
        else:
            result = await self._execute_live(intent, intent_hash)

        # Step 4: Record if successful
        if result.success:
            self._record_execution(intent_hash)

        return result

    async def _execute_dry_run(
        self,
        intent: StrategyIntent,
        intent_hash: str,
    ) -> ExecutionResult:
        """Execute in dry-run mode (no actual orders)."""
        dry_run_id = f"dry-{uuid.uuid4().hex[:8]}"

        logger.info(
            f"DRY-RUN: {intent.side.upper()} {intent.size} {intent.outcome} "
            f"@ {intent.price} | {intent.strategy_name} | {intent.reason[:50]}"
        )

        return ExecutionResult(
            success=True,
            order_id=dry_run_id,
            fill_price=intent.price,
            fill_size=intent.size,
            error=None,
            timestamp=datetime.now(timezone.utc),
            dry_run=True,
            intent_hash=intent_hash,
        )

    async def _execute_live(
        self,
        intent: StrategyIntent,
        intent_hash: str,
    ) -> ExecutionResult:
        """Execute a live order."""
        if self._client is None:
            return ExecutionResult(
                success=False,
                order_id=None,
                fill_price=None,
                fill_size=None,
                error="No Polymarket client configured",
                dry_run=False,
                intent_hash=intent_hash,
            )

        last_error = None

        for attempt in range(self._config.max_retries + 1):
            try:
                logger.info(
                    f"LIVE: {intent.side.upper()} {intent.size} {intent.outcome} "
                    f"@ {intent.price} (attempt {attempt + 1})"
                )

                # Execute via Polymarket client
                # This would call the actual Polymarket API
                result = await self._submit_order(intent)

                if result.get("success"):
                    order_id = result.get("order_id") or result.get("orderID")
                    return ExecutionResult(
                        success=True,
                        order_id=order_id,
                        fill_price=intent.price,
                        fill_size=intent.size,
                        error=None,
                        dry_run=False,
                        intent_hash=intent_hash,
                    )
                else:
                    last_error = result.get("error", "Unknown error")

            except Exception as e:
                last_error = str(e)
                logger.error(f"Order attempt {attempt + 1} failed: {e}")

            # Wait before retry
            if attempt < self._config.max_retries:
                delay = self._config.retry_delay_ms / 1000 * (attempt + 1)
                await self._sleep(delay)

        return ExecutionResult(
            success=False,
            order_id=None,
            fill_price=None,
            fill_size=None,
            error=f"Failed after {self._config.max_retries + 1} attempts: {last_error}",
            dry_run=False,
            intent_hash=intent_hash,
        )

    async def _submit_order(self, intent: StrategyIntent) -> Dict[str, Any]:
        """
        Submit order to Polymarket.

        This is the actual API call.
        """
        try:
            # Build order args
            order_args = {
                "token_id": intent.token_id,
                "price": float(intent.price),
                "size": float(intent.size),
                "side": intent.side.upper(),
            }

            # Call Polymarket client
            if hasattr(self._client, 'create_and_post_order'):
                response = self._client.create_and_post_order(order_args)
            elif hasattr(self._client, 'execute_order'):
                response = self._client.execute_order(
                    token_id=intent.token_id,
                    amount=float(intent.size),
                    price=float(intent.price),
                    side=intent.side.upper(),
                )
            else:
                # Fallback to raw client
                raw = self._client.raw_client if hasattr(self._client, 'raw_client') else self._client
                from py_clob_client.clob_types import OrderArgs, OrderType
                args = OrderArgs(
                    token_id=intent.token_id,
                    price=float(intent.price),
                    size=float(intent.size),
                    side=intent.side.upper(),
                )
                signed = raw.create_order(args)
                response = raw.post_order(signed, OrderType.GTC)

            order_id = response.get("orderID") or response.get("order_id") or response.get("id")
            return {"success": True, "order_id": order_id}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _sleep(self, seconds: float) -> None:
        """Async sleep helper."""
        import asyncio
        await asyncio.sleep(seconds)

    async def execute_pair(
        self,
        yes_intent: StrategyIntent,
        no_intent: StrategyIntent,
    ) -> tuple[ExecutionResult, ExecutionResult]:
        """
        Execute a pair of intents (for arbitrage).

        Both must succeed or we should handle partial fills.
        """
        # Execute both
        yes_result = await self.execute(yes_intent)
        no_result = await self.execute(no_intent)

        # Log outcome
        if yes_result.success and no_result.success:
            logger.info(
                f"ARBITRAGE COMPLETE: YES={yes_result.order_id}, NO={no_result.order_id}"
            )
        elif yes_result.success != no_result.success:
            logger.error(
                f"ARBITRAGE PARTIAL: YES={yes_result.success}, NO={no_result.success}"
            )
            # In production, we'd need to handle this (maybe reverse the successful leg)

        return (yes_result, no_result)

    def get_status(self) -> Dict[str, Any]:
        """Get executor status."""
        return {
            "dry_run": self._config.dry_run,
            "max_retries": self._config.max_retries,
            "tracked_hashes": len(self._executed_hashes),
            "idempotency_window_hours": self._config.idempotency_window_hours,
        }
