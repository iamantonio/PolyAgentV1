"""
Hybrid Bot Runner

The main orchestrator that combines:
- AI edge detection (from Learning Autonomous Trader)
- Arbitrage/MM strategies (from PolyAgentVPS)
- Sophisticated risk management
- Position tracking and P&L

This is the BRAIN of the hybrid bot.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Callable, Awaitable

from agents.hybrid.config import HybridConfig, get_default_config
from agents.hybrid.risk.manager import RiskManager, RiskCheckResult
from agents.hybrid.strategies.base import (
    BaseStrategy,
    StrategyManager,
    OrderBook,
    DualOrderBook,
    StrategyIntent,
)
from agents.hybrid.execution.executor import OrderExecutor, ExecutionResult

logger = logging.getLogger(__name__)


@dataclass
class RunnerStats:
    """Statistics for the runner session."""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    iterations: int = 0
    intents_generated: int = 0
    intents_approved: int = 0
    intents_rejected: int = 0
    orders_executed: int = 0
    orders_failed: int = 0
    arbitrage_opportunities: int = 0
    total_pnl: Decimal = Decimal("0")
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "runtime_seconds": (datetime.now(timezone.utc) - self.started_at).total_seconds(),
            "iterations": self.iterations,
            "intents_generated": self.intents_generated,
            "intents_approved": self.intents_approved,
            "intents_rejected": self.intents_rejected,
            "orders_executed": self.orders_executed,
            "orders_failed": self.orders_failed,
            "arbitrage_opportunities": self.arbitrage_opportunities,
            "total_pnl": float(self.total_pnl),
            "errors": self.errors,
        }


class HybridRunner:
    """
    Main runner that orchestrates all components.

    Priority order:
    1. Arbitrage (risk-free profit)
    2. AI edge detection (learned patterns)
    3. Market making (spread capture)

    Each iteration:
    1. Sync positions with chain
    2. Update edge data from learning system
    3. Scan for arbitrage
    4. Run AI analysis on markets
    5. Validate intents through risk manager
    6. Execute approved orders
    """

    def __init__(
        self,
        config: Optional[HybridConfig] = None,
        polymarket_client: Optional[Any] = None,
        discord_alerter: Optional[Any] = None,
    ):
        """
        Initialize hybrid runner.

        Args:
            config: Bot configuration
            polymarket_client: Polymarket API client
            discord_alerter: Discord alert client
        """
        self._config = config or get_default_config()
        self._client = polymarket_client
        self._discord = discord_alerter

        # Initialize components
        self._strategy_manager = StrategyManager()
        self._risk_manager: Optional[RiskManager] = None
        self._executor: Optional[OrderExecutor] = None

        # State
        self._running = False
        self._stats = RunnerStats()
        self._balance = self._config.bankroll
        self._last_sync_time = 0
        self._sync_interval = 1800  # 30 minutes

        # Callbacks (to be set by user)
        self._get_markets: Optional[Callable[[], Awaitable[List[Dict]]]] = None
        self._get_orderbook: Optional[Callable[[str], Awaitable[OrderBook]]] = None
        self._get_dual_book: Optional[Callable[[str], Awaitable[DualOrderBook]]] = None
        self._get_balance: Optional[Callable[[], Awaitable[Decimal]]] = None
        self._sync_positions: Optional[Callable[[], Awaitable[None]]] = None
        self._get_daily_pnl: Optional[Callable[[], Decimal]] = None
        self._get_open_positions: Optional[Callable[[], List[Dict]]] = None

        logger.info(f"HybridRunner initialized with config: {self._config}")

    def setup(
        self,
        strategies: List[BaseStrategy],
        get_markets: Callable[[], Awaitable[List[Dict]]],
        get_orderbook: Callable[[str], Awaitable[OrderBook]],
        get_dual_book: Callable[[str], Awaitable[DualOrderBook]],
        get_balance: Callable[[], Awaitable[Decimal]],
        sync_positions: Optional[Callable[[], Awaitable[None]]] = None,
        get_daily_pnl: Optional[Callable[[], Decimal]] = None,
        get_open_positions: Optional[Callable[[], List[Dict]]] = None,
        get_position_value: Optional[Callable[[str], Decimal]] = None,
    ) -> None:
        """
        Set up runner with callbacks.

        Args:
            strategies: List of trading strategies
            get_markets: Callback to fetch available markets
            get_orderbook: Callback to fetch orderbook for a market
            get_dual_book: Callback to fetch dual orderbook (YES + NO)
            get_balance: Callback to fetch current balance
            sync_positions: Callback to sync positions with chain
            get_daily_pnl: Callback to get today's P&L
            get_open_positions: Callback to get open positions
            get_position_value: Callback to get position value by market
        """
        # Set callbacks
        self._get_markets = get_markets
        self._get_orderbook = get_orderbook
        self._get_dual_book = get_dual_book
        self._get_balance = get_balance
        self._sync_positions = sync_positions
        self._get_daily_pnl = get_daily_pnl or (lambda: Decimal("0"))
        self._get_open_positions = get_open_positions or (lambda: [])

        # Add strategies
        for strategy in strategies:
            self._strategy_manager.add_strategy(strategy)

        # Initialize risk manager
        self._risk_manager = RiskManager(
            limits=self._config.risk,
            get_daily_pnl=get_daily_pnl or (lambda: Decimal("0")),
            get_open_positions=get_open_positions or (lambda: []),
            get_position_value=get_position_value or (lambda m: Decimal("0")),
        )

        # Initialize executor
        self._executor = OrderExecutor(
            config=self._config.execution,
            polymarket_client=self._client,
        )

        logger.info(
            f"Runner setup complete with {len(strategies)} strategies: "
            f"{[s.name for s in strategies]}"
        )

    async def run(
        self,
        loop_delay: float = 60.0,
        max_iterations: Optional[int] = None,
    ) -> None:
        """
        Main run loop.

        Args:
            loop_delay: Seconds between iterations
            max_iterations: Max iterations (None = infinite)
        """
        self._running = True
        self._stats = RunnerStats()

        logger.info("=" * 60)
        logger.info("HYBRID BOT STARTING")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY-RUN' if self._config.execution.dry_run else 'LIVE'}")
        logger.info(f"Bankroll: ${self._config.bankroll}")
        logger.info(f"Strategies: {[s.name for s in self._strategy_manager.strategies]}")
        logger.info("=" * 60)

        if self._discord:
            try:
                self._discord.send_startup_alert(
                    mode="DRY-RUN" if self._config.execution.dry_run else "LIVE",
                    strategies=[s.name for s in self._strategy_manager.strategies],
                )
            except Exception as e:
                logger.warning(f"Discord alert failed: {e}")

        iteration = 0
        while self._running:
            try:
                await self._run_iteration()
                self._stats.iterations += 1
                iteration += 1

                if max_iterations and iteration >= max_iterations:
                    logger.info(f"Max iterations ({max_iterations}) reached")
                    break

            except asyncio.CancelledError:
                logger.info("Runner cancelled")
                break
            except Exception as e:
                self._stats.errors += 1
                logger.error(f"Iteration error: {e}", exc_info=True)

                if self._discord:
                    try:
                        self._discord.alert_error("Iteration error", str(e))
                    except:
                        pass

            await asyncio.sleep(loop_delay)

        logger.info("Hybrid bot stopped")
        logger.info(f"Final stats: {self._stats.to_dict()}")

    async def _run_iteration(self) -> None:
        """Run a single iteration."""
        now = time.time()

        # 1. Sync positions periodically
        if self._sync_positions and (now - self._last_sync_time) > self._sync_interval:
            await self._sync_positions()
            self._last_sync_time = now

        # 2. Get current balance
        if self._get_balance:
            self._balance = await self._get_balance()

        # 3. Check if we can trade at all
        can_trade, reason = self._risk_manager.can_trade(self._balance)
        if not can_trade:
            logger.info(f"Trading paused: {reason}")
            return

        # 4. Get markets to analyze
        if not self._get_markets:
            return

        markets = await self._get_markets()
        if not markets:
            logger.debug("No markets to analyze")
            return

        # 5. Run strategy analysis
        await self._analyze_markets(markets)

    async def _analyze_markets(self, markets: List[Dict]) -> None:
        """
        Analyze markets and execute trades.

        Priority:
        1. Check for arbitrage first (risk-free)
        2. Run AI edge detection
        """
        for market in markets:
            market_id = market.get("id") or market.get("market_id")
            if not market_id:
                continue

            # Priority 1: Check arbitrage
            if self._config.arbitrage.enabled:
                arb_result = await self._check_arbitrage(market_id)
                if arb_result:
                    continue  # Skip other strategies if arb found

            # Priority 2: Run single-book strategies
            await self._run_single_strategies(market)

    async def _check_arbitrage(self, market_id: str) -> bool:
        """
        Check for arbitrage opportunity.

        Returns True if arbitrage was found and executed.
        """
        if not self._get_dual_book:
            return False

        try:
            dual_book = await self._get_dual_book(market_id)
            if not dual_book.is_complete:
                return False

            # Run arbitrage strategies
            arb_intents = self._strategy_manager.analyze_dual_all(dual_book)

            for yes_intent, no_intent in arb_intents:
                self._stats.arbitrage_opportunities += 1

                # Validate through risk manager
                risk_result = self._risk_manager.validate_arbitrage(
                    market_id=market_id,
                    yes_price=yes_intent.price,
                    no_price=no_intent.price,
                    size=yes_intent.size,
                    balance=self._balance,
                )

                if not risk_result.approved:
                    logger.info(f"Arbitrage rejected: {risk_result.reason}")
                    self._stats.intents_rejected += 2
                    continue

                # Execute both legs
                yes_result, no_result = await self._executor.execute_pair(
                    yes_intent, no_intent
                )

                self._stats.intents_approved += 2
                if yes_result.success:
                    self._stats.orders_executed += 1
                else:
                    self._stats.orders_failed += 1
                if no_result.success:
                    self._stats.orders_executed += 1
                else:
                    self._stats.orders_failed += 1

                return True  # Arbitrage found

        except Exception as e:
            logger.error(f"Arbitrage check error: {e}")

        return False

    async def _run_single_strategies(self, market: Dict) -> None:
        """Run single-book strategies on a market."""
        market_id = market.get("id") or market.get("market_id")
        market_type = market.get("market_type", "other")

        if not self._get_orderbook:
            return

        try:
            # Get orderbook for YES side (primary)
            orderbook = await self._get_orderbook(market_id)

            # Run all strategies
            intents = self._strategy_manager.analyze_all(orderbook)
            self._stats.intents_generated += len(intents)

            for intent in intents:
                # Validate through risk manager
                risk_result = self._risk_manager.validate_intent(
                    market_id=market_id,
                    market_type=market_type,
                    side=intent.side,
                    price=intent.price,
                    size=intent.size,
                    balance=self._balance,
                    confidence=intent.confidence,
                )

                if not risk_result.approved:
                    logger.debug(f"Intent rejected: {risk_result.reason}")
                    self._stats.intents_rejected += 1
                    continue

                # Adjust size if needed
                if risk_result.adjusted_size:
                    intent = self._adjust_intent_size(intent, risk_result.adjusted_size)

                # Execute
                self._stats.intents_approved += 1
                result = await self._executor.execute(intent)

                if result.success:
                    self._stats.orders_executed += 1
                    logger.info(
                        f"ORDER EXECUTED: {intent.side} {result.fill_size} "
                        f"@ {result.fill_price} | {intent.strategy_name}"
                    )

                    if self._discord:
                        try:
                            self._discord.alert_trade(
                                side=intent.side,
                                size=float(result.fill_size),
                                price=float(result.fill_price),
                                market=market.get("question", market_id)[:50],
                                strategy=intent.strategy_name,
                            )
                        except:
                            pass
                else:
                    self._stats.orders_failed += 1
                    logger.error(f"Order failed: {result.error}")

        except Exception as e:
            logger.error(f"Strategy error on {market_id}: {e}")

    def _adjust_intent_size(
        self,
        intent: StrategyIntent,
        new_size: Decimal,
    ) -> StrategyIntent:
        """Create new intent with adjusted size."""
        return StrategyIntent(
            market_id=intent.market_id,
            token_id=intent.token_id,
            outcome=intent.outcome,
            side=intent.side,
            price=intent.price,
            size=new_size,
            reason=f"{intent.reason} (size adjusted)",
            strategy_name=intent.strategy_name,
            confidence=intent.confidence,
            timestamp=intent.timestamp,
            metadata=intent.metadata,
        )

    def stop(self) -> None:
        """Stop the runner."""
        self._running = False
        logger.info("Stop requested")

    def get_status(self) -> Dict[str, Any]:
        """Get runner status."""
        return {
            "running": self._running,
            "config": {
                "dry_run": self._config.execution.dry_run,
                "bankroll": float(self._config.bankroll),
            },
            "stats": self._stats.to_dict(),
            "risk": self._risk_manager.get_status() if self._risk_manager else {},
            "executor": self._executor.get_status() if self._executor else {},
            "strategies": [
                {"name": s.name, "enabled": s.enabled}
                for s in self._strategy_manager.strategies
            ],
        }

    def update_edge_data(self, edge_by_type: Dict[str, Decimal]) -> None:
        """Update edge detection data."""
        if self._risk_manager:
            self._risk_manager.update_edge_data(edge_by_type)

        # Also update learning strategies
        for strategy in self._strategy_manager.strategies:
            if hasattr(strategy, 'update_edge_data'):
                strategy.update_edge_data(edge_by_type)
