"""
Hybrid Trading Bot

Combines AI-driven edge detection from Learning Autonomous Trader
with professional architecture from PolyAgentVPS.

Components:
- config: Validated configuration dataclasses
- risk: Risk management with position limits and edge filtering
- strategies: Trading strategies (AI edge, arbitrage)
- execution: Order execution with idempotency
- runner: Main orchestrator
"""

from agents.hybrid.config import (
    HybridConfig,
    RiskLimits,
    LearningConfig,
    KellySizingConfig,
    ArbitrageConfig,
    MarketMakingConfig,
    ExecutionConfig,
    AlertConfig,
    get_default_config,
    get_aggressive_config,
    get_conservative_config,
)
from agents.hybrid.runner import HybridRunner, RunnerStats
from agents.hybrid.strategies.base import (
    BaseStrategy,
    LearningStrategy,
    StrategyManager,
    StrategyIntent,
    OrderBook,
    DualOrderBook,
)
from agents.hybrid.risk.manager import RiskManager, RiskCheckResult
from agents.hybrid.execution.executor import OrderExecutor, ExecutionResult

__version__ = "1.0.0"
__all__ = [
    # Config
    "HybridConfig",
    "RiskLimits",
    "LearningConfig",
    "KellySizingConfig",
    "ArbitrageConfig",
    "MarketMakingConfig",
    "ExecutionConfig",
    "AlertConfig",
    "get_default_config",
    "get_aggressive_config",
    "get_conservative_config",
    # Runner
    "HybridRunner",
    "RunnerStats",
    # Strategies
    "BaseStrategy",
    "LearningStrategy",
    "StrategyManager",
    "StrategyIntent",
    "OrderBook",
    "DualOrderBook",
    # Risk
    "RiskManager",
    "RiskCheckResult",
    # Execution
    "OrderExecutor",
    "ExecutionResult",
]
