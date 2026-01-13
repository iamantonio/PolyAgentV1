"""
Trading Strategies for Hybrid Bot

Strategies produce intents, not orders. Intents are validated
by the RiskManager before execution.

Available strategies:
- BinaryArbitrageStrategy: Risk-free arbitrage on binary markets
- AIEdgeStrategy: AI-powered edge detection with Kelly sizing
"""

from agents.hybrid.strategies.base import (
    BaseStrategy,
    LearningStrategy,
    StrategyManager,
    StrategyIntent,
    OrderBook,
    DualOrderBook,
)
from agents.hybrid.strategies.arbitrage import (
    BinaryArbitrageStrategy,
    create_arbitrage_strategy,
)
from agents.hybrid.strategies.ai_edge import (
    AIEdgeStrategy,
    MarketAnalysis,
    create_ai_edge_strategy,
)

__all__ = [
    # Base
    "BaseStrategy",
    "LearningStrategy",
    "StrategyManager",
    "StrategyIntent",
    "OrderBook",
    "DualOrderBook",
    # Arbitrage
    "BinaryArbitrageStrategy",
    "create_arbitrage_strategy",
    # AI Edge
    "AIEdgeStrategy",
    "MarketAnalysis",
    "create_ai_edge_strategy",
]
