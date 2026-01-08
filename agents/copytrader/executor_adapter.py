"""
Execution Adapter — Phase 2 Isolation Boundary

Abstracts execution behind a stable interface with two implementations:
- MockExecutor: Deterministic mock for testing
- LiveExecutor: Real Polymarket CLOB execution

Feature-flag controlled (USE_REAL_EXECUTOR env var).
Real client loaded ONLY when flag is True (lazy import).
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """
    Standardized execution result from any executor.

    Ensures semantic equivalence between mock and live implementations.
    """

    success: bool
    price: Decimal
    size: Decimal
    market_id: str
    side: str
    error: Optional[str] = None
    execution_id: Optional[str] = None  # Transaction hash or mock ID
    timestamp: Optional[float] = None  # Execution timestamp


class ExecutorAdapter(ABC):
    """
    Abstract execution adapter.

    All executors (mock or live) must implement this interface
    to ensure parity and substitutability.
    """

    @abstractmethod
    def execute_market_order(
        self, market_id: str, side: str, size: Decimal
    ) -> ExecutionResult:
        """
        Execute a market order.

        Args:
            market_id: Polymarket market ID
            side: 'buy' or 'sell'
            size: Order size in dollars (Decimal for precision)

        Returns:
            ExecutionResult with outcome

        Raises:
            Exception if execution fails critically
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return executor name for logging."""
        pass


class MockExecutor(ExecutorAdapter):
    """
    Mock executor for testing.

    Wraps existing MockPolymarketClient with adapter interface.
    Deterministic behavior, no network calls.
    """

    def __init__(self, should_fail: bool = False):
        """
        Initialize mock executor.

        Args:
            should_fail: If True, all executions fail
        """
        from tests.mocks.mock_polymarket_client import MockPolymarketClient

        self.client = MockPolymarketClient(should_fail=should_fail)
        self.should_fail = should_fail
        logger.info(f"MockExecutor initialized (should_fail={should_fail})")

    def execute_market_order(
        self, market_id: str, side: str, size: Decimal
    ) -> ExecutionResult:
        """Execute mock market order."""
        # Convert Decimal to float for mock client
        size_float = float(size)

        # Call underlying mock
        mock_result = self.client.execute_market_order(
            market_id=market_id, side=side, size=size_float
        )

        # Convert to standardized ExecutionResult
        return ExecutionResult(
            success=mock_result.success,
            price=Decimal(str(mock_result.price)),
            size=Decimal(str(mock_result.size)),
            market_id=market_id,
            side=side,
            error=mock_result.error,
            execution_id=f"mock_{len(self.client.executions)}",
            timestamp=None,  # Mock doesn't track time
        )

    def get_name(self) -> str:
        return "MockExecutor"


class LiveExecutor(ExecutorAdapter):
    """
    Live executor for real Polymarket CLOB execution.

    Lazy-loads Polymarket client ONLY when instantiated.
    This should ONLY happen when USE_REAL_EXECUTOR=true.
    """

    def __init__(self):
        """
        Initialize live executor.

        Lazy-imports Polymarket client to avoid side effects.
        """
        # Lazy import - only loads when LiveExecutor is instantiated
        from agents.polymarket.polymarket import Polymarket

        self.client = Polymarket()
        logger.info("LiveExecutor initialized with real Polymarket client")

    def execute_market_order(
        self, market_id: str, side: str, size: Decimal
    ) -> ExecutionResult:
        """
        Execute real market order via Polymarket CLOB.

        NOTE: This is the ONLY place where real execution happens.

        Args:
            market_id: Token ID for the market outcome
            side: 'buy' or 'sell'
            size: Amount in USDC
        """
        from py_clob_client.clob_types import MarketOrderArgs, OrderType
        from datetime import datetime

        try:
            # Convert size to float
            size_float = float(size)

            logger.info(f"Executing live order: {side} {size} USDC on token {market_id}")

            # Create market order args
            # Convert side to uppercase for CLOB API
            clob_side = side.upper()  # BUY or SELL

            order_args = MarketOrderArgs(
                token_id=market_id,
                amount=size_float,
                side=clob_side,
            )

            # Create and sign the order
            signed_order = self.client.client.create_market_order(order_args)
            logger.info(f"Order signed: {signed_order}")

            # Post order to CLOB (Fill-or-Kill)
            response = self.client.client.post_order(signed_order, orderType=OrderType.FOK)
            logger.info(f"Order response: {response}")

            # Parse response
            # Response structure from CLOB varies, handle both success and failure
            if response and isinstance(response, dict):
                # Extract execution details
                order_id = response.get('orderID', 'unknown')
                status = response.get('status', 'unknown')

                # Check if order was successful (case-insensitive)
                success = status.upper() in ['MATCHED', 'FILLED', 'LIVE']

                # Try to extract price (may not be available immediately)
                # For market orders, use orderbook mid-price as approximation
                try:
                    book = self.client.client.get_order_book(market_id)
                    if book and hasattr(book, 'market'):
                        price = Decimal(str(book.market))
                    else:
                        price = Decimal("0.5")  # Default mid-price
                except:
                    price = Decimal("0.5")

                return ExecutionResult(
                    success=success,
                    price=price,
                    size=size,
                    market_id=market_id,
                    side=side,
                    error=None if success else f"Order status: {status}",
                    execution_id=order_id,
                    timestamp=datetime.now().timestamp(),
                )
            else:
                # Unexpected response format
                return ExecutionResult(
                    success=False,
                    price=Decimal("0"),
                    size=Decimal("0"),
                    market_id=market_id,
                    side=side,
                    error=f"Unexpected response: {response}",
                    execution_id=None,
                    timestamp=None,
                )

        except Exception as e:
            logger.error(f"Live execution failed: {e}")
            return ExecutionResult(
                success=False,
                price=Decimal("0"),
                size=Decimal("0"),
                market_id=market_id,
                side=side,
                error=str(e),
                execution_id=None,
                timestamp=None,
            )

    def get_name(self) -> str:
        return "LiveExecutor"


def create_executor(use_real: Optional[bool] = None) -> ExecutorAdapter:
    """
    Factory function to create appropriate executor based on feature flag.

    Args:
        use_real: Override for USE_REAL_EXECUTOR env var.
                 If None, reads from environment.
                 Default: False (mock)

    Returns:
        ExecutorAdapter (Mock or Live)

    Environment:
        USE_REAL_EXECUTOR: Set to 'true' to enable live execution
                          Default: false (mock)
    """
    if use_real is None:
        use_real = os.getenv("USE_REAL_EXECUTOR", "false").lower() == "true"

    if use_real:
        logger.warning("🔴 LIVE EXECUTOR ENABLED - Real trades will execute!")
        return LiveExecutor()
    else:
        logger.info("✓ Mock executor enabled (safe mode)")
        return MockExecutor(should_fail=False)


# Execution adapter interface version
__version__ = "1.0.0"
