#!/usr/bin/env python3
"""
Test backtesting framework

Validates that all components work correctly.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agents.backtesting import (
    HistoricalDataFetcher,
    PerformanceMetrics,
    BacktestRunner,
    ReportGenerator
)
from agents.backtesting.backtest_runner import BacktestConfig
from agents.backtesting.metrics import Trade


def test_historical_data_fetcher():
    """Test historical data fetching"""
    print("Testing HistoricalDataFetcher...")

    fetcher = HistoricalDataFetcher(data_dir="data/backtest_test")

    # Create synthetic data
    df = fetcher.create_synthetic_data(num_markets=5, days=30)

    assert len(df) > 0, "Should create synthetic data"
    assert 'timestamp' in df.columns, "Should have timestamp column"
    assert 'mid_price' in df.columns, "Should have mid_price column"

    print("✅ HistoricalDataFetcher works")


def test_performance_metrics():
    """Test performance metrics calculation"""
    print("\nTesting PerformanceMetrics...")

    metrics = PerformanceMetrics(initial_capital=100.0)

    # Create sample trades
    trades = [
        Trade(
            timestamp="2025-01-01T12:00:00",
            market_slug="test-1",
            entry_price=0.50,
            exit_price=0.60,
            position_size=10.0,
            outcome="win",
            pnl=2.0,
            pnl_pct=20.0,
            hold_duration_hours=24.0,
            confidence=0.6,
            fees=0.04
        ),
        Trade(
            timestamp="2025-01-02T12:00:00",
            market_slug="test-2",
            entry_price=0.60,
            exit_price=0.50,
            position_size=10.0,
            outcome="loss",
            pnl=-2.0,
            pnl_pct=-20.0,
            hold_duration_hours=24.0,
            confidence=0.7,
            fees=0.0
        ),
        Trade(
            timestamp="2025-01-03T12:00:00",
            market_slug="test-3",
            entry_price=0.55,
            exit_price=0.65,
            position_size=10.0,
            outcome="win",
            pnl=1.8,
            pnl_pct=18.0,
            hold_duration_hours=24.0,
            confidence=0.65,
            fees=0.036
        )
    ]

    report = metrics.calculate_metrics(trades, total_days=30)

    assert report.total_trades == 3, "Should count all trades"
    assert report.winning_trades == 2, "Should count winning trades"
    assert report.losing_trades == 1, "Should count losing trades"
    assert report.win_rate > 0.5, "Should have > 50% win rate"

    print(f"✅ PerformanceMetrics works")
    print(f"   Win Rate: {report.win_rate:.1%}")
    print(f"   Sharpe Ratio: {report.sharpe_ratio:.2f}")
    print(f"   Total PnL: ${report.total_pnl:.2f}")


def test_backtest_runner():
    """Test backtest runner"""
    print("\nTesting BacktestRunner...")

    config = BacktestConfig(
        start_date=datetime(2025, 10, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 11, 1, tzinfo=timezone.utc),
        initial_capital=100.0,
        strategy='ai-prediction',
        exit_strategy='hold-to-resolution',
        min_confidence=0.2,
        max_position_size=2.0,
        fee_rate=0.02,
        use_llm=False
    )

    runner = BacktestRunner(config)
    results = runner.run()

    assert results is not None, "Should return results"
    assert 'performance' in results, "Should have performance metrics"
    assert 'trades' in results, "Should have trade history"

    if results['performance']:
        perf = results['performance']
        print(f"✅ BacktestRunner works")
        print(f"   Trades: {perf.total_trades}")
        print(f"   Win Rate: {perf.win_rate:.1%}")
        print(f"   PnL: ${perf.net_pnl:+.2f}")


def test_report_generator():
    """Test report generation"""
    print("\nTesting ReportGenerator...")

    from agents.backtesting.metrics import PerformanceReport
    from dataclasses import dataclass

    @dataclass
    class DummyConfig:
        start_date = datetime(2025, 10, 1, tzinfo=timezone.utc)
        end_date = datetime(2025, 11, 1, tzinfo=timezone.utc)
        initial_capital = 100.0
        strategy = 'ai-prediction'
        exit_strategy = 'hold-to-resolution'
        min_confidence = 0.2
        max_position_size = 2.0
        fee_rate = 0.02

    performance = PerformanceReport(
        total_trades=10,
        winning_trades=6,
        losing_trades=4,
        win_rate=0.6,
        total_pnl=5.0,
        avg_pnl_per_trade=0.5,
        avg_win=1.25,
        avg_loss=-0.75,
        profit_factor=1.67,
        sharpe_ratio=1.0,
        sortino_ratio=1.2,
        max_drawdown=2.0,
        max_drawdown_pct=2.0,
        total_return_pct=5.0,
        annualized_return_pct=60.0,
        avg_hold_duration_hours=24.0,
        trades_per_day=0.3,
        total_fees=0.25,
        avg_fee_per_trade=0.025,
        net_pnl=4.75,
        opportunities_found=20,
        opportunities_taken=10,
        opportunity_conversion_rate=0.5
    )

    generator = ReportGenerator(output_dir="data/backtest_test/reports")
    report_path = generator.generate_html_report(performance, [], DummyConfig())

    assert os.path.exists(report_path), "Should create HTML report"
    print(f"✅ ReportGenerator works")
    print(f"   Report: {report_path}")


def main():
    """Run all tests"""
    print("=" * 80)
    print("BACKTESTING FRAMEWORK TESTS")
    print("=" * 80)

    try:
        test_historical_data_fetcher()
        test_performance_metrics()
        test_backtest_runner()
        test_report_generator()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nBacktesting framework is ready to use!")
        print("\nNext steps:")
        print("1. Run a full backtest: python -m agents.backtesting.backtest_runner --start-date 2025-10-01 --end-date 2026-01-01")
        print("2. Test different strategies")
        print("3. Compare exit strategies")
        print("4. Validate edge before live trading")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
