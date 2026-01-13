"""
Strategy Base Classes for Hybrid Bot

Combines the StrategyIntent pattern from PolyAgentVPS with
learning integration from Learning Autonomous Trader.

Key design:
- Strategies produce INTENTS, not orders
- Intents are validated by RiskManager before execution
- This separation allows for clean testing and auditing
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any


@dataclass(frozen=True, slots=True)
class StrategyIntent:
    """
    A trading intent produced by a strategy.

    This is NOT an order - it's a RECOMMENDATION that must be
    validated by the RiskManager before execution.

    Frozen for thread safety and to prevent accidental modification.
    """
    market_id: str
    token_id: str
    outcome: str               # "YES" or "NO"
    side: str                  # "buy" or "sell"
    price: Decimal
    size: Decimal
    reason: str                # Human-readable explanation
    strategy_name: str
    confidence: Decimal = Decimal("0.5")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"Intent({self.strategy_name}: {self.side.upper()} {self.size} "
            f"{self.outcome} @ {self.price:.3f}, conf={self.confidence:.2f})"
        )

    @property
    def is_buy(self) -> bool:
        return self.side.lower() == "buy"

    @property
    def is_sell(self) -> bool:
        return self.side.lower() == "sell"


@dataclass(frozen=True, slots=True)
class OrderBook:
    """
    Simplified orderbook snapshot for strategy analysis.
    """
    market_id: str
    token_id: str
    outcome: str                          # "YES" or "NO"
    bids: List[tuple[Decimal, Decimal]]   # [(price, size), ...]
    asks: List[tuple[Decimal, Decimal]]   # [(price, size), ...]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def best_bid(self) -> Optional[tuple[Decimal, Decimal]]:
        """Best bid (highest buy price)."""
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[tuple[Decimal, Decimal]]:
        """Best ask (lowest sell price)."""
        return self.asks[0] if self.asks else None

    @property
    def best_bid_price(self) -> Optional[Decimal]:
        return self.bids[0][0] if self.bids else None

    @property
    def best_ask_price(self) -> Optional[Decimal]:
        return self.asks[0][0] if self.asks else None

    @property
    def mid_price(self) -> Optional[Decimal]:
        """Mid-market price."""
        if self.best_bid_price and self.best_ask_price:
            return (self.best_bid_price + self.best_ask_price) / Decimal("2")
        return None

    @property
    def spread(self) -> Optional[Decimal]:
        """Bid-ask spread."""
        if self.best_bid_price and self.best_ask_price:
            return self.best_ask_price - self.best_bid_price
        return None


@dataclass(frozen=True, slots=True)
class DualOrderBook:
    """
    Combined YES/NO orderbooks for a binary market.

    Required for arbitrage analysis.
    """
    market_id: str
    yes_book: Optional[OrderBook] = None
    no_book: Optional[OrderBook] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_complete(self) -> bool:
        """Check if both books are available."""
        return self.yes_book is not None and self.no_book is not None


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Subclasses must implement:
    - analyze(): Analyze a single orderbook
    - name: Strategy identifier

    Optional overrides:
    - analyze_dual(): Analyze both sides (for arbitrage)
    - on_book_update(): Handle incremental updates
    - reset(): Reset internal state
    """

    def __init__(self, name: str):
        self._name = name
        self._enabled = True

    @property
    def name(self) -> str:
        """Strategy identifier."""
        return self._name

    @property
    def enabled(self) -> bool:
        """Whether strategy is active."""
        return self._enabled

    def enable(self) -> None:
        """Enable the strategy."""
        self._enabled = True

    def disable(self) -> None:
        """Disable the strategy."""
        self._enabled = False

    @abstractmethod
    def analyze(self, orderbook: OrderBook) -> Optional[StrategyIntent]:
        """
        Analyze an orderbook and optionally return a trading intent.

        Args:
            orderbook: Current orderbook snapshot

        Returns:
            StrategyIntent if strategy wants to trade, None otherwise
        """
        pass

    def analyze_dual(
        self, dual_book: DualOrderBook
    ) -> Optional[tuple[StrategyIntent, StrategyIntent]]:
        """
        Analyze both sides of a binary market.

        Default implementation returns None (no dual-book analysis).
        Override for arbitrage and other dual-book strategies.

        Args:
            dual_book: Combined YES/NO orderbooks

        Returns:
            Tuple of (YES intent, NO intent) if both sides should trade,
            None otherwise
        """
        return None

    def on_book_update(self, update: Dict[str, Any]) -> None:
        """
        Handle an incremental orderbook update.

        Default implementation does nothing (stateless).
        Override for strategies that track state.

        Args:
            update: Raw update from exchange
        """
        pass

    def reset(self) -> None:
        """
        Reset internal state.

        Called when reconnecting or switching markets.
        Default implementation does nothing.
        """
        pass

    def __repr__(self) -> str:
        status = "enabled" if self._enabled else "disabled"
        return f"{self.__class__.__name__}(name={self._name}, {status})"


class LearningStrategy(BaseStrategy):
    """
    Base class for strategies that integrate with the learning system.

    Adds:
    - Edge detection by market type
    - Confidence calibration
    - Feature extraction for ML
    """

    def __init__(self, name: str):
        super().__init__(name)
        self._edge_by_type: Dict[str, Decimal] = {}
        self._calibration_shift: Decimal = Decimal("0")

    def update_edge_data(self, edge_by_type: Dict[str, Decimal]) -> None:
        """Update edge detection data."""
        self._edge_by_type = edge_by_type

    def set_calibration_shift(self, shift: Decimal) -> None:
        """Set calibration shift for confidence adjustment."""
        self._calibration_shift = shift

    def has_edge(self, market_type: str) -> bool:
        """Check if we have positive edge in this market type."""
        if not self._edge_by_type:
            return True  # No data = assume edge
        return self._edge_by_type.get(market_type, Decimal("0")) >= Decimal("0")

    def calibrate_confidence(self, raw_confidence: Decimal) -> Decimal:
        """Apply calibration shift to raw confidence."""
        calibrated = raw_confidence + self._calibration_shift
        return max(Decimal("0"), min(Decimal("1"), calibrated))


class StrategyManager:
    """
    Manages multiple strategies and coordinates analysis.
    """

    def __init__(self):
        self._strategies: List[BaseStrategy] = []

    def add_strategy(self, strategy: BaseStrategy) -> None:
        """Add a strategy to the manager."""
        self._strategies.append(strategy)

    def remove_strategy(self, name: str) -> bool:
        """Remove a strategy by name."""
        for i, s in enumerate(self._strategies):
            if s.name == name:
                self._strategies.pop(i)
                return True
        return False

    def get_strategy(self, name: str) -> Optional[BaseStrategy]:
        """Get a strategy by name."""
        for s in self._strategies:
            if s.name == name:
                return s
        return None

    @property
    def strategies(self) -> List[BaseStrategy]:
        """Get all strategies."""
        return list(self._strategies)

    @property
    def enabled_strategies(self) -> List[BaseStrategy]:
        """Get enabled strategies only."""
        return [s for s in self._strategies if s.enabled]

    def analyze_all(
        self, orderbook: OrderBook
    ) -> List[StrategyIntent]:
        """
        Run all enabled strategies against an orderbook.

        Returns all intents (may be empty).
        """
        intents = []
        for strategy in self.enabled_strategies:
            try:
                intent = strategy.analyze(orderbook)
                if intent is not None:
                    intents.append(intent)
            except Exception as e:
                # Log but don't crash on strategy errors
                import logging
                logging.error(f"Strategy {strategy.name} error: {e}")
        return intents

    def analyze_dual_all(
        self, dual_book: DualOrderBook
    ) -> List[tuple[StrategyIntent, StrategyIntent]]:
        """
        Run all enabled strategies' dual-book analysis.

        Returns all intent pairs (may be empty).
        """
        results = []
        for strategy in self.enabled_strategies:
            try:
                result = strategy.analyze_dual(dual_book)
                if result is not None:
                    results.append(result)
            except Exception as e:
                import logging
                logging.error(f"Strategy {strategy.name} dual analysis error: {e}")
        return results

    def reset_all(self) -> None:
        """Reset all strategies."""
        for strategy in self._strategies:
            strategy.reset()
