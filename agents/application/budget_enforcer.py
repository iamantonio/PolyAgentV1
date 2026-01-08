"""
Budget enforcement for LLM calls with persistent state.

Prevents runaway API costs by enforcing hard limits on:
- Daily spend
- Hourly spend
- Total calls per hour
- Calls per market per day

State persists across restarts to prevent reset gaming.
"""

import os
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, Tuple
from pathlib import Path


class BudgetEnforcer:
    """Hard budget enforcement for LLM calls with disk persistence."""

    STATE_FILE = "data/budget_state.json"

    def __init__(self):
        # Hard limits from env or defaults
        self.DAILY_BUDGET_USD = Decimal(os.getenv("DAILY_BUDGET_USD", "2.00"))
        self.HOURLY_BUDGET_USD = Decimal(os.getenv("HOURLY_BUDGET_USD", "0.25"))
        self.MAX_CALLS_PER_HOUR = int(os.getenv("MAX_CALLS_PER_HOUR", "20"))
        self.MAX_CALLS_PER_MARKET_PER_DAY = int(os.getenv("MAX_CALLS_PER_MARKET", "2"))

        # Load persistent state
        self.state = self._load_state()

        # Clean up stale entries on init
        self._cleanup_stale_entries()

    def _load_state(self) -> dict:
        """Load budget state from disk or create new."""
        Path(self.STATE_FILE).parent.mkdir(parents=True, exist_ok=True)

        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load budget state: {e}. Starting fresh.")

        return {
            "calls": [],  # List of {timestamp, cost, market_id}
            "total_spend": "0.00",
            "blocked": False,
            "block_reason": None
        }

    def _save_state(self):
        """Persist budget state to disk."""
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save budget state: {e}")

    def _cleanup_stale_entries(self):
        """Remove calls older than 24 hours (rolling window)."""
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - (24 * 3600)

        original_count = len(self.state["calls"])
        self.state["calls"] = [
            call for call in self.state["calls"]
            if call["timestamp"] > cutoff
        ]

        removed = original_count - len(self.state["calls"])
        if removed > 0:
            print(f"[BUDGET] Cleaned up {removed} calls older than 24h")
            # Recalculate total spend from remaining calls
            self.state["total_spend"] = str(sum(
                Decimal(call["cost"]) for call in self.state["calls"]
            ))
            self._save_state()

    def _get_calls_in_window(self, hours: float) -> list:
        """Get all calls within the last N hours (rolling window)."""
        now = datetime.now(timezone.utc)
        cutoff = now.timestamp() - (hours * 3600)

        return [
            call for call in self.state["calls"]
            if call["timestamp"] > cutoff
        ]

    def _get_calls_for_market_today(self, market_id: str) -> int:
        """Count calls for a specific market in the last 24 hours."""
        calls_24h = self._get_calls_in_window(24)
        return sum(1 for call in calls_24h if call.get("market_id") == market_id)

    def can_call_llm(self, market_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Check if LLM call is allowed using rolling windows.

        Returns:
            (allowed, reason_if_blocked)
        """
        self._cleanup_stale_entries()

        # Check global block
        if self.state.get("blocked", False):
            return False, self.state.get("block_reason")

        # Get calls in rolling windows
        calls_1h = self._get_calls_in_window(1)
        calls_24h = self._get_calls_in_window(24)

        # Calculate spend in rolling windows
        spend_1h = sum(Decimal(call["cost"]) for call in calls_1h)
        spend_24h = sum(Decimal(call["cost"]) for call in calls_24h)

        # Check daily budget (rolling 24h)
        if spend_24h >= self.DAILY_BUDGET_USD:
            self.state["blocked"] = True
            self.state["block_reason"] = f"Daily budget exceeded: ${spend_24h:.2f} (limit: ${self.DAILY_BUDGET_USD})"
            self._save_state()
            return False, self.state["block_reason"]

        # Check hourly budget (rolling 1h)
        if spend_1h >= self.HOURLY_BUDGET_USD:
            return False, f"Hourly budget exceeded: ${spend_1h:.2f} (limit: ${self.HOURLY_BUDGET_USD})"

        # Check hourly call limit (rolling 1h)
        if len(calls_1h) >= self.MAX_CALLS_PER_HOUR:
            return False, f"Hourly call limit reached: {len(calls_1h)}/{self.MAX_CALLS_PER_HOUR}"

        # Check per-market limit (rolling 24h)
        if market_id:
            market_calls = self._get_calls_for_market_today(market_id)
            if market_calls >= self.MAX_CALLS_PER_MARKET_PER_DAY:
                return False, f"Market call limit reached for {market_id[:8]}: {market_calls}/{self.MAX_CALLS_PER_MARKET_PER_DAY}"

        return True, None

    def record_call(self, cost_usd: Decimal, market_id: Optional[str] = None):
        """
        Record an LLM call and its cost.

        Args:
            cost_usd: Estimated cost in USD
            market_id: Optional market identifier
        """
        now = datetime.now(timezone.utc)

        call_record = {
            "timestamp": now.timestamp(),
            "cost": str(cost_usd),
            "market_id": market_id
        }

        self.state["calls"].append(call_record)
        self.state["total_spend"] = str(
            Decimal(self.state["total_spend"]) + cost_usd
        )

        self._save_state()

    def get_stats(self) -> dict:
        """Get current budget statistics."""
        self._cleanup_stale_entries()

        calls_1h = self._get_calls_in_window(1)
        calls_24h = self._get_calls_in_window(24)

        spend_1h = sum(Decimal(call["cost"]) for call in calls_1h)
        spend_24h = sum(Decimal(call["cost"]) for call in calls_24h)

        # Count unique markets called in last 24h
        markets_24h = set(call.get("market_id") for call in calls_24h if call.get("market_id"))

        return {
            "daily_spend": float(spend_24h),
            "daily_budget": float(self.DAILY_BUDGET_USD),
            "daily_remaining": float(self.DAILY_BUDGET_USD - spend_24h),
            "hourly_spend": float(spend_1h),
            "hourly_budget": float(self.HOURLY_BUDGET_USD),
            "hourly_remaining": float(self.HOURLY_BUDGET_USD - spend_1h),
            "calls_this_hour": len(calls_1h),
            "calls_today": len(calls_24h),
            "max_calls_per_hour": self.MAX_CALLS_PER_HOUR,
            "markets_called_today": len(markets_24h),
            "blocked": self.state.get("blocked", False),
            "block_reason": self.state.get("block_reason")
        }

    def reset_block(self):
        """Manually reset block state (for admin override)."""
        self.state["blocked"] = False
        self.state["block_reason"] = None
        self._save_state()
        print("[BUDGET] Block manually reset")
