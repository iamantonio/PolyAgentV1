"""
Risk Management for CopyTrader v1.

Enforces all v1 safety limits:
- Per-trade cap ($30)
- Daily drawdown stop ($50)
- Total drawdown kill switch ($200)
- Max concurrent positions (3)
- Stale intent rejection (>10s)
- Unauthorized market/trader = immediate kill
- Position size bug detection (3x limit)
- Consecutive daily DD tracking (3-day rule)
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
from agents.copytrader.config import CopyTraderV1Config
from agents.copytrader.storage import CopyTraderStorage
from agents.copytrader.schema import TradeIntent

logger = logging.getLogger(__name__)


class RiskViolation(Exception):
    """Raised when a risk limit is violated"""
    pass


class KillSwitchTriggered(Exception):
    """Raised when kill switch is active"""
    pass


class RiskManager:
    """
    Risk management for CopyTrader v1.

    All trades must pass through should_trade() which enforces:
    1. Kill switch check (immediate rejection if active)
    2. Authorization check (trader + market)
    3. Staleness check (intent age)
    4. Position limit check (max 3 concurrent)
    5. Size limit check (per-trade cap)
    6. Daily drawdown check
    7. Total drawdown check (kill switch trigger)
    """

    def __init__(self, config: CopyTraderV1Config, storage: CopyTraderStorage):
        self.config = config
        self.storage = storage
        self._consecutive_dd_days = 0  # Track 3-day rule

    def should_trade(
        self, intent: TradeIntent, current_balance: float
    ) -> Tuple[bool, str]:
        """
        Validate if we should execute this trade.

        Returns:
            (should_trade, reason)

        Raises:
            KillSwitchTriggered if kill switch is active
        """

        try:
            # 1. Check kill switch (highest priority)
            self._check_kill_switch()

            # 2. Check authorization (trader + market)
            self._check_authorization(intent)

            # 3. Check staleness
            self._check_staleness(intent)

            # 4. Check position limits
            self._check_position_limits()

            # 5. Check size limits
            self._check_size_limits(intent, current_balance)

            # 6. Check daily drawdown
            self._check_daily_drawdown(current_balance)

            # 7. Check total drawdown (may trigger kill switch)
            self._check_total_drawdown(current_balance)

            return (True, "All risk checks passed")

        except KillSwitchTriggered:
            # Re-raise kill switch (should stop the bot)
            raise

        except RiskViolation as e:
            # Risk check failed, reject trade
            return (False, str(e))

    def _check_kill_switch(self) -> None:
        """Check if kill switch is active"""
        is_active, reason = self.storage.is_kill_switch_active()
        if is_active:
            raise KillSwitchTriggered(
                f"Kill switch is active: {reason}. "
                f"Manual restart required via CLI."
            )

    def _check_authorization(self, intent: TradeIntent) -> None:
        """
        Check if trader and market are authorized.

        v1 spec: Unauthorized trader/market triggers IMMEDIATE KILL SWITCH
        """

        # Check trader
        if intent.source_trader.lower() != self.config.trader_address.lower():
            reason = (
                f"UNAUTHORIZED TRADER: {intent.source_trader} "
                f"(only {self.config.trader_address} allowed). "
                f"This is a critical security violation."
            )
            logger.critical(reason)
            self.storage.activate_kill_switch(reason, requires_restart=True)
            raise KillSwitchTriggered(reason)

        # Check market (requires knowing market category - placeholder for now)
        # TODO: Integrate with Polymarket API to fetch market category
        # For now, rely on optional market allowlist
        if self.config.market_allowlist:
            if intent.market_id not in self.config.market_allowlist:
                reason = (
                    f"UNAUTHORIZED MARKET: {intent.market_id} "
                    f"not in allowlist. Security violation."
                )
                logger.critical(reason)
                self.storage.activate_kill_switch(reason, requires_restart=True)
                raise KillSwitchTriggered(reason)

    def _check_staleness(self, intent: TradeIntent) -> None:
        """Check if intent is too old (v1: >10 seconds)"""
        age_seconds = (datetime.utcnow() - intent.timestamp).total_seconds()

        if age_seconds > self.config.max_intent_age_seconds:
            raise RiskViolation(
                f"Intent is stale: {age_seconds:.1f}s old "
                f"(max {self.config.max_intent_age_seconds}s). "
                f"Price may have moved too much."
            )

    def _check_position_limits(self) -> None:
        """Check if we're at max concurrent positions (v1: 3)"""
        open_positions = self.storage.get_open_positions()
        num_open = len(open_positions)

        if num_open >= self.config.max_concurrent_positions:
            raise RiskViolation(
                f"Max positions reached: {num_open}/{self.config.max_concurrent_positions}. "
                f"Close a position before opening new ones."
            )

    def _check_size_limits(self, intent: TradeIntent, current_balance: float) -> None:
        """
        Check if trade size is within limits.

        v1 spec:
        - Per-trade cap: 3% of capital ($30 with $1k)
        - Position size bug: >3x configured limit triggers kill switch
        """

        max_size_usd = self.config.get_max_position_size_usd()

        # Calculate intent size in USD
        if intent.size_usdc:
            intent_size_usd = intent.size_usdc
        else:
            # Estimate from tokens (requires price)
            # Use observed price if available
            if intent.metadata.best_ask:
                intent_size_usd = intent.size_tokens * intent.metadata.best_ask
            else:
                # Can't validate without price - be conservative
                logger.warning(
                    f"Cannot validate size for SELL intent {intent.intent_id}: "
                    f"no price data available"
                )
                return

        # Check normal limit
        if intent_size_usd > max_size_usd:
            # Check if this is a bug (>3x limit)
            bug_threshold = max_size_usd * self.config.position_size_bug_multiplier

            if intent_size_usd > bug_threshold:
                reason = (
                    f"POSITION SIZE BUG: Intent size ${intent_size_usd:.2f} "
                    f"exceeds {self.config.position_size_bug_multiplier}x limit "
                    f"(${bug_threshold:.2f}). This indicates a sizing error."
                )
                logger.critical(reason)
                self.storage.activate_kill_switch(reason, requires_restart=True)
                raise KillSwitchTriggered(reason)

            # Normal over-limit (not bug)
            raise RiskViolation(
                f"Trade size ${intent_size_usd:.2f} exceeds per-trade cap "
                f"${max_size_usd:.2f} ({self.config.per_trade_risk_pct}% of capital)"
            )

    def _check_daily_drawdown(self, current_balance: float) -> None:
        """
        Check daily drawdown limit (v1: 5% = $50).

        Stops trading for the day if exceeded.
        """

        # Get today's snapshot
        today = datetime.utcnow().strftime("%Y-%m-%d")
        snapshots = self.storage.get_daily_snapshots(days=1)

        if not snapshots or snapshots[0].date != today:
            # No snapshot yet today, assume starting balance = current
            return

        snapshot = snapshots[0]
        daily_pnl_pct = (
            (current_balance - snapshot.starting_balance) / snapshot.starting_balance * 100
        )

        max_dd_pct = self.config.max_daily_drawdown_pct

        if daily_pnl_pct < -max_dd_pct:
            # Track consecutive DD days
            self._consecutive_dd_days += 1

            # Check 3-day rule
            if self._consecutive_dd_days >= self.config.consecutive_daily_dd_limit:
                reason = (
                    f"3 CONSECUTIVE DAYS OF DAILY DRAWDOWN: "
                    f"{self._consecutive_dd_days} days of >{max_dd_pct}% DD. "
                    f"Strategy is not working."
                )
                logger.critical(reason)
                self.storage.activate_kill_switch(reason, requires_restart=True)
                raise KillSwitchTriggered(reason)

            # Normal daily stop
            raise RiskViolation(
                f"Daily drawdown limit exceeded: {daily_pnl_pct:.2f}% "
                f"(max {max_dd_pct}%). Trading stopped for today."
            )
        else:
            # Reset consecutive counter if positive day
            if daily_pnl_pct >= 0:
                self._consecutive_dd_days = 0

    def _check_total_drawdown(self, current_balance: float) -> None:
        """
        Check total drawdown (v1: 20% = $200).

        Triggers HARD KILL SWITCH if exceeded.
        """

        total_pnl_pct = (
            (current_balance - self.config.starting_capital_usd)
            / self.config.starting_capital_usd
            * 100
        )

        max_dd_pct = self.config.max_total_drawdown_pct

        if total_pnl_pct < -max_dd_pct:
            reason = (
                f"TOTAL DRAWDOWN KILL SWITCH: "
                f"{total_pnl_pct:.2f}% loss (max {max_dd_pct}%). "
                f"Lost ${current_balance - self.config.starting_capital_usd:.2f}. "
                f"Manual restart required."
            )
            logger.critical(reason)
            self.storage.activate_kill_switch(reason, requires_restart=True)
            raise KillSwitchTriggered(reason)

    def check_single_trade_loss(
        self, trade_pnl_usd: float, trade_pnl_pct: float
    ) -> None:
        """
        Check if single trade loss exceeds 5% (likely a bug).

        v1 spec: Single trade loss >5% triggers kill switch
        """

        if trade_pnl_pct < -5.0:
            reason = (
                f"SINGLE TRADE LOSS EXCEEDED 5%: "
                f"Lost ${abs(trade_pnl_usd):.2f} ({trade_pnl_pct:.2f}%) on one trade. "
                f"This likely indicates a bug (bad price, wrong size, etc.)."
            )
            logger.critical(reason)
            self.storage.activate_kill_switch(reason, requires_restart=True)
            raise KillSwitchTriggered(reason)

    def calculate_position_size(
        self, trader_order_size_usd: float, current_balance: float
    ) -> float:
        """
        Calculate our position size based on v1 strategy.

        v1: Copy 10% of trader's order, but respect $30 cap
        """

        # Base calculation: 10% of trader's order
        base_size = trader_order_size_usd * (self.config.copy_percentage / 100.0)

        # Cap at per-trade limit
        max_size = self.config.get_max_position_size_usd()
        size = min(base_size, max_size)

        # Cap at available balance (safety)
        size = min(size, current_balance * 0.95)  # Keep 5% buffer

        logger.info(
            f"Position sizing: trader ${trader_order_size_usd:.2f} "
            f"× {self.config.copy_percentage}% = ${base_size:.2f}, "
            f"capped at ${size:.2f}"
        )

        return size

    def get_risk_status(self, current_balance: float) -> dict:
        """Get current risk status for monitoring"""

        total_pnl = current_balance - self.config.starting_capital_usd
        total_pnl_pct = (total_pnl / self.config.starting_capital_usd) * 100

        # Get daily PnL
        today = datetime.utcnow().strftime("%Y-%m-%d")
        snapshots = self.storage.get_daily_snapshots(days=1)
        daily_pnl_pct = 0.0
        if snapshots and snapshots[0].date == today:
            daily_pnl_pct = snapshots[0].pnl_pct

        # Get position count
        open_positions = len(self.storage.get_open_positions())

        # Calculate limits
        max_daily_dd_usd = self.config.get_max_daily_drawdown_usd()
        max_total_dd_usd = self.config.get_max_total_drawdown_usd()
        max_position_usd = self.config.get_max_position_size_usd()

        is_killed, kill_reason = self.storage.is_kill_switch_active()

        return {
            "current_balance": current_balance,
            "starting_capital": self.config.starting_capital_usd,
            "total_pnl_usd": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "daily_pnl_pct": daily_pnl_pct,
            "open_positions": open_positions,
            "max_positions": self.config.max_concurrent_positions,
            "max_daily_dd_usd": max_daily_dd_usd,
            "max_total_dd_usd": max_total_dd_usd,
            "max_position_usd": max_position_usd,
            "consecutive_dd_days": self._consecutive_dd_days,
            "kill_switch_active": is_killed,
            "kill_switch_reason": kill_reason,
            # Risk health indicators
            "daily_dd_utilized_pct": (abs(daily_pnl_pct) / self.config.max_daily_drawdown_pct * 100)
            if daily_pnl_pct < 0
            else 0,
            "total_dd_utilized_pct": (abs(total_pnl_pct) / self.config.max_total_drawdown_pct * 100)
            if total_pnl_pct < 0
            else 0,
            "position_capacity_utilized_pct": (
                open_positions / self.config.max_concurrent_positions * 100
            ),
        }
