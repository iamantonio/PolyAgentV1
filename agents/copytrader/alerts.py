"""
Alert system for CopyTrader notifications.

Sends Telegram alerts for critical events.
Alert delivery failure is logged but doesn't block operations.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    """Telegram alert configuration."""

    enabled: bool = True
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


class AlertService:
    """
    Sends Telegram notifications for critical events.

    Alert templates per Sally's spec (TBD).
    """

    def __init__(self, config: AlertConfig):
        """
        Initialize alert service.

        Args:
            config: Telegram configuration
        """
        self.config = config

        # TODO: Initialize Telegram bot when config is available
        if config.enabled and (not config.bot_token or not config.chat_id):
            logger.warning(
                "Telegram alerts enabled but credentials missing. Alerts will be logged only."
            )

    def notify_trade_executed(
        self,
        market_id: str,
        side: str,
        size: Decimal,
        price: Decimal,
        trader_id: str,
    ):
        """
        Alert: Trade successfully executed.

        Args:
            market_id: Market traded
            side: buy or sell
            size: Trade size in dollars
            price: Execution price
            trader_id: Source trader
        """
        message = f"""
✅ TRADE EXECUTED

Market: {market_id}
Side: {side.upper()}
Size: ${size:.2f}
Price: ${price:.4f}
Copied from: {trader_id}
        """.strip()

        self._send(message)

    def notify_trade_rejected(
        self, market_id: str, side: str, size: Decimal, reason: str, detail: str
    ):
        """
        Alert: Trade rejected by validation or risk kernel.

        Args:
            market_id: Market attempted
            side: buy or sell
            size: Requested size
            reason: Rejection reason code
            detail: Detailed explanation
        """
        message = f"""
⛔ TRADE REJECTED

Market: {market_id}
Side: {side.upper()}
Size: ${size:.2f}
Reason: {reason}
Detail: {detail}
        """.strip()

        self._send(message)

    def notify_daily_stop(self, daily_pnl: Decimal, daily_pnl_pct: Decimal):
        """
        Alert: Daily stop loss triggered (-5%).

        Args:
            daily_pnl: Daily PnL in dollars
            daily_pnl_pct: Daily PnL percentage
        """
        message = f"""
🛑 DAILY STOP TRIGGERED

Daily PnL: ${daily_pnl:.2f} ({daily_pnl_pct:.2f}%)
Trading halted for today.
Bot will resume tomorrow.

No action required unless you want to manually restart.
        """.strip()

        self._send(message, urgent=True)

    def notify_hard_kill(
        self, total_pnl: Decimal, total_pnl_pct: Decimal, trigger_reason: str
    ):
        """
        Alert: Hard kill switch triggered (-20% or anomaly).

        Args:
            total_pnl: Total PnL in dollars
            total_pnl_pct: Total PnL percentage
            trigger_reason: Why kill was triggered
        """
        message = f"""
🚨 HARD KILL ACTIVATED

Total PnL: ${total_pnl:.2f} ({total_pnl_pct:.2f}%)
Reason: {trigger_reason}

Bot is STOPPED and will NOT restart automatically.
MANUAL INTERVENTION REQUIRED.

Review logs and bot state before restarting.
        """.strip()

        self._send(message, urgent=True)

    def _send(self, message: str, urgent: bool = False):
        """
        Send alert message.

        Args:
            message: Alert message text
            urgent: Whether this is an urgent alert

        Note: Delivery failure is logged but doesn't raise.
        """
        prefix = "🚨 URGENT: " if urgent else ""
        full_message = prefix + message

        # Log locally
        log_level = logging.CRITICAL if urgent else logging.INFO
        logger.log(log_level, f"ALERT: {full_message}")

        # TODO: Send via Telegram when configured
        if not self.config.enabled:
            return

        if not self.config.bot_token or not self.config.chat_id:
            logger.warning("Telegram credentials missing. Alert logged only.")
            return

        try:
            # TODO: Implement actual Telegram sending
            # For now, just log
            logger.info(f"Would send Telegram alert: {full_message}")
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            # Don't raise - alert delivery failure doesn't block operations
