"""
CopyTrader execution strategy.

This module implements the actual trade execution logic based on validated intents.
It integrates with the existing Polymarket order execution path and adds:
- Position sizing strategies (FIXED, PERCENTAGE, TIERED)
- Slippage protection
- Purchase tracking for accurate sells
"""

import logging
from enum import Enum
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from agents.copytrader.schema import TradeIntent, Side
from agents.copytrader.config import CopyTraderConfig
from agents.copytrader.tracking import PurchaseTracker
from agents.polymarket.polymarket import Polymarket

logger = logging.getLogger(__name__)


class SizingStrategy(str, Enum):
    """Position sizing strategies"""

    FIXED = "FIXED"  # Fixed dollar amount per trade
    PERCENTAGE = "PERCENTAGE"  # Percentage of trader's order
    TIERED = "TIERED"  # Tiered multipliers based on order size


@dataclass
class SizingConfig:
    """Configuration for position sizing"""

    strategy: SizingStrategy = SizingStrategy.PERCENTAGE
    base_size: float = 10.0  # Meaning depends on strategy
    tiered_multipliers: Optional[Dict[Tuple[float, float], float]] = None

    @classmethod
    def from_env(cls) -> "SizingConfig":
        """Create sizing config from environment"""
        import os

        strategy_str = os.getenv("COPY_SIZING_STRATEGY", "PERCENTAGE")
        strategy = SizingStrategy(strategy_str)

        base_size = float(os.getenv("COPY_SIZE", "10.0"))

        # Parse tiered multipliers if provided
        # Format: "min-max:mult,min-max:mult,min+:mult"
        # Example: "1-100:2.0,100-1000:0.5,1000+:0.1"
        tiered_str = os.getenv("TIERED_MULTIPLIERS", "")
        tiered_multipliers = None

        if tiered_str and strategy == SizingStrategy.TIERED:
            tiered_multipliers = {}
            for tier in tiered_str.split(","):
                range_part, mult_part = tier.split(":")
                mult = float(mult_part)

                if "+" in range_part:
                    # Unbounded upper range
                    min_val = float(range_part.replace("+", ""))
                    tiered_multipliers[(min_val, float("inf"))] = mult
                else:
                    # Bounded range
                    min_val, max_val = map(float, range_part.split("-"))
                    tiered_multipliers[(min_val, max_val)] = mult

        return cls(
            strategy=strategy,
            base_size=base_size,
            tiered_multipliers=tiered_multipliers,
        )


class OrderBookGuard:
    """
    Protects against bad fills by checking orderbook before execution.

    This reads the actual orderbook and validates that:
    1. There's sufficient liquidity
    2. Price hasn't moved beyond slippage tolerance
    """

    def __init__(self, polymarket: Polymarket, config: CopyTraderConfig):
        self.polymarket = polymarket
        self.config = config

    def check_orderbook(
        self, intent: TradeIntent
    ) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Check orderbook for safe execution.

        Returns:
            (can_execute, reason, adjusted_price)
        """
        try:
            # Get orderbook from Polymarket
            # Note: This requires adding get_orderbook method to Polymarket class
            # For now, we'll assume it exists or add it
            orderbook = self._get_orderbook(intent.market_id)

            if intent.side == Side.BUY:
                # Check asks (we're buying)
                if not orderbook.get("asks"):
                    return False, "No asks available in orderbook", None

                best_ask = min(float(ask["price"]) for ask in orderbook["asks"])

                # Check slippage vs observed price
                if intent.metadata.best_ask:
                    observed_price = intent.metadata.best_ask
                    slippage = ((best_ask - observed_price) / observed_price) * 100

                    if slippage > self.config.max_slippage_percent:
                        return (
                            False,
                            f"Slippage too high: {slippage:.2f}% (max {self.config.max_slippage_percent}%)",
                            None,
                        )

                # Check price limit
                if intent.price_limit and best_ask > intent.price_limit:
                    return (
                        False,
                        f"Price ${best_ask:.4f} exceeds limit ${intent.price_limit:.4f}",
                        None,
                    )

                return True, None, best_ask

            else:  # SELL
                # Check bids (we're selling)
                if not orderbook.get("bids"):
                    return False, "No bids available in orderbook", None

                best_bid = max(float(bid["price"]) for bid in orderbook["bids"])

                # Check slippage vs observed price
                if intent.metadata.best_bid:
                    observed_price = intent.metadata.best_bid
                    slippage = ((observed_price - best_bid) / observed_price) * 100

                    if slippage > self.config.max_slippage_percent:
                        return (
                            False,
                            f"Slippage too high: {slippage:.2f}% (max {self.config.max_slippage_percent}%)",
                            None,
                        )

                # Check price limit
                if intent.price_limit and best_bid < intent.price_limit:
                    return (
                        False,
                        f"Price ${best_bid:.4f} below limit ${intent.price_limit:.4f}",
                        None,
                    )

                return True, None, best_bid

        except Exception as e:
            logger.error(f"Error checking orderbook: {e}", exc_info=True)
            return False, f"Orderbook check failed: {e}", None

    def _get_orderbook(self, market_id: str) -> dict:
        """
        Get orderbook for a market.

        This is a placeholder - the actual implementation depends on
        how Polymarket class is structured.
        """
        # TODO: Integrate with actual Polymarket.get_orderbook() method
        # For now, return empty dict
        logger.warning("OrderBook check not fully implemented - requires Polymarket integration")
        return {"asks": [], "bids": []}


class CopyTraderStrategy:
    """
    Main strategy class for copy trading.

    This coordinates:
    - Intent consumption from ingestor
    - Position sizing calculation
    - Orderbook validation
    - Order execution via Polymarket
    - Purchase tracking
    """

    def __init__(
        self,
        polymarket: Polymarket,
        config: CopyTraderConfig,
        sizing_config: SizingConfig,
        tracker: Optional[PurchaseTracker] = None,
    ):
        self.polymarket = polymarket
        self.config = config
        self.sizing_config = sizing_config
        self.tracker = tracker or PurchaseTracker()
        self.orderbook_guard = OrderBookGuard(polymarket, config)
        self._execution_count = 0
        self._rejection_count = 0

    def calculate_order_size(self, intent: TradeIntent, balance: float) -> float:
        """
        Calculate order size based on sizing strategy.

        Args:
            intent: Trade intent
            balance: Current USDC balance

        Returns:
            Order size in USDC (for BUY) or tokens (for SELL)
        """
        if self.sizing_config.strategy == SizingStrategy.FIXED:
            # Fixed dollar amount per trade
            return min(self.sizing_config.base_size, balance)

        elif self.sizing_config.strategy == SizingStrategy.PERCENTAGE:
            # Percentage of trader's order
            if intent.size_usdc:
                trader_size = intent.size_usdc
            else:
                # Estimate USDC value for token size
                trader_size = (
                    intent.size_tokens * intent.metadata.best_ask
                    if intent.metadata.best_ask
                    else 0
                )

            size = trader_size * (self.sizing_config.base_size / 100.0)
            return min(size, balance)

        elif self.sizing_config.strategy == SizingStrategy.TIERED:
            # Tiered multipliers based on trader order size
            if not self.sizing_config.tiered_multipliers:
                logger.warning("TIERED strategy configured but no multipliers set")
                return 0.0

            trader_size = intent.size_usdc or (
                intent.size_tokens * intent.metadata.best_ask
                if intent.metadata.best_ask
                else 0
            )

            # Find matching tier
            multiplier = 1.0
            for (min_val, max_val), mult in self.sizing_config.tiered_multipliers.items():
                if min_val <= trader_size < max_val:
                    multiplier = mult
                    break

            size = trader_size * multiplier
            logger.info(
                f"Tiered sizing: trader ${trader_size:.2f} × {multiplier}x = ${size:.2f}"
            )

            return min(size, balance)

        return 0.0

    def execute_intent(self, intent: TradeIntent) -> bool:
        """
        Execute a validated trade intent.

        Returns:
            True if executed successfully, False otherwise
        """
        try:
            logger.info(f"Executing intent {intent.intent_id[:8]}: {intent.side} {intent.market_id[:16]}...")

            # Check orderbook before proceeding
            can_execute, reason, current_price = self.orderbook_guard.check_orderbook(
                intent
            )
            if not can_execute:
                logger.warning(f"Orderbook check failed: {reason}")
                self._rejection_count += 1
                return False

            if intent.side == Side.BUY:
                return self._execute_buy(intent, current_price)
            else:
                return self._execute_sell(intent, current_price)

        except Exception as e:
            logger.error(f"Error executing intent: {e}", exc_info=True)
            self._rejection_count += 1
            return False

    def _execute_buy(self, intent: TradeIntent, current_price: Optional[float]) -> bool:
        """Execute BUY order"""
        # Get current balance
        balance = self.polymarket.get_balance()

        # Calculate order size
        order_size = self.calculate_order_size(intent, balance)

        # Check minimum
        if order_size < self.config.min_order_size_usdc:
            logger.warning(
                f"Order size ${order_size:.2f} below minimum ${self.config.min_order_size_usdc:.2f}"
            )
            self._rejection_count += 1
            return False

        # Execute order via Polymarket
        logger.info(f"Placing BUY order: ${order_size:.2f} on {intent.market_id[:16]}...")

        # TODO: Integrate with actual Polymarket.execute_market_order()
        # This is a placeholder for the integration
        tokens_bought = self._execute_order_placeholder(
            intent.market_id, "BUY", order_size, current_price
        )

        if tokens_bought > 0:
            # Track purchase
            self.tracker.track_buy(
                market_id=intent.market_id,
                asset_id=intent.market_id,  # TODO: Map to actual asset_id
                tokens_bought=tokens_bought,
                price_paid=current_price or 0.0,
                usdc_spent=order_size,
                source_trader=intent.source_trader,
                intent_id=intent.intent_id,
            )

            self._execution_count += 1
            logger.info(f"✓ BUY executed: {tokens_bought:.2f} tokens for ${order_size:.2f}")
            return True

        self._rejection_count += 1
        return False

    def _execute_sell(self, intent: TradeIntent, current_price: Optional[float]) -> bool:
        """Execute SELL order"""
        # Calculate sell amount based on tracked purchases
        trader_sell_percent = (
            intent.metadata.trader_order_usd / intent.metadata.trader_position_size
            if intent.metadata.trader_position_size
            else 1.0  # Assume full close if no position data
        )

        tokens_to_sell = self.tracker.calculate_sell_amount(
            market_id=intent.market_id,
            asset_id=intent.market_id,  # TODO: Map to actual asset_id
            trader_sell_percent=trader_sell_percent,
        )

        if tokens_to_sell == 0:
            logger.warning("No tokens to sell (no tracked purchases)")
            self._rejection_count += 1
            return False

        # Execute order
        logger.info(f"Placing SELL order: {tokens_to_sell:.2f} tokens on {intent.market_id[:16]}...")

        # TODO: Integrate with actual Polymarket.execute_market_order()
        tokens_sold = self._execute_order_placeholder(
            intent.market_id, "SELL", tokens_to_sell, current_price
        )

        if tokens_sold > 0:
            # Track sale
            self.tracker.track_sell(
                market_id=intent.market_id,
                asset_id=intent.market_id,  # TODO: Map to actual asset_id
                tokens_sold=tokens_sold,
            )

            self._execution_count += 1
            logger.info(f"✓ SELL executed: {tokens_sold:.2f} tokens")
            return True

        self._rejection_count += 1
        return False

    def _execute_order_placeholder(
        self, market_id: str, side: str, size: float, price: Optional[float]
    ) -> float:
        """
        Placeholder for order execution.

        TODO: Replace with actual Polymarket.execute_market_order() integration
        """
        logger.warning(
            "Using placeholder order execution - integrate with Polymarket.execute_market_order()"
        )
        # Return mock value for testing
        return size if side == "SELL" else (size / price if price else 0)

    def get_stats(self) -> dict:
        """Get strategy statistics"""
        return {
            "executions": self._execution_count,
            "rejections": self._rejection_count,
            "sizing_strategy": self.sizing_config.strategy.value,
            **self.tracker.backend.get_stats(),
        }
