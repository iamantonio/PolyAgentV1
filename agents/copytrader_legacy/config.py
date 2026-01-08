"""
CopyTrader v1 Configuration - Politics-only, Single Trader

This config enforces the v1 spec:
- $1,000 starting capital
- 5% daily drawdown limit ($50)
- 20% total drawdown kill switch ($200)
- 3% per-trade risk cap ($30)
- Politics markets only
- Copy 1 trader at 10% position sizing
"""

from typing import Set, Optional
from pydantic import BaseModel, Field
import os


class CopyTraderV1Config(BaseModel):
    """
    v1 Configuration - hardcoded conservative defaults matching spec.

    SOURCE OF TRUTH:
    - Starting capital: $1,000
    - Max daily drawdown: 5% ($50)
    - Max total drawdown: 20% ($200) => HARD KILL
    - Per-trade risk cap: 3% ($30)
    - Max concurrent positions: 3
    - Markets: Politics ONLY
    - Strategy: Copy 1 trader at 10% sizing
    """

    # Capital limits (v1 spec)
    starting_capital_usd: float = Field(
        1000.0, description="Starting capital in USD (v1 default: $1,000)"
    )

    # Risk limits (v1 spec)
    max_daily_drawdown_pct: float = Field(
        5.0, description="Max daily drawdown % (v1: 5% = $50)"
    )
    max_total_drawdown_pct: float = Field(
        20.0, description="Max total drawdown % before KILL SWITCH (v1: 20% = $200)"
    )
    per_trade_risk_pct: float = Field(
        3.0, description="Max risk per trade % (v1: 3% = $30)"
    )

    # Position limits
    max_concurrent_positions: int = Field(
        3, description="Maximum open positions at once (v1: 3)"
    )

    # Trader configuration
    trader_address: str = Field(
        ..., description="Single trader address to copy (required for v1)"
    )

    # Market filtering (v1: Politics ONLY)
    allowed_market_categories: Set[str] = Field(
        default_factory=lambda: {"politics"},
        description="Allowed market categories (v1: politics only)",
    )
    market_allowlist: Set[str] = Field(
        default_factory=set,
        description="Specific market IDs allowed (empty = all politics markets)",
    )

    # Position sizing (v1 spec)
    copy_percentage: float = Field(
        10.0, description="Copy % of trader's order size (v1: 10%)"
    )

    # Timing limits
    max_intent_age_seconds: int = Field(
        10, description="Reject intents older than this (v1: 10s staleness protection)"
    )
    poll_interval_seconds: int = Field(
        1, description="How often to poll for trader activity (v1: 1s)"
    )

    # Trader health kill criteria
    trader_max_7day_loss_pct: float = Field(
        15.0, description="Auto-pause trader if loses >15% in 7 days"
    )
    trader_min_win_rate_pct: float = Field(
        45.0, description="Auto-pause trader if win rate <45% over 20 trades"
    )
    trader_max_inactivity_hours: int = Field(
        48, description="Auto-pause trader if no activity for 48 hours"
    )

    # Safety limits
    max_slippage_pct: float = Field(
        5.0, description="Max allowed slippage %"
    )
    retry_limit: int = Field(
        3, description="Max retry attempts for failed orders"
    )

    # Kill switch tracking
    consecutive_daily_dd_limit: int = Field(
        3, description="Auto-kill after 3 consecutive days of >5% daily DD"
    )
    position_size_bug_multiplier: float = Field(
        3.0, description="Kill if position size exceeds 3x configured limit"
    )

    # Storage
    db_path: str = Field(
        "copytrader_v1.db", description="SQLite database path"
    )

    # Telegram alerts
    telegram_bot_token: Optional[str] = Field(
        None, description="Telegram bot token for alerts"
    )
    telegram_chat_id: Optional[str] = Field(
        None, description="Telegram chat ID for alerts"
    )

    @classmethod
    def from_env(cls) -> "CopyTraderV1Config":
        """Load config from environment variables with v1 defaults"""

        trader = os.getenv("FOLLOW_TRADER")
        if not trader:
            raise ValueError(
                "FOLLOW_TRADER is required for v1. "
                "Set to a single trader address from Polymarket leaderboard."
            )

        # Parse market allowlist (optional)
        market_allowlist_str = os.getenv("MARKET_ALLOWLIST", "")
        market_allowlist = set()
        if market_allowlist_str:
            market_allowlist = {
                m.strip() for m in market_allowlist_str.split(",") if m.strip()
            }

        return cls(
            # Required
            trader_address=trader.lower().strip(),

            # Optional overrides (fall back to v1 defaults)
            starting_capital_usd=float(os.getenv("STARTING_CAPITAL_USD", "1000.0")),
            max_daily_drawdown_pct=float(os.getenv("MAX_DAILY_DD_PCT", "5.0")),
            max_total_drawdown_pct=float(os.getenv("MAX_TOTAL_DD_PCT", "20.0")),
            per_trade_risk_pct=float(os.getenv("PER_TRADE_RISK_PCT", "3.0")),
            max_concurrent_positions=int(os.getenv("MAX_CONCURRENT_POSITIONS", "3")),
            copy_percentage=float(os.getenv("COPY_PERCENTAGE", "10.0")),
            market_allowlist=market_allowlist,

            # Telegram
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),

            # DB
            db_path=os.getenv("DB_PATH", "copytrader_v1.db"),
        )

    def get_max_daily_drawdown_usd(self) -> float:
        """Calculate max daily drawdown in USD"""
        return self.starting_capital_usd * (self.max_daily_drawdown_pct / 100.0)

    def get_max_total_drawdown_usd(self) -> float:
        """Calculate max total drawdown in USD (kill switch threshold)"""
        return self.starting_capital_usd * (self.max_total_drawdown_pct / 100.0)

    def get_max_position_size_usd(self) -> float:
        """Calculate max position size in USD"""
        return self.starting_capital_usd * (self.per_trade_risk_pct / 100.0)

    def is_market_allowed(self, market_category: str, market_id: str) -> bool:
        """
        Check if market is allowed for trading.

        v1: Politics only, with optional specific market allowlist
        """
        # Check category (must be politics)
        if market_category.lower() not in self.allowed_market_categories:
            return False

        # Check specific market allowlist if configured
        if self.market_allowlist and market_id not in self.market_allowlist:
            return False

        return True
