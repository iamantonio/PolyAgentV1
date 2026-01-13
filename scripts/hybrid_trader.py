#!/usr/bin/env python3
"""
Hybrid Trading Bot - Main Entry Point

Combines AI-driven edge detection with professional arbitrage strategies.

Usage:
    python scripts/hybrid_trader.py [--dry-run] [--config CONFIG_FILE]

Examples:
    # Dry run with default config
    python scripts/hybrid_trader.py --dry-run

    # Live trading with aggressive config
    python scripts/hybrid_trader.py --aggressive

    # Conservative mode
    python scripts/hybrid_trader.py --conservative --dry-run
"""

import argparse
import asyncio
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.hybrid import (
    HybridRunner,
    HybridConfig,
    get_default_config,
    get_aggressive_config,
    get_conservative_config,
    OrderBook,
    DualOrderBook,
)
from agents.hybrid.strategies import (
    create_arbitrage_strategy,
    create_ai_edge_strategy,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class PolymarketBridge:
    """
    Bridge to Polymarket API.

    Wraps the py_clob_client for use with the hybrid bot.
    """

    def __init__(self, client: Any = None):
        self._client = client
        self._balance = Decimal("0")
        self._positions: Dict[str, Dict] = {}

    @classmethod
    def create(cls) -> "PolymarketBridge":
        """Create bridge with real Polymarket client."""
        try:
            from agents.polymarket.polymarket import PolymarketClient
            client = PolymarketClient()
            bridge = cls(client)
            logger.info("PolymarketBridge created with live client")
            return bridge
        except Exception as e:
            logger.warning(f"Failed to create Polymarket client: {e}")
            logger.info("Running in simulation mode")
            return cls(None)

    async def get_markets(self) -> List[Dict]:
        """Fetch available markets."""
        if self._client is None:
            return []

        try:
            # Use existing market fetching logic
            markets = self._client.fetch_markets()
            return markets or []
        except Exception as e:
            logger.error(f"Failed to fetch markets: {e}")
            return []

    async def get_orderbook(self, market_id: str) -> OrderBook:
        """Fetch orderbook for a market."""
        if self._client is None:
            return self._empty_orderbook(market_id)

        try:
            book = self._client.get_orderbook(market_id)
            return self._convert_orderbook(market_id, book, "YES")
        except Exception as e:
            logger.error(f"Failed to fetch orderbook for {market_id}: {e}")
            return self._empty_orderbook(market_id)

    async def get_dual_book(self, market_id: str) -> DualOrderBook:
        """Fetch both YES and NO orderbooks."""
        if self._client is None:
            return DualOrderBook(market_id=market_id)

        try:
            # Get both sides
            yes_book = await self.get_orderbook(market_id)

            # For NO side, we need the complementary token
            no_token_id = self._get_no_token_id(market_id)
            if no_token_id:
                no_raw = self._client.get_orderbook(no_token_id)
                no_book = self._convert_orderbook(market_id, no_raw, "NO")
            else:
                no_book = None

            return DualOrderBook(
                market_id=market_id,
                yes_book=yes_book,
                no_book=no_book,
            )
        except Exception as e:
            logger.error(f"Failed to fetch dual book for {market_id}: {e}")
            return DualOrderBook(market_id=market_id)

    async def get_balance(self) -> Decimal:
        """Fetch current USDC balance."""
        if self._client is None:
            return Decimal("100")  # Simulation balance

        try:
            balance = self._client.get_balance()
            self._balance = Decimal(str(balance))
            return self._balance
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return self._balance

    async def sync_positions(self) -> None:
        """Sync positions with chain."""
        if self._client is None:
            return

        try:
            if hasattr(self._client, 'sync_positions'):
                self._client.sync_positions()
            logger.info("Positions synced with chain")
        except Exception as e:
            logger.error(f"Failed to sync positions: {e}")

    def get_daily_pnl(self) -> Decimal:
        """Get today's P&L."""
        # Would integrate with the learning system's P&L tracking
        return Decimal("0")

    def get_open_positions(self) -> List[Dict]:
        """Get current open positions."""
        return list(self._positions.values())

    def get_position_value(self, market_id: str) -> Decimal:
        """Get position value for a market."""
        pos = self._positions.get(market_id, {})
        return Decimal(str(pos.get("value", 0)))

    def _convert_orderbook(
        self,
        market_id: str,
        raw_book: Dict,
        outcome: str,
    ) -> OrderBook:
        """Convert raw orderbook to OrderBook dataclass."""
        bids = []
        asks = []

        for bid in raw_book.get("bids", []):
            price = Decimal(str(bid.get("price", 0)))
            size = Decimal(str(bid.get("size", 0)))
            bids.append((price, size))

        for ask in raw_book.get("asks", []):
            price = Decimal(str(ask.get("price", 0)))
            size = Decimal(str(ask.get("size", 0)))
            asks.append((price, size))

        # Sort: bids descending (best bid first), asks ascending (best ask first)
        bids.sort(key=lambda x: x[0], reverse=True)
        asks.sort(key=lambda x: x[0])

        return OrderBook(
            market_id=market_id,
            token_id=raw_book.get("token_id", market_id),
            outcome=outcome,
            bids=bids,
            asks=asks,
        )

    def _empty_orderbook(self, market_id: str) -> OrderBook:
        """Create empty orderbook."""
        return OrderBook(
            market_id=market_id,
            token_id=market_id,
            outcome="YES",
            bids=[],
            asks=[],
        )

    def _get_no_token_id(self, market_id: str) -> Optional[str]:
        """Get NO token ID for a market."""
        # This would look up the complementary token
        # Implementation depends on market data structure
        return None


def create_discord_alerter() -> Optional[Any]:
    """Create Discord alerter if configured."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        logger.info("Discord alerts disabled (no webhook URL)")
        return None

    try:
        from agents.polymarket.discord_alerts import DiscordAlerter
        alerter = DiscordAlerter(webhook_url)
        logger.info("Discord alerts enabled")
        return alerter
    except ImportError:
        logger.warning("Discord alerter not available")
        return None


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Hybrid Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no real orders)",
    )

    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="Use aggressive configuration",
    )

    parser.add_argument(
        "--conservative",
        action="store_true",
        help="Use conservative configuration",
    )

    parser.add_argument(
        "--bankroll",
        type=float,
        default=None,
        help="Override bankroll amount",
    )

    parser.add_argument(
        "--loop-delay",
        type=float,
        default=60.0,
        help="Seconds between iterations (default: 60)",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum iterations (default: infinite)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )

    parser.add_argument(
        "--no-arbitrage",
        action="store_true",
        help="Disable arbitrage strategy",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI edge strategy",
    )

    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Select configuration
    if args.aggressive:
        config = get_aggressive_config()
        logger.info("Using AGGRESSIVE configuration")
    elif args.conservative:
        config = get_conservative_config()
        logger.info("Using CONSERVATIVE configuration")
    else:
        config = get_default_config()
        logger.info("Using DEFAULT configuration")

    # Override dry-run if specified
    if args.dry_run:
        # Create new config with dry_run enabled
        from dataclasses import replace
        new_execution = replace(config.execution, dry_run=True)
        config = replace(config, execution=new_execution)
        logger.info("DRY-RUN mode enabled")

    # Override bankroll if specified
    if args.bankroll:
        from dataclasses import replace
        config = replace(config, bankroll=Decimal(str(args.bankroll)))
        logger.info(f"Bankroll set to ${args.bankroll}")

    # Create bridge
    bridge = PolymarketBridge.create()

    # Create alerter
    alerter = create_discord_alerter()

    # Create strategies
    strategies = []

    if not args.no_arbitrage:
        arb_strategy = create_arbitrage_strategy(config.arbitrage)
        strategies.append(arb_strategy)
        logger.info("Arbitrage strategy enabled")

    if not args.no_ai:
        ai_strategy = create_ai_edge_strategy(
            learning_config=config.learning,
            kelly_config=config.kelly,
            bankroll=config.bankroll,
        )
        strategies.append(ai_strategy)
        logger.info("AI Edge strategy enabled")

    if not strategies:
        logger.error("No strategies enabled! Enable at least one strategy.")
        return 1

    # Create runner
    runner = HybridRunner(
        config=config,
        polymarket_client=bridge._client,
        discord_alerter=alerter,
    )

    # Setup runner with callbacks
    runner.setup(
        strategies=strategies,
        get_markets=bridge.get_markets,
        get_orderbook=bridge.get_orderbook,
        get_dual_book=bridge.get_dual_book,
        get_balance=bridge.get_balance,
        sync_positions=bridge.sync_positions,
        get_daily_pnl=bridge.get_daily_pnl,
        get_open_positions=bridge.get_open_positions,
        get_position_value=bridge.get_position_value,
    )

    # Run
    logger.info("=" * 60)
    logger.info("HYBRID TRADING BOT STARTING")
    logger.info("=" * 60)

    try:
        await runner.run(
            loop_delay=args.loop_delay,
            max_iterations=args.max_iterations,
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        runner.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    # Print final status
    status = runner.get_status()
    logger.info("=" * 60)
    logger.info("FINAL STATUS")
    logger.info("=" * 60)
    logger.info(f"Iterations: {status['stats']['iterations']}")
    logger.info(f"Intents generated: {status['stats']['intents_generated']}")
    logger.info(f"Intents approved: {status['stats']['intents_approved']}")
    logger.info(f"Orders executed: {status['stats']['orders_executed']}")
    logger.info(f"Errors: {status['stats']['errors']}")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
