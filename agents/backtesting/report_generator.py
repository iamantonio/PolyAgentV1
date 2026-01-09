#!/usr/bin/env python3
"""
Report Generator

Generates comprehensive HTML and JSON reports from backtest results.
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List
from dataclasses import asdict

from agents.backtesting.metrics import PerformanceReport, Trade


class ReportGenerator:
    """Generate backtest reports in multiple formats"""

    def __init__(self, output_dir: str = "data/backtest/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html_report(
        self,
        performance: PerformanceReport,
        trades: List[Trade],
        config
    ) -> str:
        """Generate interactive HTML report"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f"backtest_report_{timestamp}.html"

        html = self._build_html_report(performance, trades, config)

        with open(output_file, 'w') as f:
            f.write(html)

        return str(output_file)

    def generate_json_report(
        self,
        performance: PerformanceReport,
        trades: List[Trade],
        config
    ) -> str:
        """Generate JSON report for programmatic access"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = self.output_dir / f"backtest_report_{timestamp}.json"

        report_data = {
            'config': {
                'start_date': config.start_date.isoformat(),
                'end_date': config.end_date.isoformat(),
                'initial_capital': config.initial_capital,
                'strategy': config.strategy,
                'exit_strategy': config.exit_strategy,
                'min_confidence': config.min_confidence,
                'max_position_size': config.max_position_size,
                'fee_rate': config.fee_rate
            },
            'performance': asdict(performance),
            'trades': [asdict(t) for t in trades]
        }

        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)

        return str(output_file)

    def _build_html_report(
        self,
        performance: PerformanceReport,
        trades: List[Trade],
        config
    ) -> str:
        """Build HTML report content"""
        # Convert trades to DataFrame for easier display
        trades_df = pd.DataFrame([asdict(t) for t in trades]) if trades else pd.DataFrame()

        # Format trades table
        trades_html = ""
        if not trades_df.empty:
            trades_df['timestamp'] = pd.to_datetime(trades_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
            trades_df['pnl'] = trades_df['pnl'].apply(lambda x: f"${x:+.2f}")
            trades_df['pnl_pct'] = trades_df['pnl_pct'].apply(lambda x: f"{x:+.1f}%")
            trades_df['fees'] = trades_df['fees'].apply(lambda x: f"${x:.2f}")

            trades_html = trades_df.to_html(
                classes='table table-striped table-sm',
                index=False,
                escape=False
            )

        # Edge detection verdict
        has_edge = performance.net_pnl > 0 and performance.sharpe_ratio > 0.5
        edge_verdict = "✅ POSITIVE EDGE DETECTED" if has_edge else "❌ NO POSITIVE EDGE"
        edge_class = "alert-success" if has_edge else "alert-danger"

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backtest Report - {config.strategy}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {{ padding: 20px; }}
        .metric-card {{ margin-bottom: 20px; }}
        .positive {{ color: green; }}
        .negative {{ color: red; }}
        .table-sm {{ font-size: 0.85rem; }}
    </style>
</head>
<body>
    <div class="container-fluid">
        <h1>Polymarket Bot Backtest Report</h1>
        <p class="text-muted">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="alert {edge_class}" role="alert">
            <h4 class="alert-heading">{edge_verdict}</h4>
            <p>This bot {'has demonstrated' if has_edge else 'has NOT demonstrated'} positive edge on historical data.</p>
        </div>

        <h2>Configuration</h2>
        <div class="card metric-card">
            <div class="card-body">
                <table class="table table-sm">
                    <tr><th>Strategy</th><td>{config.strategy}</td></tr>
                    <tr><th>Exit Strategy</th><td>{config.exit_strategy}</td></tr>
                    <tr><th>Date Range</th><td>{config.start_date.date()} to {config.end_date.date()}</td></tr>
                    <tr><th>Initial Capital</th><td>${config.initial_capital:.2f}</td></tr>
                    <tr><th>Min Confidence</th><td>{config.min_confidence:.1%}</td></tr>
                    <tr><th>Max Position Size</th><td>${config.max_position_size:.2f}</td></tr>
                </table>
            </div>
        </div>

        <h2>Performance Metrics</h2>
        <div class="row">
            <div class="col-md-4">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">Trading Stats</h5>
                        <table class="table table-sm">
                            <tr><th>Total Trades</th><td>{performance.total_trades}</td></tr>
                            <tr><th>Winning Trades</th><td class="positive">{performance.winning_trades}</td></tr>
                            <tr><th>Losing Trades</th><td class="negative">{performance.losing_trades}</td></tr>
                            <tr><th>Win Rate</th><td>{performance.win_rate:.1%}</td></tr>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">PnL Metrics</h5>
                        <table class="table table-sm">
                            <tr><th>Total PnL</th><td class="{'positive' if performance.total_pnl > 0 else 'negative'}">${performance.total_pnl:+.2f}</td></tr>
                            <tr><th>Net PnL (after fees)</th><td class="{'positive' if performance.net_pnl > 0 else 'negative'}">${performance.net_pnl:+.2f}</td></tr>
                            <tr><th>Total Return</th><td>{performance.total_return_pct:+.1f}%</td></tr>
                            <tr><th>Annualized Return</th><td>{performance.annualized_return_pct:+.1f}%</td></tr>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">Risk Metrics</h5>
                        <table class="table table-sm">
                            <tr><th>Sharpe Ratio</th><td>{performance.sharpe_ratio:.2f}</td></tr>
                            <tr><th>Sortino Ratio</th><td>{performance.sortino_ratio:.2f}</td></tr>
                            <tr><th>Max Drawdown</th><td class="negative">{performance.max_drawdown_pct:.1f}%</td></tr>
                            <tr><th>Profit Factor</th><td>{performance.profit_factor:.2f}</td></tr>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-4">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">Trade Quality</h5>
                        <table class="table table-sm">
                            <tr><th>Avg PnL per Trade</th><td>${performance.avg_pnl_per_trade:+.2f}</td></tr>
                            <tr><th>Avg Win</th><td class="positive">${performance.avg_win:.2f}</td></tr>
                            <tr><th>Avg Loss</th><td class="negative">${performance.avg_loss:.2f}</td></tr>
                            <tr><th>Profit Factor</th><td>{performance.profit_factor:.2f}</td></tr>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">Costs</h5>
                        <table class="table table-sm">
                            <tr><th>Total Fees</th><td>${performance.total_fees:.2f}</td></tr>
                            <tr><th>Avg Fee per Trade</th><td>${performance.avg_fee_per_trade:.2f}</td></tr>
                            <tr><th>Fee Impact</th><td>{(performance.total_fees / performance.total_pnl * 100) if performance.total_pnl > 0 else 0:.1f}%</td></tr>
                        </table>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card metric-card">
                    <div class="card-body">
                        <h5 class="card-title">Opportunities</h5>
                        <table class="table table-sm">
                            <tr><th>Found</th><td>{performance.opportunities_found}</td></tr>
                            <tr><th>Taken</th><td>{performance.opportunities_taken}</td></tr>
                            <tr><th>Conversion Rate</th><td>{performance.opportunity_conversion_rate:.1%}</td></tr>
                            <tr><th>Trades per Day</th><td>{performance.trades_per_day:.2f}</td></tr>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <h2>Trade History</h2>
        <div class="table-responsive">
            {trades_html}
        </div>

        <h2>Recommendations</h2>
        <div class="card">
            <div class="card-body">
                {self._generate_recommendations(performance)}
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
        return html

    def _generate_recommendations(self, performance: PerformanceReport) -> str:
        """Generate recommendations based on performance"""
        recommendations = []

        # Edge detection
        if performance.net_pnl <= 0:
            recommendations.append("❌ <strong>NO POSITIVE EDGE:</strong> Bot is losing money. Do NOT trade live.")
        elif performance.sharpe_ratio < 0.5:
            recommendations.append("⚠️ <strong>WEAK EDGE:</strong> Sharpe ratio is low. Risk-adjusted returns are poor.")
        else:
            recommendations.append("✅ <strong>POSITIVE EDGE DETECTED:</strong> Bot shows profitable patterns.")

        # Win rate
        if performance.win_rate < 0.5:
            recommendations.append(f"⚠️ Win rate is {performance.win_rate:.1%}. Need >50% for sustainable edge.")

        # Profit factor
        if performance.profit_factor < 1.5:
            recommendations.append(f"⚠️ Profit factor is {performance.profit_factor:.2f}. Need >1.5 for good edge.")

        # Max drawdown
        if performance.max_drawdown_pct > 20:
            recommendations.append(f"⚠️ Max drawdown is {performance.max_drawdown_pct:.1f}%. Reduce position sizes.")

        # Trading frequency
        if performance.trades_per_day < 0.5:
            recommendations.append("⚠️ Very low trading frequency. May not find enough opportunities.")
        elif performance.trades_per_day > 10:
            recommendations.append("⚠️ Very high trading frequency. May be overtrading and racking up fees.")

        # Fees
        fee_impact = (performance.total_fees / performance.total_pnl * 100) if performance.total_pnl > 0 else 0
        if fee_impact > 30:
            recommendations.append(f"⚠️ Fees are eating {fee_impact:.1f}% of profits. Consider larger position sizes.")

        # Overall verdict
        if performance.net_pnl > 0 and performance.sharpe_ratio > 1.0 and performance.win_rate > 0.55:
            recommendations.append("🚀 <strong>READY FOR LIVE TRADING:</strong> All metrics look strong!")
        else:
            recommendations.append("🛑 <strong>NOT READY:</strong> Improve strategy before risking real capital.")

        return "<ul>" + "".join(f"<li>{r}</li>" for r in recommendations) + "</ul>"


if __name__ == "__main__":
    # Example usage
    from agents.backtesting.metrics import PerformanceReport, Trade

    # Sample performance report
    performance = PerformanceReport(
        total_trades=50,
        winning_trades=30,
        losing_trades=20,
        win_rate=0.6,
        total_pnl=15.0,
        avg_pnl_per_trade=0.3,
        avg_win=0.75,
        avg_loss=-0.50,
        profit_factor=1.8,
        sharpe_ratio=1.2,
        sortino_ratio=1.5,
        max_drawdown=5.0,
        max_drawdown_pct=5.0,
        total_return_pct=15.0,
        annualized_return_pct=45.0,
        avg_hold_duration_hours=36.0,
        trades_per_day=0.5,
        total_fees=1.5,
        avg_fee_per_trade=0.03,
        net_pnl=13.5,
        opportunities_found=100,
        opportunities_taken=50,
        opportunity_conversion_rate=0.5
    )

    # Generate report
    from dataclasses import dataclass
    from datetime import datetime, timezone

    @dataclass
    class DummyConfig:
        start_date = datetime(2025, 10, 1, tzinfo=timezone.utc)
        end_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        initial_capital = 100.0
        strategy = 'ai-prediction'
        exit_strategy = 'hold-to-resolution'
        min_confidence = 0.2
        max_position_size = 2.0
        fee_rate = 0.02

    generator = ReportGenerator()
    report_path = generator.generate_html_report(performance, [], DummyConfig())
    print(f"Report generated: {report_path}")
