"""
Risk Kernel - Purely deterministic trade approval logic.

NO I/O, NO network calls, NO side effects.
This is the supreme authority on trade approval.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class RiskDecisionType(Enum):
    """Risk decision outcomes."""

    APPROVED = "approved"
    REJECTED_DAILY_STOP = "rejected_daily_stop"
    REJECTED_HARD_KILL = "rejected_hard_kill"
    REJECTED_PER_TRADE_CAP = "rejected_per_trade_cap"
    REJECTED_POSITION_LIMIT = "rejected_position_limit"
    REJECTED_ANOMALOUS_LOSS = "rejected_anomalous_loss"
    KILLED = "killed"  # Bot is dead, no trades allowed


@dataclass
class Position:
    """Current position state."""

    market_id: str
    side: str  # "buy" or "sell"
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal


@dataclass
class CapitalState:
    """Current capital and PnL state."""

    starting_capital: Decimal
    current_capital: Decimal
    daily_pnl: Decimal
    total_pnl: Decimal
    total_pnl_pct: Decimal
    daily_pnl_pct: Decimal


@dataclass
class RiskDecision:
    """Risk kernel decision result."""

    decision: RiskDecisionType
    approved: bool
    reason: str
    adjusted_size: Optional[Decimal] = None


class RiskKernel:
    """
    Purely deterministic risk limit enforcement.

    Fail-closed: Missing data = rejection.
    No I/O, no side effects, pure function of inputs.
    """

    def __init__(
        self,
        starting_capital: Decimal,
        daily_stop_pct: Decimal = Decimal("-5.0"),
        hard_kill_pct: Decimal = Decimal("-20.0"),
        per_trade_cap_pct: Decimal = Decimal("3.0"),
        max_positions: int = 3,
        anomalous_loss_pct: Decimal = Decimal("-5.0"),
    ):
        """
        Initialize risk kernel with hard limits.

        Args:
            starting_capital: Initial capital ($1000 for v1)
            daily_stop_pct: Daily loss stop (-5%)
            hard_kill_pct: Total loss kill switch (-20%)
            per_trade_cap_pct: Max size per trade (3%)
            max_positions: Max concurrent positions (3)
            anomalous_loss_pct: Single trade loss that triggers kill (-5%)
        """
        self.starting_capital = starting_capital
        self.daily_stop_pct = daily_stop_pct
        self.hard_kill_pct = hard_kill_pct
        self.per_trade_cap_pct = per_trade_cap_pct
        self.max_positions = max_positions
        self.anomalous_loss_pct = anomalous_loss_pct
        self.is_killed = False

    def kill(self) -> None:
        """Manually kill the bot. No trades allowed after this."""
        self.is_killed = True

    def approve_trade(
        self,
        trade_size: Decimal,
        current_positions: List[Position],
        capital_state: CapitalState,
    ) -> RiskDecision:
        """
        Approve or reject trade based on risk limits.

        Checks performed (fail-fast, order matters):
        1. Bot killed check
        2. Hard kill check (total PnL <= -20%)
        3. Daily stop check (daily PnL <= -5%)
        4. Position limit check (>= 3 positions)
        5. Per-trade cap check (size > 3% capital)

        Args:
            trade_size: Requested trade size in dollars
            current_positions: List of current open positions
            capital_state: Current capital and PnL state

        Returns:
            RiskDecision with approval status and reason
        """
        # 1. Bot killed check
        if self.is_killed:
            return RiskDecision(
                decision=RiskDecisionType.KILLED,
                approved=False,
                reason="Bot has been killed. Manual reset required.",
            )

        # 2. Hard kill check
        if capital_state.total_pnl_pct <= self.hard_kill_pct:
            self.is_killed = True
            return RiskDecision(
                decision=RiskDecisionType.REJECTED_HARD_KILL,
                approved=False,
                reason=f"Hard kill triggered: total PnL {capital_state.total_pnl_pct:.2f}% <= {self.hard_kill_pct}%",
            )

        # 3. Daily stop check
        if capital_state.daily_pnl_pct <= self.daily_stop_pct:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED_DAILY_STOP,
                approved=False,
                reason=f"Daily stop triggered: daily PnL {capital_state.daily_pnl_pct:.2f}% <= {self.daily_stop_pct}%",
            )

        # 4. Position limit check
        if len(current_positions) >= self.max_positions:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED_POSITION_LIMIT,
                approved=False,
                reason=f"Position limit reached: {len(current_positions)} >= {self.max_positions}",
            )

        # 5. Per-trade cap check
        max_trade_size = capital_state.current_capital * (
            self.per_trade_cap_pct / Decimal("100")
        )
        if trade_size > max_trade_size:
            return RiskDecision(
                decision=RiskDecisionType.REJECTED_PER_TRADE_CAP,
                approved=False,
                reason=f"Trade size ${trade_size} exceeds per-trade cap ${max_trade_size:.2f} ({self.per_trade_cap_pct}%)",
                adjusted_size=max_trade_size,
            )

        # All checks passed
        return RiskDecision(
            decision=RiskDecisionType.APPROVED,
            approved=True,
            reason="All risk checks passed",
        )

    def check_post_trade_anomaly(
        self, trade_pnl_pct: Decimal
    ) -> Optional[RiskDecision]:
        """
        Check if a completed trade resulted in anomalous loss.

        Single trade loss >5% indicates likely bug. Kill immediately.

        Args:
            trade_pnl_pct: Realized PnL percentage for the trade

        Returns:
            RiskDecision if anomaly detected, None otherwise
        """
        if trade_pnl_pct <= self.anomalous_loss_pct:
            self.is_killed = True
            return RiskDecision(
                decision=RiskDecisionType.REJECTED_ANOMALOUS_LOSS,
                approved=False,
                reason=f"Anomalous loss detected: {trade_pnl_pct:.2f}% on single trade. Likely bug. Bot killed.",
            )
        return None
