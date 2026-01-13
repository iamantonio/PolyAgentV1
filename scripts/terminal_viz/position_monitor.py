#!/home/tony/Dev/agents/.venv/bin/python
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    💰 POSITION MONITOR 💰                                     ║
║                    Live position & P&L tracking                               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sqlite3
import os
import time
import random
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
[bold yellow]
██████╗  ██████╗ ███████╗██╗████████╗██╗ ██████╗ ███╗   ██╗███████╗
██╔══██╗██╔═══██╗██╔════╝██║╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝
██████╔╝██║   ██║███████╗██║   ██║   ██║██║   ██║██╔██╗ ██║███████╗
██╔═══╝ ██║   ██║╚════██║██║   ██║   ██║██║   ██║██║╚██╗██║╚════██║
██║     ╚██████╔╝███████║██║   ██║   ██║╚██████╔╝██║ ╚████║███████║
╚═╝      ╚═════╝ ╚══════╝╚═╝   ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
[/bold yellow]
"""


def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def get_open_positions(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            id,
            market_id,
            question,
            predicted_outcome,
            trade_price as entry_price,
            trade_size_usdc as size,
            confidence,
            entry_timestamp,
            market_type,
            time_to_close_hours
        FROM predictions
        WHERE position_open = 1 AND trade_executed = 1
        ORDER BY entry_timestamp DESC
    """)
    return [dict(row) for row in cursor.fetchall()]


def get_recent_closed(conn, limit=10):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            question,
            predicted_outcome,
            actual_outcome,
            trade_price as entry_price,
            exit_price,
            trade_size_usdc as size,
            profit_loss_usdc as pnl,
            exit_reason,
            exit_timestamp
        FROM predictions
        WHERE position_open = 0
        AND trade_executed = 1
        AND exit_timestamp IS NOT NULL
        ORDER BY exit_timestamp DESC
        LIMIT ?
    """, (limit,))
    return [dict(row) for row in cursor.fetchall()]


def get_portfolio_summary(conn):
    cursor = conn.cursor()

    # Open positions summary
    cursor.execute("""
        SELECT
            COUNT(*) as open_count,
            SUM(trade_size_usdc) as total_exposure
        FROM predictions
        WHERE position_open = 1 AND trade_executed = 1
    """)
    open_data = dict(cursor.fetchone())

    # Closed positions summary
    cursor.execute("""
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN profit_loss_usdc > 0 THEN 1 ELSE 0 END) as wins,
            SUM(profit_loss_usdc) as total_pnl,
            AVG(profit_loss_usdc) as avg_pnl
        FROM predictions
        WHERE trade_executed = 1 AND actual_outcome IS NOT NULL
    """)
    closed_data = dict(cursor.fetchone())

    return {**open_data, **closed_data}


def make_pnl_bar(pnl, max_pnl=5.0, width=15):
    """Create P&L visualization bar"""
    if pnl >= 0:
        filled = min(int((pnl / max_pnl) * width), width)
        return f"[green]{'█' * filled}{'░' * (width - filled)}[/green] +${pnl:.2f}"
    else:
        filled = min(int((abs(pnl) / max_pnl) * width), width)
        return f"[red]{'█' * filled}{'░' * (width - filled)}[/red] -${abs(pnl):.2f}"


class PositionMonitor:
    def __init__(self):
        self.simulated_prices = {}  # Simulated current prices for demo
        self.update_count = 0

    def simulate_price_movement(self, position):
        """Simulate price movement for unrealized P&L demo"""
        market_id = position['market_id']
        entry_price = position['entry_price'] or 0.5

        if market_id not in self.simulated_prices:
            self.simulated_prices[market_id] = entry_price

        # Random walk
        change = random.uniform(-0.02, 0.02)
        new_price = self.simulated_prices[market_id] + change
        new_price = max(0.01, min(0.99, new_price))
        self.simulated_prices[market_id] = new_price

        return new_price

    def calculate_unrealized_pnl(self, position, current_price):
        """Calculate unrealized P&L"""
        entry = position['entry_price']
        size = position['size']

        if not entry or not size:
            return 0.0

        # P&L = size * (current - entry) / entry
        return size * (current_price - entry) / entry

    def generate_display(self):
        """Generate the monitor display"""
        self.update_count += 1

        conn = get_db_connection()
        if not conn:
            return Panel(
                "[bold red]⚠️ Database not found[/bold red]\n\n"
                "[yellow]Run your trading bot first to create positions.[/yellow]",
                title="[bold red]ERROR[/bold red]",
                border_style="red"
            )

        try:
            positions = get_open_positions(conn)
            closed = get_recent_closed(conn)
            summary = get_portfolio_summary(conn)

            layout = Layout()
            layout.split_column(
                Layout(name="header", size=9),
                Layout(name="main"),
                Layout(name="footer", size=3)
            )

            layout["main"].split_row(
                Layout(name="positions", ratio=2),
                Layout(name="sidebar")
            )

            layout["sidebar"].split_column(
                Layout(name="summary", size=15),
                Layout(name="closed")
            )

            # Header
            layout["header"].update(Panel(
                Align.center(Text.from_markup(HEADER.strip())),
                border_style="yellow"
            ))

            # Positions table
            pos_table = Table(
                show_header=True,
                header_style="bold cyan",
                border_style="cyan",
                box=box.ROUNDED,
                expand=True
            )

            pos_table.add_column("Market", style="white", max_width=35)
            pos_table.add_column("Side", justify="center")
            pos_table.add_column("Entry", justify="right")
            pos_table.add_column("Current", justify="right")
            pos_table.add_column("Size", justify="right")
            pos_table.add_column("Unreal. P&L", justify="right")
            pos_table.add_column("Conf", justify="center")

            total_unrealized = 0.0

            if positions:
                for pos in positions:
                    question = pos['question'][:33] + "..." if len(pos['question'] or "") > 33 else (pos['question'] or "N/A")

                    side = pos['predicted_outcome'] or "?"
                    side_style = "green" if side == "Yes" else "red"

                    entry = pos['entry_price']
                    size = pos['size']
                    conf = pos['confidence']

                    # Get simulated current price
                    current = self.simulate_price_movement(pos)
                    pnl = self.calculate_unrealized_pnl(pos, current)
                    total_unrealized += pnl

                    pnl_style = "green" if pnl >= 0 else "red"
                    pnl_prefix = "+" if pnl >= 0 else ""

                    # Confidence bar
                    conf_val = (conf or 0) * 100
                    conf_display = f"{'█' * int(conf_val/20)}{'░' * (5 - int(conf_val/20))} {conf_val:.0f}%"

                    pos_table.add_row(
                        question,
                        f"[{side_style}]{side}[/{side_style}]",
                        f"${entry:.3f}" if entry else "N/A",
                        f"${current:.3f}",
                        f"${size:.2f}" if size else "N/A",
                        f"[{pnl_style}]{pnl_prefix}${pnl:.2f}[/{pnl_style}]",
                        conf_display
                    )
            else:
                pos_table.add_row(
                    "[dim]No open positions[/dim]",
                    "", "", "", "", "", ""
                )

            # Total row
            total_style = "green" if total_unrealized >= 0 else "red"
            total_prefix = "+" if total_unrealized >= 0 else ""

            positions_panel = Panel(
                pos_table,
                title=f"[bold cyan]📊 OPEN POSITIONS ({len(positions)})[/bold cyan]",
                subtitle=f"[{total_style}]Total Unrealized: {total_prefix}${total_unrealized:.2f}[/{total_style}]",
                border_style="cyan"
            )
            layout["positions"].update(positions_panel)

            # Summary panel
            total_pnl = summary['total_pnl'] or 0
            wins = summary['wins'] or 0
            total_trades = summary['total_trades'] or 0
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

            pnl_color = "green" if total_pnl >= 0 else "red"
            pnl_symbol = "▲" if total_pnl >= 0 else "▼"

            summary_content = f"""
[bold]Portfolio Summary[/bold]
{'─' * 20}

[bold]Open Positions:[/bold] [cyan]{summary['open_count'] or 0}[/cyan]
[bold]Total Exposure:[/bold] [yellow]${summary['total_exposure'] or 0:.2f}[/yellow]

{'─' * 20}

[bold]Realized P&L:[/bold]
  [{pnl_color}]{pnl_symbol} ${total_pnl:.2f}[/{pnl_color}]

[bold]Win Rate:[/bold]
  [{'green' if win_rate >= 50 else 'red'}]{win_rate:.1f}%[/{'green' if win_rate >= 50 else 'red'}] ({wins}/{total_trades})

[bold]Avg P&L/Trade:[/bold]
  ${summary['avg_pnl'] or 0:.2f}
"""
            layout["summary"].update(Panel(
                summary_content,
                title="[bold yellow]💼 PORTFOLIO[/bold yellow]",
                border_style="yellow"
            ))

            # Recent closed positions
            closed_table = Table(
                show_header=True,
                header_style="bold green",
                border_style="green",
                box=box.SIMPLE
            )
            closed_table.add_column("Market", max_width=25)
            closed_table.add_column("Result", justify="center")
            closed_table.add_column("P&L", justify="right")

            if closed:
                for c in closed[:6]:
                    q = (c['question'] or "")[:23] + "..." if len(c['question'] or "") > 23 else (c['question'] or "")
                    pnl = c['pnl'] or 0

                    result = "[green]WIN[/green]" if pnl > 0 else "[red]LOSS[/red]"
                    pnl_str = f"[green]+${pnl:.2f}[/green]" if pnl > 0 else f"[red]-${abs(pnl):.2f}[/red]"

                    closed_table.add_row(q, result, pnl_str)
            else:
                closed_table.add_row("[dim]No closed positions[/dim]", "", "")

            layout["closed"].update(Panel(
                closed_table,
                title="[bold green]📜 RECENT CLOSED[/bold green]",
                border_style="green"
            ))

            # Footer with live ticker
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ticker = "█" if self.update_count % 2 == 0 else "░"
            layout["footer"].update(Panel(
                f"[dim]⏱️  {now} | [green]{ticker}[/green] LIVE | Updates: {self.update_count} | Ctrl+C to exit[/dim]",
                border_style="dim"
            ))

            return layout

        finally:
            conn.close()


def main():
    console.clear()
    monitor = PositionMonitor()

    with Live(monitor.generate_display(), refresh_per_second=1, screen=True) as live:
        try:
            while True:
                time.sleep(1)
                live.update(monitor.generate_display())
        except KeyboardInterrupt:
            pass

    console.print("\n[bold yellow]Position monitor closed. 💰[/bold yellow]")


if __name__ == "__main__":
    main()
