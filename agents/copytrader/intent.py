"""
Trade Intent schema and validation logic.

TradeIntent represents a copy signal from the followed trader.
Validation enforces: freshness, allowlist, position limits.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class IntentRejectionReason(Enum):
    """Reasons for intent rejection."""

    STALE = "stale"
    NOT_ON_ALLOWLIST = "not_on_allowlist"
    POSITION_LIMIT_REACHED = "position_limit_reached"
    ALLOWLIST_EMPTY = "allowlist_empty"
    INVALID_SIDE = "invalid_side"
    INVALID_SIZE = "invalid_size"


class TradeIntent(BaseModel):
    """
    Immutable trade intent from copied trader.

    Represents a signal to copy: "Trader X bought Y shares of market Z at time T"
    """

    trader_id: str = Field(..., description="ID of the trader being copied")
    market_id: str = Field(..., description="Polymarket market ID")
    side: str = Field(..., description="Trade side: 'buy' or 'sell'")
    size: Decimal = Field(..., description="Trade size in dollars", gt=0)
    timestamp: datetime = Field(..., description="When the intent was generated")

    @validator("side")
    def validate_side(cls, v):
        if v not in ["buy", "sell"]:
            raise ValueError(f"Invalid side: {v}. Must be 'buy' or 'sell'")
        return v

    class Config:
        frozen = True  # Immutable


@dataclass
class IntentValidationResult:
    """Result of intent validation."""

    valid: bool
    intent: Optional[TradeIntent]
    rejection_reason: Optional[IntentRejectionReason]
    rejection_detail: Optional[str]


class IntentValidator:
    """
    Validates trade intents against business rules.

    Fail-closed: Any validation failure = rejection.
    """

    def __init__(
        self,
        staleness_threshold_seconds: int = 10,
        max_positions: int = 3,
    ):
        """
        Initialize validator.

        Args:
            staleness_threshold_seconds: Max age of intent (10s default)
            max_positions: Max concurrent positions (3 default)
        """
        self.staleness_threshold = timedelta(seconds=staleness_threshold_seconds)
        self.max_positions = max_positions

    def validate(
        self,
        intent: TradeIntent,
        allowlist: List[str],
        current_positions_count: int,
    ) -> IntentValidationResult:
        """
        Validate intent against all rules.

        Checks performed (fail-fast):
        1. Staleness check (>10s = reject)
        2. Allowlist check (empty allowlist = fail-closed reject all)
        3. Market on allowlist check
        4. Position limit check

        Args:
            intent: Trade intent to validate
            allowlist: List of allowed market IDs
            current_positions_count: Number of currently open positions

        Returns:
            IntentValidationResult with validation outcome
        """
        # 1. Staleness check
        age = datetime.now() - intent.timestamp
        if age > self.staleness_threshold:
            return IntentValidationResult(
                valid=False,
                intent=intent,
                rejection_reason=IntentRejectionReason.STALE,
                rejection_detail=f"Intent age {age.total_seconds():.1f}s exceeds threshold {self.staleness_threshold.total_seconds()}s",
            )

        # 2. Empty allowlist = fail-closed
        if not allowlist:
            return IntentValidationResult(
                valid=False,
                intent=intent,
                rejection_reason=IntentRejectionReason.ALLOWLIST_EMPTY,
                rejection_detail="Allowlist is empty. Fail-closed: rejecting all intents.",
            )

        # 3. Market on allowlist check
        if intent.market_id not in allowlist:
            return IntentValidationResult(
                valid=False,
                intent=intent,
                rejection_reason=IntentRejectionReason.NOT_ON_ALLOWLIST,
                rejection_detail=f"Market {intent.market_id} not in politics allowlist",
            )

        # 4. Position limit check (only if this is a new position)
        # NOTE: This is a simplified check. Full check requires knowing if
        # this market is already in current positions.
        if current_positions_count >= self.max_positions:
            return IntentValidationResult(
                valid=False,
                intent=intent,
                rejection_reason=IntentRejectionReason.POSITION_LIMIT_REACHED,
                rejection_detail=f"Position limit reached: {current_positions_count} >= {self.max_positions}",
            )

        # All checks passed
        return IntentValidationResult(
            valid=True,
            intent=intent,
            rejection_reason=None,
            rejection_detail=None,
        )
