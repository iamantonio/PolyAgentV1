#!/home/tony/Dev/agents/.venv/bin/python
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 LIVE TRADING DASHBOARD 🚀                               ║
║                    Real-time performance metrics                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import os
import time
import sys
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.align import Align

console = Console()

# Database path
DB_PATH = os.path.expanduser("~/.polymarket/learning_trader.db")

# ASCII Art Header
HEADER = """
[bold cyan]
 ██████╗  ██████╗ ██╗  ██╗   ██╗███╗   ███╗ █████╗ ██████╗ ██╗  ██╗███████╗████████╗
 ██╔══██╗██╔═══██╗██║  ╚██╗ ██╔╝████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔════╝╚══██╔══╝
 ██████╔╝██║   ██║██║   ╚████╔╝ ██╔████╔██║███████║██████╔╝█████╔╝ █████╗     ██║
 ██╔═══╝ ██║   ██║██║    ╚██╔╝  ██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██╔══╝     ██║
 ██║     ╚██████╔╝███████╗██║   ██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗███████╗   ██║
 ╚═╝      ╚═════╝ ╚══════╝╚═╝   ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝
[/bold cyan]
[bold yellow]                      ⚡ LEARNING AUTONOMOUS TRADER ⚡[/bold yellow]
"""


def get_db_connection():
    """Get database connection"""
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def get_performance_summary(conn, days=30):
    """Get performance metrics"""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) as total_predictions,
            SUM(CASE WHEN trade_executed = 1 THEN 1 ELSE 0 END) as trades_executed,
            SUM(CASE WHEN profit_loss_usdc > 0 THEN 1 ELSE 0 END) as profitable_trades,
            SUM(profit_loss_usdc) as total_pnl,
            AVG(confidence) as avg_confidence,
            COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END) as resolved_markets,
            MAX(timestamp) as last_trade
        FROM predictions
        WHERE timestamp >= ?
    """, (cutoff,))

    return dict(cursor.fetchone())


def get_market_type_stats(conn):
    """Get stats by market type"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COALESCE(market_type, 'unknown') as market_type,
            COUNT(*) as total_trades,
            SUM(CASE WHEN profit_loss_usdc > 0 THEN 1 ELSE 0 END) as wins,
            SUM(profit_loss_usdc) as total_pnl,
            AVG(profit_loss_usdc) as avg_pnl
        FROM predictions
        WHERE trade_executed = 1 AND actual_outcome IS NOT NULL
        GROUP BY market_type
        ORDER BY total_trades DESC
    """)

    return [dict(row) for row in cursor.fetchall()]


def get_open_positions(conn):
    """Get open positions"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            question,
            predicted_outcome,
            trade_price as entry_price,
            trade_size_usdc as size,
            confidence,
            entry_timestamp
        FROM predictions
        WHERE position_open = 1 AND trade_executed = 1
        ORDER BY entry_timestamp DESC
        LIMIT 5
    """)

    return [dict(row) for row in cursor.fetchall()]


def get_recent_trades(conn, limit=5):
    """Get recent trades"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            question,
            predicted_outcome,
            profit_loss_usdc,
            actual_outcome,
            resolution_date
        FROM predictions
        WHERE trade_executed = 1 AND actual_outcome IS NOT NULL
        ORDER BY resolution_date DESC
        LIMIT ?
    """, (limit,))

    return [dict(row) for row in cursor.fetchall()]


def create_sparkline(values, width=20):
    """Create a text sparkline"""
    if not values:
        return "─" * width

    chars = "▁▂▃▄▅▆▇█"
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        return chars[3] * min(len(values), width)

    result = ""
    for v in values[-width:]:
        idx = int((v - min_val) / (max_val - min_val) * (len(chars) - 1))
        result += chars[idx]

    return result


def make_bar(value, max_value, width=20, color="green"):
    """Create a progress bar"""
    if max_value == 0:
        filled = 0
    else:
        filled = int((value / max_value) * width)

    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}]"


def generate_dashboard():
    """Generate the dashboard layout"""
    conn = get_db_connection()

    if not conn:
        return Panel(
            "[bold red]⚠️  Database not found at ~/.polymarket/learning_trader.db[/bold red]\n\n"
            "[yellow]Run your trading bot first to create the database.[/yellow]",
            title="[bold red]ERROR[/bold red]",
            border_style="red"
        )

    try:
        # Fetch all data
        perf = get_performance_summary(conn)
        market_stats = get_market_type_stats(conn)
        positions = get_open_positions(conn)
        recent = get_recent_trades(conn)

        # Build layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=10),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )

        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )

        layout["left"].split_column(
            Layout(name="stats", size=12),
            Layout(name="markets")
        )

        layout["right"].split_column(
            Layout(name="positions", size=15),
            Layout(name="recent")
        )

        # Header
        layout["header"].update(Panel(
            Align.center(Text.from_markup(HEADER.strip())),
            border_style="cyan"
        ))

        # Stats Panel
        total_pnl = perf['total_pnl'] or 0
        win_rate = 0
        if perf['resolved_markets'] and perf['resolved_markets'] > 0:
            wins = perf['profitable_trades'] or 0
            win_rate = (wins / perf['resolved_markets']) * 100

        pnl_color = "green" if total_pnl >= 0 else "red"
        pnl_symbol = "▲" if total_pnl >= 0 else "▼"

        stats_text = f"""
[bold white]📊 PERFORMANCE METRICS (30 DAYS)[/bold white]

  Total P&L:      [{pnl_color}]{pnl_symbol} ${total_pnl:,.2f}[/{pnl_color}]
  Win Rate:       {make_bar(win_rate, 100, 15, 'cyan')} [bold]{win_rate:.1f}%[/bold]

  Predictions:    [bold cyan]{perf['total_predictions']}[/bold cyan]
  Trades:         [bold yellow]{perf['trades_executed'] or 0}[/bold yellow]
  Resolved:       [bold green]{perf['resolved_markets'] or 0}[/bold green]
  Avg Confidence: [bold magenta]{(perf['avg_confidence'] or 0) * 100:.1f}%[/bold magenta]
"""

        layout["stats"].update(Panel(stats_text, title="[bold cyan]📈 Stats[/bold cyan]", border_style="cyan"))

        # Market Type Performance
        market_table = Table(show_header=True, header_style="bold magenta", border_style="magenta")
        market_table.add_column("Type", style="cyan")
        market_table.add_column("Trades", justify="right")
        market_table.add_column("Win%", justify="right")
        market_table.add_column("P&L", justify="right")
        market_table.add_column("Edge", justify="center")

        for m in market_stats:
            wins = m['wins'] or 0
            total = m['total_trades']
            win_pct = (wins / total * 100) if total > 0 else 0
            pnl = m['total_pnl'] or 0
            avg_pnl = m['avg_pnl'] or 0

            edge = "[bold green]✓[/bold green]" if avg_pnl > 0 else "[bold red]✗[/bold red]"
            pnl_style = "green" if pnl >= 0 else "red"

            market_table.add_row(
                m['market_type'][:12],
                str(total),
                f"{win_pct:.0f}%",
                f"[{pnl_style}]${pnl:.2f}[/{pnl_style}]",
                edge
            )

        layout["markets"].update(Panel(market_table, title="[bold magenta]🎯 Market Types[/bold magenta]", border_style="magenta"))

        # Open Positions
        pos_table = Table(show_header=True, header_style="bold yellow", border_style="yellow", show_lines=True)
        pos_table.add_column("Market", style="white", max_width=30)
        pos_table.add_column("Side", justify="center", style="cyan")
        pos_table.add_column("Entry", justify="right")
        pos_table.add_column("Size", justify="right")

        if positions:
            for p in positions:
                question = (p['question'] or "")[:28] + "..." if len(p['question'] or "") > 28 else (p['question'] or "")
                side_color = "green" if p['predicted_outcome'] == 'Yes' else "red"

                pos_table.add_row(
                    question,
                    f"[{side_color}]{p['predicted_outcome']}[/{side_color}]",
                    f"${p['entry_price']:.2f}" if p['entry_price'] else "N/A",
                    f"${p['size']:.2f}" if p['size'] else "N/A"
                )
        else:
            pos_table.add_row("[dim]No open positions[/dim]", "", "", "")

        layout["positions"].update(Panel(pos_table, title="[bold yellow]📍 Open Positions[/bold yellow]", border_style="yellow"))

        # Recent Trades
        recent_table = Table(show_header=True, header_style="bold green", border_style="green")
        recent_table.add_column("Market", style="white", max_width=35)
        recent_table.add_column("Result", justify="center")
        recent_table.add_column("P&L", justify="right")

        if recent:
            for r in recent:
                question = (r['question'] or "")[:33] + "..." if len(r['question'] or "") > 33 else (r['question'] or "")
                pnl = r['profit_loss_usdc'] or 0

                if pnl > 0:
                    result = "[bold green]WIN ✓[/bold green]"
                    pnl_text = f"[green]+${pnl:.2f}[/green]"
                else:
                    result = "[bold red]LOSS ✗[/bold red]"
                    pnl_text = f"[red]-${abs(pnl):.2f}[/red]"

                recent_table.add_row(question, result, pnl_text)
        else:
            recent_table.add_row("[dim]No recent trades[/dim]", "", "")

        layout["recent"].update(Panel(recent_table, title="[bold green]📜 Recent Trades[/bold green]", border_style="green"))

        # Footer
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        layout["footer"].update(Panel(
            f"[dim]Last updated: {now} | Refresh: 2s | Press Ctrl+C to exit[/dim]",
            border_style="dim"
        ))

        return layout

    finally:
        conn.close()


def main():
    console.clear()

    with Live(generate_dashboard(), refresh_per_second=0.5, screen=True) as live:
        try:
            while True:
                time.sleep(2)
                live.update(generate_dashboard())
        except KeyboardInterrupt:
            pass

    console.print("\n[bold cyan]Dashboard closed. Happy trading! 🚀[/bold cyan]")


if __name__ == "__main__":
    main()
