"""
Intent validation firewall.

This module implements the security boundary between untrusted intent sources
and the execution engine. All intents must pass validation before execution.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Set
import logging

from agents.copytrader.schema import TradeIntent
from agents.copytrader.config import CopyTraderConfig

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when an intent fails validation"""

    pass


class IntentFirewall:
    """
    Validates trade intents against security policies.

    This is the critical security boundary. Any intent that fails validation
    is rejected and logged. Common rejection reasons:
    - Trader not in allowlist
    - Market not in allowlist
    - Intent too old (stale)
    - Intent too large (exceeds size cap)
    - Duplicate intent (already processed)
    """

    def __init__(self, config: CopyTraderConfig):
        self.config = config
        self._seen_intents: Dict[str, datetime] = {}  # intent_id -> timestamp
        self._cleanup_interval = timedelta(
            seconds=config.intent_dedup_window_seconds * 2
        )
        self._last_cleanup = datetime.utcnow()

    def validate(self, intent: TradeIntent) -> None:
        """
        Validate intent against all security policies.

        Raises ValidationError if intent fails any check.
        """
        # Clean up old entries periodically
        self._maybe_cleanup()

        # Check each validation rule in order
        self._validate_trader_allowlist(intent)
        self._validate_market_allowlist(intent)
        self._validate_staleness(intent)
        self._validate_size_limits(intent)
        self._validate_duplication(intent)

        # Log successful validation
        logger.info(
            f"Intent {intent.intent_id[:8]} passed validation: "
            f"{intent.side} {intent.size_usdc or intent.size_tokens} "
            f"from {intent.source_trader[:8]}..."
        )

    def _validate_trader_allowlist(self, intent: TradeIntent) -> None:
        """Ensure trader is in allowlist"""
        if not self.config.is_trader_allowed(intent.source_trader):
            raise ValidationError(
                f"Trader {intent.source_trader} not in allowlist. "
                f"Add to FOLLOW_TRADERS to enable."
            )

    def _validate_market_allowlist(self, intent: TradeIntent) -> None:
        """Ensure market is in allowlist (if allowlist is configured)"""
        if not self.config.is_market_allowed(intent.market_id):
            raise ValidationError(
                f"Market {intent.market_id} not in allowlist. "
                f"Add to MARKET_ALLOWLIST to enable."
            )

    def _validate_staleness(self, intent: TradeIntent) -> None:
        """Ensure intent is not too old"""
        if intent.is_stale(self.config.max_intent_age_seconds):
            age = intent.age_seconds()
            raise ValidationError(
                f"Intent is stale: {age:.1f}s old (max {self.config.max_intent_age_seconds}s). "
                f"Markets move too fast to execute safely."
            )

    def _validate_size_limits(self, intent: TradeIntent) -> None:
        """Ensure intent size is within safety limits"""
        # Check maximum size
        if intent.size_usdc and intent.size_usdc > self.config.max_intent_size_usdc:
            raise ValidationError(
                f"Intent size ${intent.size_usdc:.2f} exceeds maximum "
                f"${self.config.max_intent_size_usdc:.2f}. "
                f"Increase MAX_INTENT_SIZE_USDC if intentional."
            )

        if (
            intent.size_tokens
            and intent.size_tokens > self.config.max_intent_size_tokens
        ):
            raise ValidationError(
                f"Intent size {intent.size_tokens:.2f} tokens exceeds maximum "
                f"{self.config.max_intent_size_tokens:.2f}. "
                f"Increase MAX_INTENT_SIZE_TOKENS if intentional."
            )

        # Check minimum size (Polymarket requirement)
        if intent.size_usdc and intent.size_usdc < self.config.min_order_size_usdc:
            raise ValidationError(
                f"Intent size ${intent.size_usdc:.2f} below Polymarket minimum "
                f"${self.config.min_order_size_usdc:.2f}. "
                f"Consider trade aggregation for small orders."
            )

    def _validate_duplication(self, intent: TradeIntent) -> None:
        """Ensure intent hasn't been processed recently"""
        if intent.intent_id in self._seen_intents:
            prev_time = self._seen_intents[intent.intent_id]
            raise ValidationError(
                f"Duplicate intent {intent.intent_id[:8]} "
                f"(first seen {(datetime.utcnow() - prev_time).total_seconds():.1f}s ago). "
                f"This prevents double-execution."
            )

        # Mark as seen
        self._seen_intents[intent.intent_id] = datetime.utcnow()

    def _maybe_cleanup(self) -> None:
        """Clean up old entries from dedup cache"""
        now = datetime.utcnow()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - timedelta(seconds=self.config.intent_dedup_window_seconds)
        before_count = len(self._seen_intents)

        # Remove old entries
        self._seen_intents = {
            k: v for k, v in self._seen_intents.items() if v > cutoff
        }

        cleaned = before_count - len(self._seen_intents)
        if cleaned > 0:
            logger.debug(f"Cleaned {cleaned} old intent IDs from dedup cache")

        self._last_cleanup = now

    def get_stats(self) -> dict:
        """Get firewall statistics"""
        return {
            "seen_intents_count": len(self._seen_intents),
            "allowed_traders_count": len(self.config.allowed_traders),
            "allowed_markets_count": len(self.config.allowed_markets),
            "max_intent_size_usdc": self.config.max_intent_size_usdc,
            "max_intent_age_seconds": self.config.max_intent_age_seconds,
        }
