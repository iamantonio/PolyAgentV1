"""
TradeIntent schema definition.

This is the contract between the signal generator (TypeScript) and executor (Python).
All intents must conform to this schema or they will be rejected.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid


class Side(str, Enum):
    """Trade side: BUY or SELL"""

    BUY = "BUY"
    SELL = "SELL"


class Outcome(str, Enum):
    """Market outcome: YES or NO"""

    YES = "YES"
    NO = "NO"


class TradeIntentMetadata(BaseModel):
    """
    Metadata about the trade intent observation.

    This helps the executor make informed decisions about execution quality.
    """

    best_bid: Optional[float] = Field(
        None, description="Best bid price observed at signal time", ge=0, le=1
    )
    best_ask: Optional[float] = Field(
        None, description="Best ask price observed at signal time", ge=0, le=1
    )
    detection_latency_ms: Optional[int] = Field(
        None, description="Milliseconds between trader's tx and our detection", ge=0
    )
    trader_position_size: Optional[float] = Field(
        None, description="Trader's position size before this trade", ge=0
    )
    trader_balance_usd: Optional[float] = Field(
        None, description="Trader's estimated balance in USD", ge=0
    )
    trader_order_usd: Optional[float] = Field(
        None, description="Trader's order size in USD", ge=0
    )
    source_tx_hash: Optional[str] = Field(
        None, description="Transaction hash of the trader's order"
    )
    extra: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class TradeIntent(BaseModel):
    """
    Trade intent message from signal generator.

    This represents a validated trade signal that should be considered for execution.
    The Python executor will apply additional validation before executing.
    """

    # Identity and tracking
    intent_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this intent (UUID)",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When this intent was created"
    )

    # Source trader
    source_trader: str = Field(
        ...,
        description="Ethereum address of the trader being copied (0x...)",
        min_length=42,
        max_length=42,
    )

    # Market identification
    market_id: str = Field(
        ...,
        description="Polymarket market/token ID or condition ID",
        min_length=1,
    )
    outcome: Outcome = Field(..., description="YES or NO outcome")

    # Trade parameters
    side: Side = Field(..., description="BUY or SELL")
    price_limit: Optional[float] = Field(
        None,
        description="Maximum price for BUY, minimum price for SELL",
        ge=0,
        le=1,
    )

    # Position sizing (exactly one must be provided)
    size_usdc: Optional[float] = Field(
        None, description="Order size in USDC (for BUY orders)", gt=0
    )
    size_tokens: Optional[float] = Field(
        None, description="Order size in tokens (for SELL orders)", gt=0
    )

    # Observable context
    metadata: TradeIntentMetadata = Field(
        default_factory=TradeIntentMetadata, description="Observational metadata"
    )

    @field_validator("source_trader")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate Ethereum address format"""
        if not v.startswith("0x"):
            raise ValueError("source_trader must start with 0x")
        if not all(c in "0123456789abcdefABCDEF" for c in v[2:]):
            raise ValueError("source_trader must be valid hex")
        return v.lower()

    @model_validator(mode="after")
    def validate_size_fields(self) -> "TradeIntent":
        """Ensure exactly one size field is provided"""
        has_usdc = self.size_usdc is not None
        has_tokens = self.size_tokens is not None

        if has_usdc and has_tokens:
            raise ValueError("Cannot specify both size_usdc and size_tokens")
        if not has_usdc and not has_tokens:
            raise ValueError("Must specify either size_usdc or size_tokens")

        # For BUY orders, prefer size_usdc
        if self.side == Side.BUY and not has_usdc:
            raise ValueError("BUY orders should specify size_usdc")

        # For SELL orders, prefer size_tokens
        if self.side == Side.SELL and not has_tokens:
            raise ValueError("SELL orders should specify size_tokens")

        return self

    @model_validator(mode="after")
    def validate_price_limit(self) -> "TradeIntent":
        """Validate price limit makes sense for the side"""
        if self.price_limit is not None:
            if self.side == Side.BUY and self.price_limit > 0.99:
                raise ValueError("BUY price_limit should be < 0.99")
            if self.side == Side.SELL and self.price_limit < 0.01:
                raise ValueError("SELL price_limit should be > 0.01")
        return self

    def age_seconds(self) -> float:
        """Calculate age of this intent in seconds"""
        return (datetime.utcnow() - self.timestamp).total_seconds()

    def is_stale(self, max_age_seconds: int = 60) -> bool:
        """Check if this intent is too old to execute safely"""
        return self.age_seconds() > max_age_seconds

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "TradeIntent":
        """Parse from dictionary"""
        return cls.model_validate(data)
