"""
Mock Polymarket client for testing.

Provides deterministic responses without web3/network dependencies.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MockExecutionResult:
    """Mock execution result."""

    success: bool
    price: float
    size: float
    error: Optional[str] = None


class MockPolymarketClient:
    """
    Mock Polymarket client for E2E tests.

    Exposes same interface used by CopyTrader executor,
    returns deterministic responses.

    No web3 imports. No network calls.
    """

    def __init__(self, should_fail: bool = False):
        """
        Initialize mock client.

        Args:
            should_fail: If True, execution will fail
        """
        self.should_fail = should_fail
        self.executions = []  # Track all execution calls

    def execute_market_order(
        self, market_id: str, side: str, size: float
    ) -> MockExecutionResult:
        """
        Mock market order execution.

        Args:
            market_id: Market to trade
            side: 'buy' or 'sell'
            size: Trade size in dollars

        Returns:
            MockExecutionResult with deterministic data
        """
        # Record the execution call
        self.executions.append(
            {"market_id": market_id, "side": side, "size": size}
        )

        if self.should_fail:
            return MockExecutionResult(
                success=False, price=0.0, size=0.0, error="Mock execution failure"
            )

        # Return deterministic success
        return MockExecutionResult(
            success=True,
            price=0.50,  # Mock price
            size=size,
        )

    def get_execution_count(self) -> int:
        """Get number of executions called."""
        return len(self.executions)

    def get_last_execution(self) -> Optional[dict]:
        """Get last execution parameters."""
        return self.executions[-1] if self.executions else None

    def reset(self):
        """Reset execution history."""
        self.executions = []
