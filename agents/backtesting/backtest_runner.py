#!/usr/bin/env python3
"""
Backtest Runner - Main backtesting engine

Simulates trading bot on historical data to validate edge before live trading.

Key features:
1. Replay historical markets through bot logic
2. Simulate LLM predictions (cached or simplified)
3. Test different exit strategies
4. Calculate comprehensive performance metrics
5. Generate detailed reports
"""

import os
import sys
import json
import argparse
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from agents.backtesting.historical_data import HistoricalDataFetcher, MarketSnapshot
from agents.backtesting.metrics import PerformanceMetrics, Trade
from agents.backtesting.report_generator import ReportGenerator


@dataclass
class BacktestConfig:
    """Backtest configuration"""
    start_date: datetime
    end_date: datetime
    initial_capital: float
    strategy: str  # 'ai-prediction', 'simple-momentum', 'mean-reversion'
    exit_strategy: str  # 'hold-to-resolution', 'take-profit-10', 'stop-loss-10', etc.
    min_confidence: float
    max_position_size: float
    fee_rate: float  # 2% on winnings
    use_llm: bool  # If False, use simplified decision logic


class BacktestRunner:
    """
    Main backtesting engine

    Simulates trading bot execution on historical data
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.data_fetcher = HistoricalDataFetcher()
        self.metrics_calculator = PerformanceMetrics(
            initial_capital=config.initial_capital
        )
        self.report_generator = ReportGenerator()

        # State tracking
        self.current_capital = config.initial_capital
        self.open_positions: List[Dict] = []
        self.closed_trades: List[Trade] = []
        self.opportunities_found = 0

        print("=" * 80)
        print("POLYMARKET BOT BACKTESTING")
        print("=" * 80)
        print(f"Strategy: {config.strategy}")
        print(f"Exit Strategy: {config.exit_strategy}")
        print(f"Date Range: {config.start_date.date()} to {config.end_date.date()}")
        print(f"Initial Capital: ${config.initial_capital:.2f}")
        print("=" * 80)
        print()

    def run(self) -> Dict:
        """
        Run complete backtest

        Returns:
            Dict with performance metrics and trade history
        """
        # Load or create historical data
        print("Loading historical data...")
        df = self._load_historical_data()

        if df is None or df.empty:
            print("ERROR: No historical data available")
            return self._empty_results()

        print(f"Loaded {len(df)} market snapshots")
        print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print()

        # Run simulation
        print("Running backtest simulation...")
        self._simulate_trading(df)

        print()
        print("=" * 80)
        print("BACKTEST COMPLETE")
        print("=" * 80)
        print(f"Opportunities Found: {self.opportunities_found}")
        print(f"Trades Executed: {len(self.closed_trades)}")
        print(f"Final Capital: ${self.current_capital:.2f}")
        print()

        # Calculate metrics
        total_days = (self.config.end_date - self.config.start_date).days
        performance_report = self.metrics_calculator.calculate_metrics(
            self.closed_trades,
            total_days
        )

        # Add opportunity metrics
        performance_report.opportunities_found = self.opportunities_found
        performance_report.opportunity_conversion_rate = (
            len(self.closed_trades) / self.opportunities_found
            if self.opportunities_found > 0 else 0.0
        )

        # Generate report
        report_path = self.report_generator.generate_html_report(
            performance_report,
            self.closed_trades,
            self.config
        )

        print(f"Report generated: {report_path}")
        print()

        return {
            'performance': performance_report,
            'trades': self.closed_trades,
            'report_path': report_path
        }

    def _load_historical_data(self) -> Optional[pd.DataFrame]:
        """Load historical market data"""
        data_file = "synthetic_historical_data.parquet"
        data_path = self.data_fetcher.data_dir / data_file

        # Check if data exists
        if not data_path.exists():
            print(f"No historical data found at {data_path}")
            print("Creating synthetic data for testing...")

            # Create synthetic data
            days = (self.config.end_date - self.config.start_date).days
            df = self.data_fetcher.create_synthetic_data(
                num_markets=20,
                days=days
            )

            # Save for future use
            snapshots = []
            for _, row in df.iterrows():
                snapshot = MarketSnapshot(**row.to_dict())
                snapshots.append(snapshot)

            self.data_fetcher.save_snapshots_to_parquet(snapshots, data_file)

            return df

        # Load existing data
        return self.data_fetcher.load_snapshots_from_parquet(data_file)

    def _simulate_trading(self, df: pd.DataFrame):
        """
        Simulate trading on historical data

        This is the core backtest logic that:
        1. Iterates through time
        2. Evaluates markets at each point
        3. Makes entry/exit decisions
        4. Tracks PnL
        """
        # Sort by timestamp
        df = df.sort_values('timestamp')

        # Group by market
        markets = df.groupby('market_slug')

        for market_slug, market_df in markets:
            market_df = market_df.sort_values('timestamp')

            # Simulate this market's lifecycle
            self._simulate_market(market_slug, market_df)

        # Close any remaining open positions at end
        self._close_remaining_positions()

    def _simulate_market(self, market_slug: str, market_df: pd.DataFrame):
        """
        Simulate trading for a single market

        Evaluates at each time point whether to enter/exit
        """
        for idx, row in market_df.iterrows():
            current_time = row['timestamp']

            # Check if we should enter a position
            if not self._has_open_position(market_slug):
                should_enter, confidence = self._evaluate_entry(row)

                if should_enter:
                    self.opportunities_found += 1
                    self._enter_position(row, confidence)

            # Check if we should exit existing position
            else:
                should_exit, reason = self._evaluate_exit(row, market_slug)

                if should_exit:
                    self._exit_position(row, market_slug, reason)

    def _evaluate_entry(self, market_snapshot: pd.Series) -> Tuple[bool, float]:
        """
        Decide if we should enter a position

        Returns:
            (should_enter, confidence)
        """
        if self.config.strategy == 'ai-prediction':
            return self._ai_prediction_strategy(market_snapshot)
        elif self.config.strategy == 'simple-momentum':
            return self._momentum_strategy(market_snapshot)
        elif self.config.strategy == 'mean-reversion':
            return self._mean_reversion_strategy(market_snapshot)
        else:
            return False, 0.0

    def _ai_prediction_strategy(self, snapshot: pd.Series) -> Tuple[bool, float]:
        """
        Simulate AI prediction strategy

        In real backtest, this would:
        1. Use cached LLM responses (if available)
        2. Or use simplified heuristics
        3. Or skip if use_llm=False
        """
        if self.config.use_llm:
            # TODO: Implement LLM simulation
            # For now, use simplified logic
            pass

        # Simplified heuristic: Look for mispriced markets
        mid_price = snapshot['mid_price']

        # Avoid extreme prices (low information content)
        if mid_price < 0.05 or mid_price > 0.95:
            return False, 0.0

        # Look for asymmetric opportunities
        # If price is low but volume is high, might be undervalued
        if mid_price < 0.30 and snapshot['volume_24h'] > 1000:
            confidence = 0.50 + (0.30 - mid_price) * 0.5
            return True, confidence

        # If price is high but dropping, might be overvalued
        if mid_price > 0.70 and snapshot['volume_24h'] > 1000:
            confidence = 0.50 + (mid_price - 0.70) * 0.5
            return True, confidence

        return False, 0.0

    def _momentum_strategy(self, snapshot: pd.Series) -> Tuple[bool, float]:
        """Simple momentum strategy"""
        # Buy if price is rising (would need price history)
        # For now, random entry for testing
        import random
        if random.random() > 0.7:  # 30% entry rate
            return True, 0.6
        return False, 0.0

    def _mean_reversion_strategy(self, snapshot: pd.Series) -> Tuple[bool, float]:
        """Simple mean reversion strategy"""
        # Buy when price deviates from 0.5
        mid_price = snapshot['mid_price']
        deviation = abs(mid_price - 0.5)

        if deviation > 0.2:  # Significant deviation
            confidence = 0.5 + deviation
            return True, confidence

        return False, 0.0

    def _evaluate_exit(
        self,
        market_snapshot: pd.Series,
        market_slug: str
    ) -> Tuple[bool, str]:
        """
        Decide if we should exit an open position

        Returns:
            (should_exit, reason)
        """
        position = self._get_open_position(market_slug)
        if not position:
            return False, ""

        current_price = market_snapshot['mid_price']
        entry_price = position['entry_price']

        # Calculate current PnL
        pnl_pct = ((current_price - entry_price) / entry_price) * 100

        # Check exit strategy
        if self.config.exit_strategy == 'hold-to-resolution':
            # Only exit when market resolves
            if market_snapshot['is_resolved']:
                return True, "market_resolved"

        elif self.config.exit_strategy.startswith('take-profit-'):
            target_pct = float(self.config.exit_strategy.split('-')[-1])
            if pnl_pct >= target_pct:
                return True, f"take_profit_{target_pct}%"

        elif self.config.exit_strategy.startswith('stop-loss-'):
            stop_pct = float(self.config.exit_strategy.split('-')[-1])
            if pnl_pct <= -stop_pct:
                return True, f"stop_loss_{stop_pct}%"

        elif self.config.exit_strategy.startswith('time-'):
            # Exit after X hours
            hours = float(self.config.exit_strategy.split('-')[-1].replace('h', ''))
            hold_time = (market_snapshot['timestamp'] - position['entry_time']).total_seconds() / 3600

            if hold_time >= hours:
                return True, f"time_exit_{hours}h"

        # Always exit if resolved
        if market_snapshot['is_resolved']:
            return True, "market_resolved"

        return False, ""

    def _enter_position(self, market_snapshot: pd.Series, confidence: float):
        """Enter a new position"""
        # Check if we have enough capital
        if self.current_capital < 1.0:
            return

        # Calculate position size (for now, use fixed size)
        position_size = min(
            self.config.max_position_size,
            self.current_capital * 0.1  # Max 10% per position
        )

        # Only enter if confidence is high enough
        if confidence < self.config.min_confidence:
            return

        position = {
            'market_slug': market_snapshot['market_slug'],
            'token_id': market_snapshot['token_id'],
            'entry_time': market_snapshot['timestamp'],
            'entry_price': market_snapshot['mid_price'],
            'position_size': position_size,
            'confidence': confidence
        }

        self.open_positions.append(position)
        self.current_capital -= position_size

        print(f"[ENTER] {market_snapshot['market_slug'][:30]} @ ${market_snapshot['mid_price']:.3f} "
              f"size=${position_size:.2f} conf={confidence:.1%}")

    def _exit_position(
        self,
        market_snapshot: pd.Series,
        market_slug: str,
        reason: str
    ):
        """Exit an open position"""
        position = self._get_open_position(market_slug)
        if not position:
            return

        # Remove from open positions
        self.open_positions.remove(position)

        # Calculate PnL
        entry_price = position['entry_price']
        exit_price = market_snapshot['mid_price']

        # Determine if win or loss based on resolution
        if market_snapshot['is_resolved']:
            # Use actual resolution outcome
            winning_outcome = market_snapshot['winning_outcome']
            our_outcome = market_snapshot['outcome']

            if winning_outcome == our_outcome:
                # We won - get full payout
                exit_price = 1.0
            else:
                # We lost - get nothing
                exit_price = 0.0

        position_size = position['position_size']
        shares = position_size / entry_price
        exit_value = shares * exit_price

        pnl = exit_value - position_size
        pnl_pct = (pnl / position_size) * 100 if position_size > 0 else 0.0

        # Calculate fees (2% on winnings only)
        fees = 0.0
        if pnl > 0:
            fees = pnl * self.config.fee_rate

        net_pnl = pnl - fees

        # Update capital
        self.current_capital += exit_value - fees

        # Hold duration
        hold_duration = (market_snapshot['timestamp'] - position['entry_time']).total_seconds() / 3600

        # Create trade record
        trade = Trade(
            timestamp=market_snapshot['timestamp'].isoformat(),
            market_slug=market_slug,
            entry_price=entry_price,
            exit_price=exit_price,
            position_size=position_size,
            outcome='win' if pnl > 0 else 'loss',
            pnl=net_pnl,
            pnl_pct=pnl_pct,
            hold_duration_hours=hold_duration,
            confidence=position['confidence'],
            fees=fees
        )

        self.closed_trades.append(trade)

        print(f"[EXIT] {market_slug[:30]} @ ${exit_price:.3f} "
              f"PnL=${net_pnl:+.2f} ({pnl_pct:+.1f}%) reason={reason}")

    def _has_open_position(self, market_slug: str) -> bool:
        """Check if we have an open position in this market"""
        return any(p['market_slug'] == market_slug for p in self.open_positions)

    def _get_open_position(self, market_slug: str) -> Optional[Dict]:
        """Get open position for a market"""
        for position in self.open_positions:
            if position['market_slug'] == market_slug:
                return position
        return None

    def _close_remaining_positions(self):
        """Force close any remaining open positions at end of backtest"""
        for position in self.open_positions[:]:  # Copy list to avoid modification during iteration
            print(f"[FORCE CLOSE] {position['market_slug']} - backtest ended")

            # Create dummy snapshot for exit
            dummy_snapshot = pd.Series({
                'timestamp': self.config.end_date,
                'market_slug': position['market_slug'],
                'token_id': position['token_id'],
                'mid_price': position['entry_price'],  # Exit at entry (no profit)
                'is_resolved': False,
                'winning_outcome': None,
                'outcome': None
            })

            self._exit_position(dummy_snapshot, position['market_slug'], 'backtest_end')

    def _empty_results(self) -> Dict:
        """Return empty results if backtest fails"""
        return {
            'performance': None,
            'trades': [],
            'report_path': None
        }


def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Backtest Polymarket trading bot'
    )

    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='Start date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='End date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--strategy',
        type=str,
        default='ai-prediction',
        choices=['ai-prediction', 'simple-momentum', 'mean-reversion'],
        help='Trading strategy to test'
    )

    parser.add_argument(
        '--exit-strategy',
        type=str,
        default='hold-to-resolution',
        help='Exit strategy (hold-to-resolution, take-profit-20, stop-loss-10, time-24h)'
    )

    parser.add_argument(
        '--initial-capital',
        type=float,
        default=100.0,
        help='Initial capital in USDC'
    )

    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.2,
        help='Minimum confidence to enter trade'
    )

    parser.add_argument(
        '--max-position-size',
        type=float,
        default=2.0,
        help='Maximum position size in USDC'
    )

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d').replace(tzinfo=timezone.utc)

    # Create config
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.initial_capital,
        strategy=args.strategy,
        exit_strategy=args.exit_strategy,
        min_confidence=args.min_confidence,
        max_position_size=args.max_position_size,
        fee_rate=0.02,  # 2% on winnings
        use_llm=False  # Use simplified logic for now
    )

    # Run backtest
    runner = BacktestRunner(config)
    results = runner.run()

    # Print summary
    if results['performance']:
        perf = results['performance']
        print("PERFORMANCE SUMMARY")
        print("=" * 80)
        print(f"Win Rate: {perf.win_rate:.1%}")
        print(f"Total PnL: ${perf.net_pnl:+.2f}")
        print(f"Total Return: {perf.total_return_pct:+.1f}%")
        print(f"Sharpe Ratio: {perf.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {perf.max_drawdown_pct:.1f}%")
        print(f"Profit Factor: {perf.profit_factor:.2f}")
        print()

        # Edge detection
        if perf.net_pnl > 0 and perf.sharpe_ratio > 0.5:
            print("✅ BOT SHOWS POSITIVE EDGE")
        else:
            print("❌ BOT DOES NOT SHOW POSITIVE EDGE")
            print("   Consider improving strategy before live trading!")


if __name__ == "__main__":
    main()
