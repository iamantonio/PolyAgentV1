"""
Hybrid Bot Configuration

Combines validated dataclass config from PolyAgentVPS with
learning parameters from Learning Autonomous Trader.

All monetary values use Decimal for precision.
All configs are frozen (immutable) for thread safety.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
import os


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """
    Risk management limits - from PolyAgentVPS.

    All limits are enforced by the RiskManager before execution.
    """
    max_position_size: Decimal = Decimal("50")      # Max $ per single trade
    max_total_exposure: Decimal = Decimal("200")    # Max $ total open positions
    max_daily_loss: Decimal = Decimal("25")         # Stop trading after this loss
    max_single_trade: Decimal = Decimal("50")       # Max $ per order
    max_positions: int = 10                         # Max concurrent positions
    min_balance: Decimal = Decimal("10")            # Min balance to trade
    cooldown_after_loss: int = 300                  # Seconds to pause after loss
    max_position_per_market: Decimal = Decimal("100")  # Max exposure per market

    def __post_init__(self) -> None:
        """Validate all limits are positive."""
        if self.max_position_size <= Decimal("0"):
            raise ValueError(f"max_position_size must be positive: {self.max_position_size}")
        if self.max_total_exposure <= Decimal("0"):
            raise ValueError(f"max_total_exposure must be positive: {self.max_total_exposure}")
        if self.max_daily_loss <= Decimal("0"):
            raise ValueError(f"max_daily_loss must be positive: {self.max_daily_loss}")
        if self.max_positions <= 0:
            raise ValueError(f"max_positions must be positive: {self.max_positions}")
        if self.min_balance < Decimal("0"):
            raise ValueError(f"min_balance must be non-negative: {self.min_balance}")


@dataclass(frozen=True, slots=True)
class LearningConfig:
    """
    Learning system configuration - from Learning Autonomous Trader.

    Controls AI edge detection and ML parameters.
    """
    min_confidence: Decimal = Decimal("0.55")       # Min confidence to trade
    min_sample_size: int = 20                       # Min trades before trusting learning
    apply_calibration: bool = True                  # Apply isotonic calibration
    calibration_shift: Decimal = Decimal("-0.044") # Overconfidence adjustment
    use_multi_agent: bool = True                    # Enable multi-agent reasoning
    use_crypto_edge: bool = True                    # Enable crypto signal detection
    edge_threshold: Decimal = Decimal("0")          # Min P&L to consider "edge"

    def __post_init__(self) -> None:
        """Validate learning parameters."""
        if not (Decimal("0") <= self.min_confidence <= Decimal("1")):
            raise ValueError(f"min_confidence must be 0-1: {self.min_confidence}")
        if self.min_sample_size < 0:
            raise ValueError(f"min_sample_size must be non-negative: {self.min_sample_size}")


@dataclass(frozen=True, slots=True)
class KellySizingConfig:
    """
    Kelly criterion position sizing - from Learning Autonomous Trader.
    """
    enabled: bool = True
    fraction: Decimal = Decimal("0.25")    # Use 1/4 Kelly (conservative)
    min_edge: Decimal = Decimal("0.02")    # Min edge to apply Kelly
    max_bet_fraction: Decimal = Decimal("0.10")  # Never bet more than 10% of bankroll

    def __post_init__(self) -> None:
        """Validate Kelly parameters."""
        if not (Decimal("0") < self.fraction <= Decimal("1")):
            raise ValueError(f"fraction must be 0-1: {self.fraction}")
        if not (Decimal("0") <= self.max_bet_fraction <= Decimal("1")):
            raise ValueError(f"max_bet_fraction must be 0-1: {self.max_bet_fraction}")


@dataclass(frozen=True, slots=True)
class ArbitrageConfig:
    """
    Arbitrage strategy configuration - from PolyAgentVPS.
    """
    enabled: bool = True
    min_profit: Decimal = Decimal("0.005")     # Min profit margin (0.5%)
    fee_rate: Decimal = Decimal("0.02")        # Expected fee rate (2%)
    min_size: Decimal = Decimal("25")          # Min position size
    max_size: Decimal = Decimal("500")         # Max position size
    max_execution_ms: int = 1000               # Max time for both legs

    def __post_init__(self) -> None:
        """Validate arbitrage parameters."""
        if self.min_profit < Decimal("0"):
            raise ValueError(f"min_profit must be non-negative: {self.min_profit}")
        if not (Decimal("0") <= self.fee_rate <= Decimal("1")):
            raise ValueError(f"fee_rate must be 0-1: {self.fee_rate}")


@dataclass(frozen=True, slots=True)
class MarketMakingConfig:
    """
    Market making strategy configuration - from PolyAgentVPS.
    """
    enabled: bool = False  # Disabled by default (requires more capital)
    base_spread: Decimal = Decimal("0.02")     # 2% spread
    min_spread: Decimal = Decimal("0.01")      # 1% min spread
    max_spread: Decimal = Decimal("0.10")      # 10% max spread
    base_size: Decimal = Decimal("50")         # Order size
    max_inventory: Decimal = Decimal("500")    # Max net position
    inventory_skew_factor: Decimal = Decimal("0.5")

    def __post_init__(self) -> None:
        """Validate market making parameters."""
        if self.base_spread < Decimal("0"):
            raise ValueError(f"base_spread must be non-negative: {self.base_spread}")
        if self.min_spread > self.max_spread:
            raise ValueError(f"min_spread must be <= max_spread")


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """
    Order execution configuration.
    """
    dry_run: bool = True                       # Safe default: don't execute
    max_retries: int = 3                       # Retry failed orders
    retry_delay_ms: int = 500                  # Delay between retries
    idempotency_window_hours: int = 24         # Dedupe window

    def __post_init__(self) -> None:
        """Validate execution parameters."""
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be non-negative: {self.max_retries}")


@dataclass(frozen=True, slots=True)
class AlertConfig:
    """
    Alerting configuration - from Learning Autonomous Trader.
    """
    discord_enabled: bool = True
    alert_on_trade: bool = True
    alert_on_error: bool = True
    alert_on_daily_summary: bool = True


@dataclass(frozen=True, slots=True)
class HybridConfig:
    """
    Master configuration for the Hybrid Bot.

    Combines all sub-configurations with sensible defaults.
    """
    # Core settings
    bankroll: Decimal = Decimal("100")
    db_path: str = field(default_factory=lambda: os.path.expanduser("~/.polymarket/hybrid_trader.db"))

    # Sub-configurations
    risk: RiskLimits = field(default_factory=RiskLimits)
    learning: LearningConfig = field(default_factory=LearningConfig)
    kelly: KellySizingConfig = field(default_factory=KellySizingConfig)
    arbitrage: ArbitrageConfig = field(default_factory=ArbitrageConfig)
    market_making: MarketMakingConfig = field(default_factory=MarketMakingConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)

    # Strategy priorities (higher = preferred)
    strategy_priority: tuple = field(default_factory=lambda: (
        "arbitrage",      # Priority 1: Risk-free profit
        "ai_edge",        # Priority 2: AI-detected edge
        "market_making",  # Priority 3: Spread capture
    ))

    def __post_init__(self) -> None:
        """Validate master config."""
        if self.bankroll <= Decimal("0"):
            raise ValueError(f"bankroll must be positive: {self.bankroll}")

    @classmethod
    def from_env(cls) -> "HybridConfig":
        """Create config from environment variables."""
        return cls(
            bankroll=Decimal(os.getenv("BANKROLL", "100")),
            db_path=os.getenv("HYBRID_DB_PATH", os.path.expanduser("~/.polymarket/hybrid_trader.db")),
            execution=ExecutionConfig(
                dry_run=os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes"),
            ),
        )


def get_default_config() -> HybridConfig:
    """Get default hybrid bot configuration."""
    return HybridConfig()


def get_aggressive_config() -> HybridConfig:
    """Get aggressive trading configuration (higher risk/reward)."""
    return HybridConfig(
        bankroll=Decimal("100"),
        risk=RiskLimits(
            max_position_size=Decimal("100"),
            max_total_exposure=Decimal("300"),
            max_daily_loss=Decimal("50"),
            max_positions=15,
        ),
        learning=LearningConfig(
            min_confidence=Decimal("0.50"),  # Lower threshold
            min_sample_size=10,
        ),
        kelly=KellySizingConfig(
            fraction=Decimal("0.50"),  # Half Kelly
        ),
    )


def get_conservative_config() -> HybridConfig:
    """Get conservative trading configuration (lower risk)."""
    return HybridConfig(
        bankroll=Decimal("100"),
        risk=RiskLimits(
            max_position_size=Decimal("25"),
            max_total_exposure=Decimal("100"),
            max_daily_loss=Decimal("15"),
            max_positions=5,
            cooldown_after_loss=600,  # 10 min cooldown
        ),
        learning=LearningConfig(
            min_confidence=Decimal("0.65"),  # Higher threshold
            min_sample_size=30,
        ),
        kelly=KellySizingConfig(
            fraction=Decimal("0.125"),  # 1/8 Kelly
        ),
    )
