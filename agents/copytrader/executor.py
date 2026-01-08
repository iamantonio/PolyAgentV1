"""
CopyTrader executor - Main orchestration engine.

Coordinates the full trade flow:
  intent → validate → risk_check → execute → record → alert

Any step failure = abort, record reason, alert.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from agents.copytrader.allowlist import AllowlistService
from agents.copytrader.alerts import AlertService
from agents.copytrader.executor_adapter import ExecutorAdapter
from agents.copytrader.intent import (
    IntentValidator,
    IntentRejectionReason,
    TradeIntent,
)
from agents.copytrader.position_tracker import PositionTracker, TradeRecord
from agents.copytrader.risk_kernel import RiskKernel, RiskDecisionType
from agents.copytrader.storage import CopyTraderDB

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of intent processing."""

    success: bool
    intent: TradeIntent
    rejection_reason: Optional[str] = None
    rejection_detail: Optional[str] = None
    execution_detail: Optional[str] = None
    trade_id: Optional[int] = None


class CopyTrader:
    """
    Main CopyTrader orchestrator.

    Coordinates: validation → risk → execution → recording → alerts
    """

    def __init__(
        self,
        executor: ExecutorAdapter,
        risk_kernel: RiskKernel,
        allowlist: AllowlistService,
        tracker: PositionTracker,
        alerts: AlertService,
        intent_validator: Optional[IntentValidator] = None,
        dry_run: bool = False,
    ):
        """
        Initialize CopyTrader executor.

        Args:
            executor: Execution adapter (Mock or Live)
            risk_kernel: Risk limit enforcer
            allowlist: Market allowlist service
            tracker: Position and PnL tracker
            alerts: Alert notification service
            intent_validator: Intent validator (defaults to new instance)
            dry_run: If True, skip actual execution (testing mode)
        """
        self.executor = executor
        self.risk_kernel = risk_kernel
        self.allowlist = allowlist
        self.tracker = tracker
        self.alerts = alerts
        self.intent_validator = intent_validator or IntentValidator()
        self.dry_run = dry_run

        logger.info(
            f"CopyTrader initialized (executor={executor.get_name()}, dry_run={dry_run}, max_positions={intent_validator.max_positions if intent_validator else 3})"
        )

    def process_intent(self, intent: TradeIntent) -> ExecutionResult:
        """
        Process a trade intent through full pipeline.

        Flow:
        1. Validate intent (staleness, allowlist, position limit)
        2. Check risk kernel approval
        3. Execute trade (if not dry_run)
        4. Record result
        5. Send alert

        Any step failure = abort, record, alert.

        Args:
            intent: Trade intent to process

        Returns:
            ExecutionResult with outcome
        """
        logger.info(
            f"Processing intent: {intent.market_id} {intent.side} ${intent.size}"
        )

        # Step 1: Validate intent
        current_positions = self.tracker.get_current_positions()
        validation_result = self.intent_validator.validate(
            intent=intent,
            allowlist=self.allowlist.get_allowlist(),
            current_positions_count=len(current_positions),
        )

        if not validation_result.valid:
            logger.warning(
                f"Intent validation failed: {validation_result.rejection_reason}"
            )

            # Log rejection
            self.tracker.db.log_intent(
                trader_id=intent.trader_id,
                market_id=intent.market_id,
                side=intent.side,
                size=intent.size,
                intent_timestamp=intent.timestamp,
                validation_status="rejected",
                rejection_reason=validation_result.rejection_reason.value
                if validation_result.rejection_reason
                else None,
                rejection_detail=validation_result.rejection_detail,
            )

            # Alert rejection
            self.alerts.notify_trade_rejected(
                market_id=intent.market_id,
                side=intent.side,
                size=intent.size,
                reason=validation_result.rejection_reason.value
                if validation_result.rejection_reason
                else "unknown",
                detail=validation_result.rejection_detail or "",
            )

            return ExecutionResult(
                success=False,
                intent=intent,
                rejection_reason=validation_result.rejection_reason.value
                if validation_result.rejection_reason
                else None,
                rejection_detail=validation_result.rejection_detail,
            )

        # Step 2: Risk kernel approval
        capital_state = self.tracker.calculate_pnl()
        risk_decision = self.risk_kernel.approve_trade(
            trade_size=intent.size,
            current_positions=current_positions,
            capital_state=capital_state,
        )

        if not risk_decision.approved:
            logger.warning(f"Risk kernel rejected: {risk_decision.reason}")

            # Log rejection
            self.tracker.db.log_intent(
                trader_id=intent.trader_id,
                market_id=intent.market_id,
                side=intent.side,
                size=intent.size,
                intent_timestamp=intent.timestamp,
                validation_status="rejected",
                risk_decision=risk_decision.decision.value,
                risk_decision_detail=risk_decision.reason,
            )

            # Alert rejection
            self.alerts.notify_trade_rejected(
                market_id=intent.market_id,
                side=intent.side,
                size=intent.size,
                reason=risk_decision.decision.value,
                detail=risk_decision.reason,
            )

            # Check for kill triggers
            if risk_decision.decision in [
                RiskDecisionType.REJECTED_HARD_KILL,
                RiskDecisionType.REJECTED_ANOMALOUS_LOSS,
                RiskDecisionType.KILLED,
            ]:
                self.alerts.notify_hard_kill(
                    total_pnl=capital_state.total_pnl,
                    total_pnl_pct=capital_state.total_pnl_pct,
                    trigger_reason=risk_decision.reason,
                )

                # Log kill event
                self.tracker.db.log_risk_event(
                    event_type="hard_kill",
                    daily_pnl=capital_state.daily_pnl,
                    daily_pnl_pct=capital_state.daily_pnl_pct,
                    total_pnl=capital_state.total_pnl,
                    total_pnl_pct=capital_state.total_pnl_pct,
                    detail=risk_decision.reason,
                )

            elif risk_decision.decision == RiskDecisionType.REJECTED_DAILY_STOP:
                self.alerts.notify_daily_stop(
                    daily_pnl=capital_state.daily_pnl,
                    daily_pnl_pct=capital_state.daily_pnl_pct,
                )

                # Log daily stop event
                self.tracker.db.log_risk_event(
                    event_type="daily_stop",
                    daily_pnl=capital_state.daily_pnl,
                    daily_pnl_pct=capital_state.daily_pnl_pct,
                    total_pnl=capital_state.total_pnl,
                    total_pnl_pct=capital_state.total_pnl_pct,
                    detail=risk_decision.reason,
                )

            return ExecutionResult(
                success=False,
                intent=intent,
                rejection_reason=risk_decision.decision.value,
                rejection_detail=risk_decision.reason,
            )

        # Step 3: Execute trade
        execution_status = "success"
        execution_detail = None
        actual_price = Decimal("0")

        if self.dry_run:
            logger.info(
                f"DRY RUN: Would execute {intent.side} ${intent.size} of {intent.market_id}"
            )
            execution_detail = "dry_run_mode"
            actual_price = Decimal("0.50")  # Mock price for dry run
        else:
            try:
                # Execute via adapter (Mock or Live based on feature flag)
                logger.info(
                    f"EXECUTING via {self.executor.get_name()}: {intent.side} ${intent.size} of {intent.market_id}"
                )

                exec_result = self.executor.execute_market_order(
                    market_id=intent.market_id,
                    side=intent.side,
                    size=intent.size,
                )

                if exec_result.success:
                    actual_price = exec_result.price
                    execution_detail = f"executed_via_{self.executor.get_name()}"
                    logger.info(
                        f"Execution succeeded: price={actual_price}, exec_id={exec_result.execution_id}"
                    )
                else:
                    execution_status = "failed"
                    execution_detail = f"execution_failed: {exec_result.error}"
                    logger.error(f"Execution failed: {exec_result.error}")

            except Exception as e:
                logger.error(f"Execution exception: {e}")
                execution_status = "failed"
                execution_detail = str(e)

        # Step 4: Record trade
        trade_record = TradeRecord(
            market_id=intent.market_id,
            side=intent.side,
            size=intent.size,
            price=actual_price,
            timestamp=intent.timestamp,
            trader_id=intent.trader_id,
        )

        trade_id = self.tracker.record_trade(
            trade=trade_record,
            execution_status=execution_status,
            execution_detail=execution_detail,
        )

        # Log accepted intent
        self.tracker.db.log_intent(
            trader_id=intent.trader_id,
            market_id=intent.market_id,
            side=intent.side,
            size=intent.size,
            intent_timestamp=intent.timestamp,
            validation_status="accepted",
            risk_decision=risk_decision.decision.value,
            risk_decision_detail=risk_decision.reason,
        )

        # Step 5: Alert
        if execution_status == "success":
            self.alerts.notify_trade_executed(
                market_id=intent.market_id,
                side=intent.side,
                size=intent.size,
                price=actual_price,
                trader_id=intent.trader_id,
            )

            logger.info(f"Trade executed successfully. Trade ID: {trade_id}")

            return ExecutionResult(
                success=True,
                intent=intent,
                execution_detail=execution_detail,
                trade_id=trade_id,
            )
        else:
            self.alerts.notify_trade_rejected(
                market_id=intent.market_id,
                side=intent.side,
                size=intent.size,
                reason="execution_failed",
                detail=execution_detail or "unknown error",
            )

            logger.error(f"Trade execution failed. Trade ID: {trade_id}")

            return ExecutionResult(
                success=False,
                intent=intent,
                rejection_reason="execution_failed",
                rejection_detail=execution_detail,
                trade_id=trade_id,
            )

    def get_status(self) -> dict:
        """
        Get current bot status.

        Returns:
            Status dictionary with positions, PnL, risk state
        """
        positions = self.tracker.get_current_positions()
        capital_state = self.tracker.calculate_pnl()

        return {
            "dry_run": self.dry_run,
            "is_killed": self.risk_kernel.is_killed,
            "positions": len(positions),
            "capital": {
                "starting": float(capital_state.starting_capital),
                "current": float(capital_state.current_capital),
                "total_pnl": float(capital_state.total_pnl),
                "total_pnl_pct": float(capital_state.total_pnl_pct),
                "daily_pnl": float(capital_state.daily_pnl),
                "daily_pnl_pct": float(capital_state.daily_pnl_pct),
            },
            "allowlist_size": len(self.allowlist.get_allowlist()),
        }
