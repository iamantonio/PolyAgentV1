"""
Backtesting Framework for Polymarket Trading Bot

This module provides comprehensive backtesting capabilities to validate
if the trading bot has positive edge before risking real capital.
"""

from .backtest_runner import BacktestRunner
from .historical_data import HistoricalDataFetcher
from .metrics import PerformanceMetrics
from .report_generator import ReportGenerator

__all__ = [
    'BacktestRunner',
    'HistoricalDataFetcher',
    'PerformanceMetrics',
    'ReportGenerator'
]
