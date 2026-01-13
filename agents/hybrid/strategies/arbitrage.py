"""
Binary Arbitrage Strategy for Hybrid Bot

Adapted from PolyAgentVPS with improvements.

This strategy detects risk-free profit opportunities when:
YES price + NO price < 1.00 (guaranteed payout)

After fees, if profitable, buy both sides.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple
import logging

from agents.hybrid.strategies.base import (
    BaseStrategy,
    OrderBook,
    DualOrderBook,
    StrategyIntent,
)
from agents.hybrid.config import ArbitrageConfig

logger = logging.getLogger(__name__)


class BinaryArbitrageStrategy(BaseStrategy):
    """
    Arbitrage strategy for binary prediction markets.

    Detects opportunities when the combined cost of buying both YES and NO
    is less than $1.00 (the guaranteed payout). After accounting for fees,
    if a profitable opportunity exists, the strategy returns intents to
    buy both outcomes.

    The arbitrage profit comes from:
    - Guaranteed payout: One outcome MUST resolve to 1.0
    - Combined cost: YES ask + NO ask < 1.0
    - Net profit: 1.0 - combined_cost - fees
    """

    def __init__(self, config: Optional[ArbitrageConfig] = None):
        """
        Initialize arbitrage strategy.

        Args:
            config: Strategy configuration
        """
        super().__init__(name="arbitrage")
        self._config = config or ArbitrageConfig()

    def analyze(self, orderbook: OrderBook) -> Optional[StrategyIntent]:
        """
        Single orderbook analysis not applicable for arbitrage.

        Arbitrage requires both YES and NO books.
        """
        return None

    def analyze_dual(
        self, dual_book: DualOrderBook
    ) -> Optional[Tuple[StrategyIntent, StrategyIntent]]:
        """
        Analyze a dual orderbook for arbitrage opportunities.

        Returns tuple of (YES intent, NO intent) if profitable.
        """
        if not self._config.enabled:
            return None

        if not dual_book.is_complete:
            return None

        yes_book = dual_book.yes_book
        no_book = dual_book.no_book

        if yes_book is None or no_book is None:
            return None

        # Get best asks for both outcomes
        yes_ask = yes_book.best_ask
        no_ask = no_book.best_ask

        if yes_ask is None or no_ask is None:
            return None

        yes_price, yes_size = yes_ask
        no_price, no_size = no_ask

        # Calculate combined cost
        combined_cost = yes_price + no_price

        # No arbitrage if combined cost >= 1.0
        if combined_cost >= Decimal("1.0"):
            return None

        # Calculate net profit after fees
        net_profit = self._calculate_net_profit(yes_price, no_price)

        # Check if profit meets minimum threshold
        if net_profit < self._config.min_profit:
            logger.debug(
                f"Arbitrage profit {net_profit:.4f} below threshold {self._config.min_profit}"
            )
            return None

        # Calculate optimal size based on available liquidity
        size = self._calculate_optimal_size(yes_size, no_size)

        if size < self._config.min_size:
            logger.debug(f"Arbitrage size {size} below minimum {self._config.min_size}")
            return None

        # Calculate confidence based on profit margin
        confidence = self._calculate_confidence(net_profit, size)

        reason = (
            f"Arbitrage: YES@{yes_price:.3f} + NO@{no_price:.3f} = {combined_cost:.3f}, "
            f"net profit={net_profit:.3%}"
        )

        # Create YES buy intent
        yes_intent = StrategyIntent(
            market_id=dual_book.market_id,
            token_id=yes_book.token_id,
            outcome="YES",
            side="buy",
            price=yes_price,
            size=size,
            reason=reason,
            strategy_name=self.name,
            confidence=confidence,
            metadata={
                "arb_type": "binary",
                "combined_cost": float(combined_cost),
                "net_profit_pct": float(net_profit),
                "leg": "YES",
            }
        )

        # Create NO buy intent
        no_intent = StrategyIntent(
            market_id=dual_book.market_id,
            token_id=no_book.token_id,
            outcome="NO",
            side="buy",
            price=no_price,
            size=size,
            reason=reason,
            strategy_name=self.name,
            confidence=confidence,
            metadata={
                "arb_type": "binary",
                "combined_cost": float(combined_cost),
                "net_profit_pct": float(net_profit),
                "leg": "NO",
            }
        )

        logger.info(
            f"ARBITRAGE FOUND: {dual_book.market_id} | "
            f"YES@{yes_price:.3f} + NO@{no_price:.3f} = {combined_cost:.3f} | "
            f"Profit: {net_profit:.2%} | Size: {size}"
        )

        return (yes_intent, no_intent)

    def _calculate_net_profit(
        self,
        yes_price: Decimal,
        no_price: Decimal,
    ) -> Decimal:
        """
        Calculate net profit after fees.

        Gross profit = 1.0 - (yes_price + no_price)
        Fees = combined_cost * fee_rate
        Net profit = gross_profit - fees
        """
        combined_cost = yes_price + no_price
        gross_profit = Decimal("1.0") - combined_cost
        fees = combined_cost * self._config.fee_rate
        return gross_profit - fees

    def _calculate_optimal_size(
        self,
        yes_size: Decimal,
        no_size: Decimal,
    ) -> Decimal:
        """
        Calculate optimal position size.

        Limited by:
        1. Available liquidity on smaller side
        2. Max size config
        """
        available = min(yes_size, no_size)
        return min(available, self._config.max_size)

    def _calculate_confidence(
        self,
        net_profit: Decimal,
        size: Decimal,
    ) -> Decimal:
        """
        Calculate confidence score.

        Higher confidence when:
        - Larger profit margin
        - Larger available size
        """
        base_confidence = Decimal("0.85")  # Arbitrage is high confidence

        # Boost for larger profit
        profit_boost = min(net_profit * Decimal("5"), Decimal("0.10"))

        # Boost for larger size
        size_ratio = size / self._config.max_size
        if size_ratio >= Decimal("0.5"):
            size_boost = Decimal("0.03")
        else:
            size_boost = Decimal("0")

        return min(base_confidence + profit_boost + size_boost, Decimal("0.95"))

    def is_profitable(self, dual_book: DualOrderBook) -> bool:
        """Quick check if arbitrage exists."""
        if not dual_book.is_complete:
            return False

        yes_book = dual_book.yes_book
        no_book = dual_book.no_book

        if yes_book is None or no_book is None:
            return False

        yes_ask = yes_book.best_ask_price
        no_ask = no_book.best_ask_price

        if yes_ask is None or no_ask is None:
            return False

        combined = yes_ask + no_ask
        if combined >= Decimal("1.0"):
            return False

        net_profit = self._calculate_net_profit(yes_ask, no_ask)
        return net_profit >= self._config.min_profit

    def get_edge(self, dual_book: DualOrderBook) -> Optional[Decimal]:
        """Get arbitrage edge (net profit) if it exists."""
        if not dual_book.is_complete:
            return None

        yes_book = dual_book.yes_book
        no_book = dual_book.no_book

        if yes_book is None or no_book is None:
            return None

        yes_ask = yes_book.best_ask_price
        no_ask = no_book.best_ask_price

        if yes_ask is None or no_ask is None:
            return None

        if yes_ask + no_ask >= Decimal("1.0"):
            return None

        return self._calculate_net_profit(yes_ask, no_ask)


def create_arbitrage_strategy(
    config: Optional[ArbitrageConfig] = None,
) -> BinaryArbitrageStrategy:
    """Factory function to create arbitrage strategy."""
    return BinaryArbitrageStrategy(config=config)
