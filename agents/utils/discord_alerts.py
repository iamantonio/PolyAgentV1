"""
Discord Alerts for Trading Bot

Sends notifications to Discord webhook for:
- Trade executions
- Market resolutions
- Learning updates
- Edge detection discoveries
- Performance summaries
"""

import os
import requests
from typing import Dict, Optional
from datetime import datetime


class DiscordAlerter:
    """Send trading alerts to Discord"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

        if not self.webhook_url:
            print("⚠️  No Discord webhook URL configured")

    def send_alert(self, title: str, description: str, color: int = 0x00ff00, fields: Optional[list] = None):
        """
        Send Discord embed alert

        Args:
            title: Alert title
            description: Alert description
            color: Embed color (0x00ff00 = green, 0xff0000 = red, 0xffff00 = yellow)
            fields: List of {"name": str, "value": str, "inline": bool}
        """
        if not self.webhook_url:
            return

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": fields or []
        }

        payload = {"embeds": [embed]}

        try:
            response = requests.post(self.webhook_url, json=payload)
            if response.status_code not in [200, 204]:
                print(f"Discord alert failed: {response.status_code}")
        except Exception as e:
            print(f"Discord alert error: {e}")

    def alert_trade_executed(self, market: str, outcome: str, size: float, price: float, dry_run: bool = True):
        """Alert when trade is executed"""
        mode = "🧪 DRY RUN" if dry_run else "💰 LIVE"
        color = 0xffff00 if dry_run else 0x00ff00

        self.send_alert(
            title=f"{mode} Trade Executed",
            description=f"**Market**: {market[:100]}",
            color=color,
            fields=[
                {"name": "Outcome", "value": outcome, "inline": True},
                {"name": "Size", "value": f"${size:.2f}", "inline": True},
                {"name": "Price", "value": f"${price:.4f}", "inline": True}
            ]
        )

    def alert_market_resolved(self, market: str, predicted: str, actual: str, pnl: float):
        """Alert when market resolves"""
        was_correct = (predicted == actual)
        color = 0x00ff00 if was_correct else 0xff0000
        result = "✅ WIN" if was_correct else "❌ LOSS"

        self.send_alert(
            title=f"{result} Market Resolved",
            description=f"**Market**: {market[:100]}",
            color=color,
            fields=[
                {"name": "Predicted", "value": predicted, "inline": True},
                {"name": "Actual", "value": actual, "inline": True},
                {"name": "P&L", "value": f"${pnl:+.2f}", "inline": True}
            ]
        )

    def alert_edge_detected(self, market_type: str, has_edge: bool, win_rate: float, avg_pnl: float):
        """Alert when edge detection discovers good/bad market type"""
        color = 0x00ff00 if has_edge else 0xff0000
        status = "✅ EDGE FOUND" if has_edge else "❌ NO EDGE"

        self.send_alert(
            title=f"{status}: {market_type.upper()}",
            description=f"Learning system detected {'profitable' if has_edge else 'unprofitable'} market type",
            color=color,
            fields=[
                {"name": "Win Rate", "value": f"{win_rate:.1%}", "inline": True},
                {"name": "Avg P&L", "value": f"${avg_pnl:+.2f}", "inline": True},
                {"name": "Action", "value": "Trade" if has_edge else "Skip", "inline": True}
            ]
        )

    def alert_skipped_market(self, market: str, reason: str):
        """Alert when market is skipped"""
        self.send_alert(
            title="⏭️  Market Skipped",
            description=f"**Market**: {market[:100]}",
            color=0xffaa00,
            fields=[
                {"name": "Reason", "value": reason, "inline": False}
            ]
        )

    def alert_learning_update(self, total_trades: int, win_rate: float, total_pnl: float, brier_score: Optional[float] = None):
        """Alert with learning progress summary"""
        color = 0x00ff00 if win_rate > 0.55 else 0xffaa00 if win_rate > 0.45 else 0xff0000

        fields = [
            {"name": "Total Trades", "value": str(total_trades), "inline": True},
            {"name": "Win Rate", "value": f"{win_rate:.1%}", "inline": True},
            {"name": "Total P&L", "value": f"${total_pnl:+.2f}", "inline": True}
        ]

        if brier_score is not None:
            fields.append({"name": "Brier Score", "value": f"{brier_score:.4f}", "inline": True})

        self.send_alert(
            title="📊 Learning Progress Update",
            description="Bot performance summary",
            color=color,
            fields=fields
        )

    def alert_backwards_trade_prevented(self, market: str, prediction: str, attempted_buy: str):
        """Alert when multi-agent system prevents backwards trade"""
        self.send_alert(
            title="🛡️  BACKWARDS TRADE PREVENTED",
            description=f"Multi-agent verification caught a logic error",
            color=0xff0000,
            fields=[
                {"name": "Market", "value": market[:100], "inline": False},
                {"name": "Prediction", "value": f"{prediction} is more likely", "inline": True},
                {"name": "Attempted Buy", "value": attempted_buy, "inline": True},
                {"name": "Action", "value": "Trade blocked", "inline": True}
            ]
        )

    def alert_position_closed(self, market: str, reason: str, pnl: float, exit_price: float):
        """Alert when position is closed via stop-loss or take-profit"""
        color = 0x00ff00 if pnl > 0 else 0xff0000

        reason_emoji = {
            "stop_loss_50pct": "🛑",
            "stop_loss_25pct_time": "⏰",
            "take_profit_30pct": "✅",
            "take_profit_15pct_time": "⏰"
        }.get(reason, "🔄")

        reason_text = {
            "stop_loss_50pct": "Stop-Loss (Down >50%)",
            "stop_loss_25pct_time": "Stop-Loss (Down 25-50%, <6h close)",
            "take_profit_30pct": "Take-Profit (Up >30%)",
            "take_profit_15pct_time": "Take-Profit (Up >15%, <12h close)"
        }.get(reason, reason)

        self.send_alert(
            title=f"{reason_emoji} Position Closed",
            description=f"**Market**: {market[:100]}",
            color=color,
            fields=[
                {"name": "Exit Reason", "value": reason_text, "inline": False},
                {"name": "Exit Price", "value": f"${exit_price:.4f}", "inline": True},
                {"name": "Realized P&L", "value": f"${pnl:+.2f}", "inline": True}
            ]
        )
