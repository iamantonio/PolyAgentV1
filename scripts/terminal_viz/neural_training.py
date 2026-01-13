#!/home/tony/Dev/agents/.venv/bin/python
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🧠 NEURAL CALIBRATION TRAINING 🧠                          ║
║                    Real isotonic regression training - LIVE DATA              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import sqlite3
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, '/home/tony/Dev/agents')

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.table import Table
from rich.align import Align
from rich import box

console = Console()

# Database path
DB_PATH = os.path.expanduser("~/.polymarket/learning_trader.db")

HEADER = """
[bold magenta]
███╗   ██╗███████╗██╗   ██╗██████╗  █████╗ ██╗
████╗  ██║██╔════╝██║   ██║██╔══██╗██╔══██╗██║
██╔██╗ ██║█████╗  ██║   ██║██████╔╝███████║██║
██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██╔══██║██║
██║ ╚████║███████╗╚██████╔╝██║  ██║██║  ██║███████╗
╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
[/bold magenta]
[bold cyan]      ⚡ ISOTONIC CALIBRATION - REAL TRAINING DATA ⚡[/bold cyan]
"""


class RealNeuralTrainer:
    """Real training using isotonic regression on actual trade data"""

    def __init__(self):
        self.status = "INITIALIZING"
        self.log = []

        # Training state
        self.epoch = 0
        self.max_epochs = 20
        self.training_complete = False

        # Real data
        self.raw_data = []
        self.calibrator = None
        self.training_samples = 0

        # Metrics from real data
        self.brier_before = None
        self.brier_after = None
        self.calibration_error = None

        # Calibration curve data
        self.calibration_buckets = []

        # Training history
        self.loss_history = []
        self.accuracy_history = []

        self.add_log("🚀 Initializing calibration trainer...", "cyan")
        self._load_training_data()

    def add_log(self, msg, style="white"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[dim]{ts}[/dim] [{style}]{msg}[/{style}]")
        if len(self.log) > 12:
            self.log.pop(0)

    def _load_training_data(self):
        """Load real prediction data from database"""
        if not os.path.exists(DB_PATH):
            self.add_log("❌ Database not found", "red")
            self.status = "NO DATA"
            return

        try:
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    confidence,
                    predicted_probability,
                    profit_loss_usdc,
                    market_type
                FROM predictions
                WHERE actual_outcome IS NOT NULL
                AND confidence IS NOT NULL
                AND trade_executed = 1
            """)

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                self.add_log("⚠️ No resolved predictions found", "yellow")
                self.status = "INSUFFICIENT DATA"
                return

            self.raw_data = [dict(row) for row in rows]
            self.training_samples = len(self.raw_data)
            self.add_log(f"📊 Loaded {self.training_samples} training samples", "green")

            # Calculate calibration buckets
            self._calculate_calibration_buckets()

            # Calculate initial Brier score
            self._calculate_brier_scores()

            self.status = "READY"

        except Exception as e:
            self.add_log(f"❌ DB error: {e}", "red")
            self.status = "ERROR"

    def _calculate_calibration_buckets(self):
        """Calculate calibration curve from real data"""
        buckets = {}
        for row in self.raw_data:
            conf = row['confidence']
            pnl = row['profit_loss_usdc']
            outcome = 1 if (pnl is not None and pnl > 0) else 0

            bucket = int(conf * 10) / 10  # Round to 0.1
            if bucket not in buckets:
                buckets[bucket] = {'total': 0, 'correct': 0}

            buckets[bucket]['total'] += 1
            buckets[bucket]['correct'] += outcome

        self.calibration_buckets = []
        for conf, data in sorted(buckets.items()):
            acc = data['correct'] / data['total'] if data['total'] > 0 else 0
            self.calibration_buckets.append({
                'confidence': conf,
                'accuracy': acc,
                'count': data['total']
            })

    def _calculate_brier_scores(self):
        """Calculate Brier score before and after calibration"""
        if not self.raw_data:
            return

        brier_scores = []
        for row in self.raw_data:
            conf = row['confidence']
            pnl = row['profit_loss_usdc']
            actual = 1.0 if (pnl is not None and pnl > 0) else 0.0
            brier_scores.append((conf - actual) ** 2)

        self.brier_before = sum(brier_scores) / len(brier_scores)

    def train_step(self):
        """Perform one training epoch using isotonic regression"""
        if self.training_complete or not self.raw_data:
            return

        self.epoch += 1
        self.status = "TRAINING"

        try:
            from sklearn.isotonic import IsotonicRegression

            # Extract data
            y_pred = np.array([row['confidence'] for row in self.raw_data])
            y_true = np.array([1.0 if (row['profit_loss_usdc'] or 0) > 0 else 0.0 for row in self.raw_data])

            # Train isotonic regression
            self.calibrator = IsotonicRegression(out_of_bounds='clip')
            self.calibrator.fit(y_pred, y_true)

            # Calculate calibrated Brier score
            y_calibrated = self.calibrator.predict(y_pred)
            brier_after_scores = [(y_calibrated[i] - y_true[i]) ** 2 for i in range(len(y_true))]
            self.brier_after = sum(brier_after_scores) / len(brier_after_scores)

            # Calculate calibration error (mean absolute difference from perfect calibration)
            errors = []
            for bucket in self.calibration_buckets:
                predicted = bucket['confidence']
                actual = bucket['accuracy']
                errors.append(abs(predicted - actual))
            self.calibration_error = sum(errors) / len(errors) if errors else 0

            # Track progress
            improvement = (self.brier_before - self.brier_after) / self.brier_before * 100 if self.brier_before else 0
            self.loss_history.append(self.brier_after)
            self.accuracy_history.append(100 - self.calibration_error * 100)

            if self.epoch % 5 == 0:
                self.add_log(f"Epoch {self.epoch}: Brier {self.brier_after:.4f} ({improvement:+.1f}%)", "green")

        except ImportError:
            self.add_log("❌ sklearn not available", "red")
            self.status = "ERROR"
            return
        except Exception as e:
            self.add_log(f"⚠️ Training error: {e}", "yellow")

        if self.epoch >= self.max_epochs:
            self.training_complete = True
            self.status = "COMPLETE"
            self.add_log("🎉 Training complete!", "green bold")

    def make_sparkline(self, values, width=30):
        """Create sparkline from values"""
        if not values:
            return "─" * width

        chars = "▁▂▃▄▅▆▇█"
        min_v = min(values) if values else 0
        max_v = max(values) if values else 1

        if max_v == min_v:
            return chars[4] * min(len(values), width)

        result = ""
        for v in values[-width:]:
            idx = int((v - min_v) / (max_v - min_v + 0.001) * (len(chars) - 1))
            result += chars[idx]

        return result

    def generate_display(self):
        """Generate the training display"""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=9),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        layout["main"].split_row(
            Layout(name="training", ratio=2),
            Layout(name="sidebar")
        )

        layout["sidebar"].split_column(
            Layout(name="calibration", size=18),
            Layout(name="log")
        )

        # Header
        progress_pct = (self.epoch / self.max_epochs) * 100 if self.max_epochs else 0
        status_color = "green" if self.status == "COMPLETE" else ("yellow" if self.status == "TRAINING" else "cyan")

        header_content = f"""
[bold cyan]🧠 ISOTONIC CALIBRATION TRAINER[/bold cyan]

[bold]Samples:[/bold] {self.training_samples}  [bold]Epoch:[/bold] {self.epoch}/{self.max_epochs}  [bold]Status:[/bold] [{status_color}]{self.status}[/{status_color}]

[cyan][{"█" * int(progress_pct/2)}{"░" * (50 - int(progress_pct/2))}][/cyan] {progress_pct:.0f}%
"""
        layout["header"].update(Panel(header_content, border_style="magenta"))

        # Training Panel
        training_content = self._build_training_panel()
        layout["training"].update(Panel(
            training_content,
            title="[bold green]📈 TRAINING METRICS[/bold green]",
            border_style="green",
            box=box.DOUBLE
        ))

        # Calibration Curve Panel
        calibration_content = self._build_calibration_panel()
        layout["calibration"].update(Panel(
            calibration_content,
            title="[bold magenta]📊 CALIBRATION CURVE[/bold magenta]",
            border_style="magenta"
        ))

        # Log Panel
        log_content = "\n".join(self.log) if self.log else "[dim]Initializing...[/dim]"
        layout["log"].update(Panel(
            log_content,
            title="[bold yellow]📜 LOG[/bold yellow]",
            border_style="yellow"
        ))

        # Footer
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        layout["footer"].update(Panel(
            f"[dim]⏱️  {now} | Training samples: {self.training_samples} | Press Ctrl+C to stop[/dim]",
            border_style="dim"
        ))

        return layout

    def _build_training_panel(self):
        """Build training metrics panel"""
        if not self.raw_data:
            return "[bold red]No training data available[/bold red]\n\nRun the trading bot to generate predictions."

        brier_before = self.brier_before or 0
        brier_after = self.brier_after or brier_before
        improvement = ((brier_before - brier_after) / brier_before * 100) if brier_before else 0

        # Color based on improvement
        if improvement > 5:
            imp_color = "green"
        elif improvement > 0:
            imp_color = "yellow"
        else:
            imp_color = "red"

        loss_spark = self.make_sparkline(self.loss_history)

        content = f"""
[bold white]═══════════════ BRIER SCORE ═══════════════[/bold white]

[bold]Before Calibration:[/bold] [yellow]{brier_before:.4f}[/yellow]
[bold]After Calibration:[/bold]  [green]{brier_after:.4f}[/green]
[bold]Improvement:[/bold]        [{imp_color}]{improvement:+.1f}%[/{imp_color}]

[dim](Lower Brier score = better calibration)[/dim]

[bold white]═══════════════ LOSS HISTORY ═══════════════[/bold white]

[cyan]{loss_spark}[/cyan]

[bold white]═══════════════ TRAINING DATA ═══════════════[/bold white]

[bold]Total Predictions:[/bold] {self.training_samples}
[bold]Calibration Error:[/bold] {(self.calibration_error or 0)*100:.1f}%

"""

        # Add data breakdown by market type
        market_types = {}
        for row in self.raw_data:
            mt = row.get('market_type', 'unknown')
            if mt not in market_types:
                market_types[mt] = 0
            market_types[mt] += 1

        if market_types:
            content += "[bold]By Market Type:[/bold]\n"
            for mt, count in sorted(market_types.items(), key=lambda x: -x[1]):
                content += f"  [cyan]{mt}:[/cyan] {count}\n"

        return content

    def _build_calibration_panel(self):
        """Build calibration curve visualization"""
        if not self.calibration_buckets:
            return "[dim]No calibration data[/dim]"

        lines = []
        lines.append("[bold]Pred → Actual (count)[/bold]")
        lines.append("")

        for bucket in self.calibration_buckets:
            conf = bucket['confidence']
            acc = bucket['accuracy']
            count = bucket['count']

            # Visual bar
            bar_width = 12
            conf_bar = int(conf * bar_width)
            acc_bar = int(acc * bar_width)

            # Determine calibration quality
            diff = abs(conf - acc)
            if diff < 0.1:
                quality = "[green]●[/green]"
            elif diff < 0.2:
                quality = "[yellow]●[/yellow]"
            else:
                quality = "[red]●[/red]"

            lines.append(
                f"{quality} {conf*100:3.0f}%→{acc*100:3.0f}% ({count:2d})"
            )

        lines.append("")
        lines.append("[green]●[/green]<10% [yellow]●[/yellow]<20% [red]●[/red]>20% error")

        return "\n".join(lines)


def main():
    console.clear()
    trainer = RealNeuralTrainer()

    with Live(trainer.generate_display(), refresh_per_second=2, screen=True) as live:
        try:
            time.sleep(1)

            while not trainer.training_complete:
                trainer.train_step()
                live.update(trainer.generate_display())
                time.sleep(0.5)

            # Keep displaying after complete
            while True:
                time.sleep(1)
                live.update(trainer.generate_display())

        except KeyboardInterrupt:
            pass

    if trainer.brier_after:
        console.print(f"\n[bold green]Training complete! Brier score: {trainer.brier_after:.4f}[/bold green]")
    else:
        console.print("\n[bold yellow]Training interrupted.[/bold yellow]")


if __name__ == "__main__":
    main()
