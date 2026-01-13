#!/home/tony/Dev/agents/.venv/bin/python
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    📊 CALIBRATION ANALYZER 📊                                 ║
║                    Prediction accuracy visualization                          ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import os
import time
from datetime import datetime, timedelta
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from rich import box

console = Console()

DB_PATH = os.path.expanduser("~/.polymarket/learning_trader.db")

HEADER = """
[bold blue]
 ██████╗ █████╗ ██╗     ██╗██████╗ ██████╗  █████╗ ████████╗██╗ ██████╗ ███╗   ██╗
██╔════╝██╔══██╗██║     ██║██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║
██║     ███████║██║     ██║██████╔╝██████╔╝███████║   ██║   ██║██║   ██║██╔██╗ ██║
██║     ██╔══██║██║     ██║██╔══██╗██╔══██╗██╔══██║   ██║   ██║██║   ██║██║╚██╗██║
╚██████╗██║  ██║███████╗██║██████╔╝██║  ██║██║  ██║   ██║   ██║╚██████╔╝██║ ╚████║
 ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
[/bold blue]
"""


def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def get_calibration_data(conn):
    """Get calibration curve data"""
    cursor = conn.cursor()

    # Get predictions grouped by confidence buckets
    cursor.execute("""
        SELECT
            CAST(confidence * 10 AS INTEGER) / 10.0 as bucket,
            COUNT(*) as total,
            SUM(CASE WHEN profit_loss_usdc IS NOT NULL AND profit_loss_usdc > 0 THEN 1 ELSE 0 END) as correct
        FROM predictions
        WHERE trade_executed = 1 AND actual_outcome IS NOT NULL AND confidence IS NOT NULL
        GROUP BY CAST(confidence * 10 AS INTEGER)
        ORDER BY bucket
    """)

    return [dict(row) for row in cursor.fetchall()]


def get_brier_score(conn):
    """Calculate Brier score"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT confidence, profit_loss_usdc
        FROM predictions
        WHERE trade_executed = 1 AND actual_outcome IS NOT NULL
        AND confidence IS NOT NULL
    """)

    rows = cursor.fetchall()
    if not rows:
        return None

    brier_scores = []
    for row in rows:
        conf = row['confidence']
        pnl = row['profit_loss_usdc']
        if conf is None:
            continue
        actual = 1.0 if (pnl is not None and pnl > 0) else 0.0
        brier_scores.append((conf - actual) ** 2)

    return sum(brier_scores) / len(brier_scores) if brier_scores else None


def get_strategy_performance(conn):
    """Get performance by strategy"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COALESCE(strategy, 'unknown') as strategy,
            COUNT(*) as total,
            SUM(CASE WHEN profit_loss_usdc > 0 THEN 1 ELSE 0 END) as wins,
            SUM(profit_loss_usdc) as pnl,
            AVG(confidence) as avg_conf
        FROM predictions
        WHERE trade_executed = 1 AND actual_outcome IS NOT NULL
        GROUP BY strategy
        ORDER BY total DESC
    """)
    return [dict(row) for row in cursor.fetchall()]


def draw_calibration_chart(data, width=50, height=15):
    """Draw ASCII calibration chart"""
    if not data:
        return "[dim]No calibration data available[/dim]"

    lines = []

    # Header
    lines.append("[bold white]Predicted vs Actual Accuracy[/bold white]")
    lines.append("")

    # Y-axis labels and chart
    for y in range(height, -1, -1):
        y_val = y / height * 100

        if y % 3 == 0:
            label = f"{y_val:3.0f}% │"
        else:
            label = "     │"

        row = label

        for x in range(width):
            x_val = x / width  # 0 to 1

            # Find data point for this x position
            point_data = None
            for d in data:
                if abs(d['bucket'] - x_val) < 0.1:
                    point_data = d
                    break

            # Perfect calibration line
            perfect_y = x_val * 100
            on_perfect_line = abs(perfect_y - y_val) < (100 / height / 2)

            # Actual accuracy point
            if point_data:
                actual_acc = (point_data['correct'] / point_data['total'] * 100) if point_data['total'] > 0 else 0
                on_actual = abs(actual_acc - y_val) < (100 / height / 2)
            else:
                on_actual = False

            if on_actual and point_data:
                # Color based on how close to perfect
                diff = abs(actual_acc - (point_data['bucket'] * 100))
                if diff < 10:
                    row += "[green]●[/green]"
                elif diff < 20:
                    row += "[yellow]●[/yellow]"
                else:
                    row += "[red]●[/red]"
            elif on_perfect_line:
                row += "[dim]·[/dim]"
            else:
                row += " "

        lines.append(row)

    # X-axis
    lines.append("     └" + "─" * width)

    # X-axis labels
    x_labels = "      "
    for i in range(0, width + 1, width // 5):
        pct = int(i / width * 100)
        x_labels += f"{pct}%".ljust(width // 5)
    lines.append(x_labels)
    lines.append("[dim]           Predicted Confidence →[/dim]")

    # Legend
    lines.append("")
    lines.append("[dim]·[/dim] = Perfect calibration    [green]●[/green] = Well calibrated (<10% off)")
    lines.append("[yellow]●[/yellow] = Moderate (<20% off)      [red]●[/red] = Poor calibration (>20% off)")

    return "\n".join(lines)


def draw_confidence_histogram(data, width=40):
    """Draw histogram of predictions by confidence"""
    if not data:
        return "[dim]No data[/dim]"

    max_count = max(d['total'] for d in data) if data else 1

    lines = []
    lines.append("[bold]Distribution of Predictions by Confidence[/bold]")
    lines.append("")

    for d in data:
        bucket = d['bucket']
        total = d['total']
        correct = d['correct'] or 0
        acc = (correct / total * 100) if total > 0 else 0

        bar_len = int((total / max_count) * width)
        correct_len = int((correct / max_count) * width) if max_count > 0 else 0

        bar = f"[green]{'█' * correct_len}[/green][red]{'█' * (bar_len - correct_len)}[/red]{'░' * (width - bar_len)}"

        lines.append(f"{bucket*100:3.0f}% │{bar}│ {total:3d} ({acc:.0f}%)")

    return "\n".join(lines)


def generate_display():
    """Generate the calibration display"""
    conn = get_db_connection()

    if not conn:
        return Panel(
            "[bold red]⚠️ Database not found[/bold red]",
            title="ERROR",
            border_style="red"
        )

    try:
        cal_data = get_calibration_data(conn)
        brier = get_brier_score(conn)
        strategies = get_strategy_performance(conn)

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=9),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        layout["main"].split_row(
            Layout(name="chart", ratio=2),
            Layout(name="sidebar")
        )

        layout["sidebar"].split_column(
            Layout(name="histogram"),
            Layout(name="strategies")
        )

        # Header
        layout["header"].update(Panel(
            Align.center(Text.from_markup(HEADER.strip())),
            border_style="blue"
        ))

        # Calibration chart
        chart_content = draw_calibration_chart(cal_data)

        # Add Brier score
        if brier is not None:
            brier_quality = "Excellent" if brier < 0.1 else ("Good" if brier < 0.2 else ("Fair" if brier < 0.3 else "Poor"))
            brier_color = "green" if brier < 0.15 else ("yellow" if brier < 0.25 else "red")
            chart_content += f"\n\n[bold]Brier Score:[/bold] [{brier_color}]{brier:.4f}[/{brier_color}] ({brier_quality})"
            chart_content += f"\n[dim](Lower is better. 0 = perfect, 0.25 = random)[/dim]"

        layout["chart"].update(Panel(
            chart_content,
            title="[bold blue]📈 CALIBRATION CURVE[/bold blue]",
            border_style="blue",
            box=box.DOUBLE
        ))

        # Histogram
        histogram = draw_confidence_histogram(cal_data)
        layout["histogram"].update(Panel(
            histogram,
            title="[bold magenta]📊 CONFIDENCE DIST[/bold magenta]",
            border_style="magenta"
        ))

        # Strategy performance
        strat_table = Table(
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            box=box.SIMPLE
        )
        strat_table.add_column("Strategy", style="white")
        strat_table.add_column("Trades", justify="right")
        strat_table.add_column("Win%", justify="right")
        strat_table.add_column("P&L", justify="right")

        for s in strategies:
            wins = s['wins'] or 0
            total = s['total']
            win_rate = (wins / total * 100) if total > 0 else 0
            pnl = s['pnl'] or 0

            pnl_style = "green" if pnl >= 0 else "red"

            strat_table.add_row(
                s['strategy'][:15],
                str(total),
                f"{win_rate:.0f}%",
                f"[{pnl_style}]${pnl:.2f}[/{pnl_style}]"
            )

        layout["strategies"].update(Panel(
            strat_table,
            title="[bold cyan]🎯 BY STRATEGY[/bold cyan]",
            border_style="cyan"
        ))

        # Footer
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        layout["footer"].update(Panel(
            f"[dim]⏱️  {now} | Refresh: 5s | Press Ctrl+C to exit[/dim]",
            border_style="dim"
        ))

        return layout

    finally:
        conn.close()


def main():
    console.clear()

    with Live(generate_display(), refresh_per_second=0.2, screen=True) as live:
        try:
            while True:
                time.sleep(5)
                live.update(generate_display())
        except KeyboardInterrupt:
            pass

    console.print("\n[bold blue]Calibration analyzer closed. 📊[/bold blue]")


if __name__ == "__main__":
    main()
