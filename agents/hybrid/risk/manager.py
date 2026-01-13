"""
Risk Manager for Hybrid Bot

Combines sophisticated risk controls from PolyAgentVPS with
edge-based filtering from Learning Autonomous Trader.

This is the GATEKEEPER - no trade executes without approval.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any
import logging
import time

from agents.hybrid.config import RiskLimits, HybridConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RiskCheckResult:
    """
    Result of a risk validation check.

    approved: Whether the trade is approved
    reason: Human-readable explanation
    adjusted_size: If approved but size was reduced
    blocked_by: Which limit caused the block (if blocked)
    """
    approved: bool
    reason: str
    adjusted_size: Optional[Decimal] = None
    blocked_by: Optional[str] = None

    def __repr__(self) -> str:
        if self.approved:
            if self.adjusted_size:
                return f"APPROVED (adjusted to {self.adjusted_size}): {self.reason}"
            return f"APPROVED: {self.reason}"
        return f"BLOCKED by {self.blocked_by}: {self.reason}"


class RiskManager:
    """
    Risk management system for the Hybrid Bot.

    Enforces:
    - Daily loss limits
    - Position count limits
    - Per-market exposure limits
    - Total exposure limits
    - Minimum balance requirements
    - Cooldown periods after losses
    - Edge-based market filtering
    """

    def __init__(
        self,
        limits: RiskLimits,
        get_daily_pnl: callable = None,
        get_open_positions: callable = None,
        get_position_value: callable = None,
    ):
        """
        Initialize risk manager.

        Args:
            limits: Risk limit configuration
            get_daily_pnl: Callback to get today's P&L
            get_open_positions: Callback to get open position count
            get_position_value: Callback to get position value by market
        """
        self._limits = limits
        self._get_daily_pnl = get_daily_pnl or (lambda: Decimal("0"))
        self._get_open_positions = get_open_positions or (lambda: [])
        self._get_position_value = get_position_value or (lambda m: Decimal("0"))

        # Internal state
        self._last_loss_time: Optional[float] = None
        self._daily_pnl_cache: Optional[Decimal] = None
        self._daily_pnl_cache_time: float = 0
        self._cache_ttl: float = 60.0  # Cache daily P&L for 60 seconds

        # Edge tracking (from Learning Autonomous Trader)
        self._edge_by_market_type: Dict[str, Decimal] = {}

        logger.info(f"RiskManager initialized with limits: {limits}")

    def update_edge_data(self, edge_by_type: Dict[str, Decimal]) -> None:
        """
        Update edge detection data from learning system.

        Args:
            edge_by_type: P&L by market type (crypto, sports, etc.)
        """
        self._edge_by_market_type = edge_by_type
        logger.info(f"Updated edge data: {edge_by_type}")

    def set_last_loss_time(self, timestamp: float) -> None:
        """Record when the last loss occurred (for cooldown)."""
        self._last_loss_time = timestamp
        logger.info(f"Loss recorded at {timestamp}, cooldown active for {self._limits.cooldown_after_loss}s")

    def invalidate_daily_loss_cache(self) -> None:
        """Invalidate daily P&L cache after a trade."""
        self._daily_pnl_cache = None
        self._daily_pnl_cache_time = 0

    def _get_cached_daily_pnl(self) -> Decimal:
        """Get daily P&L with caching."""
        now = time.time()
        if self._daily_pnl_cache is not None and (now - self._daily_pnl_cache_time) < self._cache_ttl:
            return self._daily_pnl_cache

        self._daily_pnl_cache = self._get_daily_pnl()
        self._daily_pnl_cache_time = now
        return self._daily_pnl_cache

    def can_trade(self, balance: Decimal) -> tuple[bool, str]:
        """
        Quick check if trading is allowed at all.

        Returns:
            (can_trade, reason) tuple
        """
        # Check minimum balance
        if balance < self._limits.min_balance:
            return False, f"Balance {balance} below minimum {self._limits.min_balance}"

        # Check daily loss limit
        daily_pnl = self._get_cached_daily_pnl()
        if daily_pnl <= -self._limits.max_daily_loss:
            return False, f"Daily loss limit reached: {daily_pnl}"

        # Check cooldown
        if self._last_loss_time is not None:
            elapsed = time.time() - self._last_loss_time
            if elapsed < self._limits.cooldown_after_loss:
                remaining = int(self._limits.cooldown_after_loss - elapsed)
                return False, f"In cooldown after loss, {remaining}s remaining"

        return True, "Trading allowed"

    def check_market_edge(self, market_type: str) -> tuple[bool, str]:
        """
        Check if we have edge in this market type.

        From Learning Autonomous Trader's edge detection.
        """
        if not self._edge_by_market_type:
            return True, "No edge data available, allowing trade"

        edge = self._edge_by_market_type.get(market_type, Decimal("0"))
        if edge < Decimal("0"):
            return False, f"Negative edge in {market_type}: ${edge:.2f}"

        return True, f"Positive edge in {market_type}: ${edge:.2f}"

    def validate_intent(
        self,
        market_id: str,
        market_type: str,
        side: str,
        price: Decimal,
        size: Decimal,
        balance: Decimal,
        confidence: Decimal = Decimal("1"),
    ) -> RiskCheckResult:
        """
        Validate a trading intent against all risk limits.

        This is the main entry point for risk checks.

        Args:
            market_id: Market identifier
            market_type: Market type (crypto, sports, etc.)
            side: "buy" or "sell"
            price: Order price
            size: Order size in $
            balance: Current available balance
            confidence: Strategy confidence (0-1)

        Returns:
            RiskCheckResult with approval/rejection details
        """
        # 1. Basic trading check
        can_trade, reason = self.can_trade(balance)
        if not can_trade:
            return RiskCheckResult(
                approved=False,
                reason=reason,
                blocked_by="trading_blocked"
            )

        # 2. Check market edge (from learning system)
        has_edge, edge_reason = self.check_market_edge(market_type)
        if not has_edge:
            return RiskCheckResult(
                approved=False,
                reason=edge_reason,
                blocked_by="negative_edge"
            )

        # 3. Check position count
        open_positions = self._get_open_positions()
        if len(open_positions) >= self._limits.max_positions:
            return RiskCheckResult(
                approved=False,
                reason=f"Max positions reached: {len(open_positions)}/{self._limits.max_positions}",
                blocked_by="max_positions"
            )

        # 4. Check per-market exposure
        current_market_value = self._get_position_value(market_id)
        if current_market_value + size > self._limits.max_position_per_market:
            max_additional = self._limits.max_position_per_market - current_market_value
            if max_additional <= Decimal("0"):
                return RiskCheckResult(
                    approved=False,
                    reason=f"Max exposure in market {market_id}: ${current_market_value}",
                    blocked_by="max_market_exposure"
                )
            # Adjust size down
            size = max_additional

        # 5. Check total exposure
        total_exposure = sum(
            Decimal(str(p.get("size", 0))) * Decimal(str(p.get("entry_price", 0)))
            for p in open_positions
        )
        if total_exposure + size > self._limits.max_total_exposure:
            max_additional = self._limits.max_total_exposure - total_exposure
            if max_additional <= Decimal("0"):
                return RiskCheckResult(
                    approved=False,
                    reason=f"Max total exposure reached: ${total_exposure}",
                    blocked_by="max_total_exposure"
                )
            # Adjust size down
            size = min(size, max_additional)

        # 6. Check single trade limit
        if size > self._limits.max_single_trade:
            size = self._limits.max_single_trade

        # 7. Check position size limit
        if size > self._limits.max_position_size:
            size = self._limits.max_position_size

        # 8. Check minimum viable size (avoid dust trades)
        MIN_TRADE_SIZE = Decimal("1")
        if size < MIN_TRADE_SIZE:
            return RiskCheckResult(
                approved=False,
                reason=f"Size {size} below minimum {MIN_TRADE_SIZE}",
                blocked_by="min_size"
            )

        # All checks passed
        return RiskCheckResult(
            approved=True,
            reason=f"Approved: {side} ${size} in {market_type}",
            adjusted_size=size if size != size else None  # Only set if adjusted
        )

    def validate_arbitrage(
        self,
        market_id: str,
        yes_price: Decimal,
        no_price: Decimal,
        size: Decimal,
        balance: Decimal,
    ) -> RiskCheckResult:
        """
        Validate an arbitrage opportunity.

        Arbitrage bypasses edge checking since it's risk-free.

        Args:
            market_id: Market identifier
            yes_price: YES side price
            no_price: NO side price
            size: Total size for both legs
            balance: Current available balance

        Returns:
            RiskCheckResult
        """
        # 1. Basic trading check
        can_trade, reason = self.can_trade(balance)
        if not can_trade:
            return RiskCheckResult(
                approved=False,
                reason=reason,
                blocked_by="trading_blocked"
            )

        # 2. Check we have enough balance for both legs
        total_cost = (yes_price + no_price) * size
        if total_cost > balance:
            max_size = balance / (yes_price + no_price)
            size = max_size

        # 3. Check total exposure
        open_positions = self._get_open_positions()
        total_exposure = sum(
            Decimal(str(p.get("size", 0))) * Decimal(str(p.get("entry_price", 0)))
            for p in open_positions
        )
        if total_exposure + total_cost > self._limits.max_total_exposure:
            return RiskCheckResult(
                approved=False,
                reason=f"Arbitrage would exceed exposure limit",
                blocked_by="max_total_exposure"
            )

        # 4. Check minimum size
        MIN_ARB_SIZE = Decimal("25")
        if size < MIN_ARB_SIZE:
            return RiskCheckResult(
                approved=False,
                reason=f"Arbitrage size {size} below minimum {MIN_ARB_SIZE}",
                blocked_by="min_arb_size"
            )

        return RiskCheckResult(
            approved=True,
            reason=f"Arbitrage approved: {size} @ YES={yes_price} NO={no_price}",
            adjusted_size=size
        )

    def get_status(self) -> Dict[str, Any]:
        """Get current risk manager status."""
        daily_pnl = self._get_cached_daily_pnl()
        open_positions = self._get_open_positions()
        total_exposure = sum(
            Decimal(str(p.get("size", 0))) * Decimal(str(p.get("entry_price", 0)))
            for p in open_positions
        )

        in_cooldown = False
        cooldown_remaining = 0
        if self._last_loss_time is not None:
            elapsed = time.time() - self._last_loss_time
            if elapsed < self._limits.cooldown_after_loss:
                in_cooldown = True
                cooldown_remaining = int(self._limits.cooldown_after_loss - elapsed)

        return {
            "daily_pnl": float(daily_pnl),
            "daily_loss_limit": float(self._limits.max_daily_loss),
            "daily_loss_remaining": float(self._limits.max_daily_loss + daily_pnl),
            "open_positions": len(open_positions),
            "max_positions": self._limits.max_positions,
            "total_exposure": float(total_exposure),
            "max_exposure": float(self._limits.max_total_exposure),
            "in_cooldown": in_cooldown,
            "cooldown_remaining": cooldown_remaining,
            "edge_data": {k: float(v) for k, v in self._edge_by_market_type.items()},
        }
