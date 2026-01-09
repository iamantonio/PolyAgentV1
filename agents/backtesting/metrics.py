#!/usr/bin/env python3
"""
Performance Metrics Calculator

Calculates comprehensive trading performance metrics for backtesting:
- Win rate
- Average profit/loss
- Sharpe ratio
- Maximum drawdown
- Total returns
- Risk-adjusted metrics
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Trade:
    """Single trade record"""
    timestamp: str
    market_slug: str
    entry_price: float
    exit_price: float
    position_size: float
    outcome: str  # 'win' or 'loss'
    pnl: float
    pnl_pct: float
    hold_duration_hours: float
    confidence: float
    fees: float


@dataclass
class PerformanceReport:
    """Complete performance metrics"""
    # Basic metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    # PnL metrics
    total_pnl: float
    avg_pnl_per_trade: float
    avg_win: float
    avg_loss: float
    profit_factor: float  # Total wins / Total losses

    # Risk metrics
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_pct: float

    # Returns
    total_return_pct: float
    annualized_return_pct: float

    # Trading stats
    avg_hold_duration_hours: float
    trades_per_day: float

    # Cost analysis
    total_fees: float
    avg_fee_per_trade: float
    net_pnl: float  # After fees

    # Opportunity metrics
    opportunities_found: int
    opportunities_taken: int
    opportunity_conversion_rate: float


class PerformanceMetrics:
    """
    Calculate comprehensive trading performance metrics
    """

    def __init__(self, initial_capital: float = 100.0, risk_free_rate: float = 0.04):
        """
        Args:
            initial_capital: Starting capital in USDC
            risk_free_rate: Annual risk-free rate for Sharpe calculation (default 4%)
        """
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate

    def calculate_metrics(
        self,
        trades: List[Trade],
        total_days: int
    ) -> PerformanceReport:
        """
        Calculate all performance metrics from trade history
        """
        if not trades:
            return self._empty_report()

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame([asdict(t) for t in trades])
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Basic counts
        total_trades = len(trades)
        winning_trades = len(df[df['pnl'] > 0])
        losing_trades = len(df[df['pnl'] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        # PnL metrics
        total_pnl = df['pnl'].sum()
        avg_pnl = df['pnl'].mean()
        avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0.0
        avg_loss = df[df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0.0

        total_wins = df[df['pnl'] > 0]['pnl'].sum()
        total_losses = abs(df[df['pnl'] < 0]['pnl'].sum())
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        # Risk-adjusted metrics
        sharpe = self._calculate_sharpe_ratio(df['pnl_pct'].values, total_days)
        sortino = self._calculate_sortino_ratio(df['pnl_pct'].values, total_days)
        max_dd, max_dd_pct = self._calculate_max_drawdown(df['pnl'].values, self.initial_capital)

        # Returns
        total_return_pct = (total_pnl / self.initial_capital) * 100
        annualized_return = self._annualize_return(total_return_pct, total_days)

        # Trading stats
        avg_hold_duration = df['hold_duration_hours'].mean()
        trades_per_day = total_trades / max(total_days, 1)

        # Fees
        total_fees = df['fees'].sum()
        avg_fee = df['fees'].mean()
        net_pnl = total_pnl - total_fees

        return PerformanceReport(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl_per_trade=avg_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            total_return_pct=total_return_pct,
            annualized_return_pct=annualized_return,
            avg_hold_duration_hours=avg_hold_duration,
            trades_per_day=trades_per_day,
            total_fees=total_fees,
            avg_fee_per_trade=avg_fee,
            net_pnl=net_pnl,
            opportunities_found=0,  # Set by backtest runner
            opportunities_taken=total_trades,
            opportunity_conversion_rate=0.0  # Set by backtest runner
        )

    def _calculate_sharpe_ratio(
        self,
        returns: np.ndarray,
        total_days: int
    ) -> float:
        """
        Calculate Sharpe Ratio (risk-adjusted return)

        Sharpe = (Mean Return - Risk Free Rate) / Std Dev of Returns
        """
        if len(returns) < 2:
            return 0.0

        # Annualize returns
        mean_return = np.mean(returns) * (365 / total_days) if total_days > 0 else 0
        std_return = np.std(returns) * np.sqrt(365 / total_days) if total_days > 0 else 0

        if std_return == 0:
            return 0.0

        sharpe = (mean_return - self.risk_free_rate) / std_return
        return sharpe

    def _calculate_sortino_ratio(
        self,
        returns: np.ndarray,
        total_days: int
    ) -> float:
        """
        Calculate Sortino Ratio (like Sharpe but only penalizes downside volatility)

        Better metric than Sharpe for asymmetric returns.
        """
        if len(returns) < 2:
            return 0.0

        # Only look at negative returns (downside deviation)
        downside_returns = returns[returns < 0]

        if len(downside_returns) == 0:
            return float('inf')  # No downside risk

        mean_return = np.mean(returns) * (365 / total_days) if total_days > 0 else 0
        downside_std = np.std(downside_returns) * np.sqrt(365 / total_days) if total_days > 0 else 0

        if downside_std == 0:
            return 0.0

        sortino = (mean_return - self.risk_free_rate) / downside_std
        return sortino

    def _calculate_max_drawdown(
        self,
        pnls: np.ndarray,
        initial_capital: float
    ) -> Tuple[float, float]:
        """
        Calculate maximum drawdown (largest peak-to-trough decline)

        Returns:
            (max_drawdown_dollars, max_drawdown_percent)
        """
        # Calculate cumulative equity curve
        equity = initial_capital + np.cumsum(pnls)

        # Calculate running maximum
        running_max = np.maximum.accumulate(equity)

        # Calculate drawdown at each point
        drawdown = running_max - equity

        # Find maximum drawdown
        max_dd = np.max(drawdown)
        max_dd_pct = (max_dd / initial_capital) * 100 if initial_capital > 0 else 0.0

        return max_dd, max_dd_pct

    def _annualize_return(
        self,
        total_return_pct: float,
        total_days: int
    ) -> float:
        """Convert total return to annualized return"""
        if total_days <= 0:
            return 0.0

        # Compound annual growth rate (CAGR)
        years = total_days / 365
        cagr = (((1 + total_return_pct / 100) ** (1 / years)) - 1) * 100

        return cagr

    def _empty_report(self) -> PerformanceReport:
        """Return empty performance report"""
        return PerformanceReport(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_pnl_per_trade=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            total_return_pct=0.0,
            annualized_return_pct=0.0,
            avg_hold_duration_hours=0.0,
            trades_per_day=0.0,
            total_fees=0.0,
            avg_fee_per_trade=0.0,
            net_pnl=0.0,
            opportunities_found=0,
            opportunities_taken=0,
            opportunity_conversion_rate=0.0
        )

    def compare_strategies(
        self,
        strategy_results: Dict[str, PerformanceReport]
    ) -> pd.DataFrame:
        """
        Compare multiple strategies side-by-side

        Args:
            strategy_results: Dict of strategy_name -> PerformanceReport

        Returns:
            DataFrame with comparison metrics
        """
        comparison = {}

        for strategy_name, report in strategy_results.items():
            comparison[strategy_name] = asdict(report)

        return pd.DataFrame(comparison).T

    def calculate_position_sizing_stats(
        self,
        trades: List[Trade]
    ) -> Dict:
        """Analyze position sizing behavior"""
        if not trades:
            return {}

        sizes = [t.position_size for t in trades]

        return {
            'avg_position_size': np.mean(sizes),
            'median_position_size': np.median(sizes),
            'min_position_size': np.min(sizes),
            'max_position_size': np.max(sizes),
            'std_position_size': np.std(sizes)
        }


if __name__ == "__main__":
    # Example usage
    metrics = PerformanceMetrics(initial_capital=100.0)

    # Sample trades
    trades = [
        Trade(
            timestamp="2025-01-01T12:00:00",
            market_slug="test-market-1",
            entry_price=0.50,
            exit_price=0.55,
            position_size=10.0,
            outcome="win",
            pnl=0.50,
            pnl_pct=5.0,
            hold_duration_hours=24.0,
            confidence=0.6,
            fees=0.01
        ),
        Trade(
            timestamp="2025-01-02T12:00:00",
            market_slug="test-market-2",
            entry_price=0.60,
            exit_price=0.55,
            position_size=10.0,
            outcome="loss",
            pnl=-0.50,
            pnl_pct=-5.0,
            hold_duration_hours=48.0,
            confidence=0.7,
            fees=0.01
        )
    ]

    report = metrics.calculate_metrics(trades, total_days=30)

    print("Performance Report:")
    print(f"Total Trades: {report.total_trades}")
    print(f"Win Rate: {report.win_rate:.1%}")
    print(f"Total PnL: ${report.total_pnl:.2f}")
    print(f"Sharpe Ratio: {report.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {report.max_drawdown_pct:.1f}%")
