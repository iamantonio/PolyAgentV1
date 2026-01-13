#!/home/tony/Dev/agents/.venv/bin/python
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🔍 REAL-TIME MARKET SCANNER 🔍                             ║
║                    Live Polymarket analysis - REAL DATA ONLY                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, '/home/tony/Dev/agents')

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.align import Align
from rich import box

console = Console()

# Cyber-style header
HEADER = """
[bold green]
███╗   ███╗ █████╗ ██████╗ ██╗  ██╗███████╗████████╗    ███████╗ ██████╗ █████╗ ███╗   ██╗
████╗ ████║██╔══██╗██╔══██╗██║ ██╔╝██╔════╝╚══██╔══╝    ██╔════╝██╔════╝██╔══██╗████╗  ██║
██╔████╔██║███████║██████╔╝█████╔╝ █████╗     ██║       ███████╗██║     ███████║██╔██╗ ██║
██║╚██╔╝██║██╔══██║██╔══██╗██╔═██╗ ██╔══╝     ██║       ╚════██║██║     ██╔══██║██║╚██╗██║
██║ ╚═╝ ██║██║  ██║██║  ██║██║  ██╗███████╗   ██║       ███████║╚██████╗██║  ██║██║ ╚████║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝       ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝
[/bold green]
[bold yellow]                         ⚡ LIVE POLYMARKET DATA ⚡[/bold yellow]
"""

# Database path
DB_PATH = os.path.expanduser("~/.polymarket/learning_trader.db")


class RealMarketScanner:
    """Scanner using real Polymarket Gamma API"""

    def __init__(self):
        self.scan_count = 0
        self.markets_analyzed = 0
        self.opportunities_found = 0
        self.current_market = None
        self.edge_data = {}
        self.log_lines = []
        self.markets = []
        self.market_index = 0
        self.last_fetch = 0
        self.fetch_interval = 60  # Refresh markets every 60 seconds

        # Import Gamma client
        try:
            from agents.polymarket.gamma import GammaMarketClient
            self.gamma = GammaMarketClient()
            self.api_available = True
            self.add_log("✅ Connected to Polymarket Gamma API", "green")
        except Exception as e:
            self.gamma = None
            self.api_available = False
            self.add_log(f"❌ Gamma API unavailable: {e}", "red")

        # Load edge data from DB
        self.edge_by_type = self._load_edge_data()

    def add_log(self, msg, style="white"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_lines.append(f"[dim]{timestamp}[/dim] [{style}]{msg}[/{style}]")
        if len(self.log_lines) > 15:
            self.log_lines.pop(0)

    def _load_edge_data(self) -> Dict:
        """Load edge detection data from DB"""
        if not os.path.exists(DB_PATH):
            return {}

        try:
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COALESCE(market_type, 'unknown') as market_type,
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit_loss_usdc IS NOT NULL AND profit_loss_usdc > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(profit_loss_usdc) as total_pnl,
                    AVG(profit_loss_usdc) as avg_pnl
                FROM predictions
                WHERE trade_executed = 1 AND actual_outcome IS NOT NULL
                GROUP BY market_type
            """)

            results = {}
            for row in cursor.fetchall():
                mtype = row['market_type']
                total = row['total_trades']
                wins = row['wins'] or 0
                avg_pnl = row['avg_pnl'] or 0

                results[mtype] = {
                    "total_trades": total,
                    "win_rate": (wins / total * 100) if total > 0 else 0,
                    "avg_pnl": avg_pnl,
                    "has_edge": avg_pnl > 0
                }

            conn.close()
            return results

        except Exception as e:
            self.add_log(f"⚠️ DB error: {e}", "yellow")
            return {}

    def fetch_markets(self):
        """Fetch real markets from Polymarket"""
        if not self.api_available:
            return

        now = time.time()
        if now - self.last_fetch < self.fetch_interval and self.markets:
            return  # Use cached markets

        try:
            self.add_log("🔄 Fetching markets from Polymarket...", "cyan")

            # Get active markets
            raw_markets = self.gamma.get_markets({
                "active": "true",
                "closed": "false",
                "limit": 50
            })

            if raw_markets:
                self.markets = raw_markets
                self.last_fetch = now
                self.add_log(f"📊 Loaded {len(self.markets)} active markets", "green")
            else:
                self.add_log("⚠️ No markets returned", "yellow")

        except Exception as e:
            self.add_log(f"❌ API error: {str(e)[:40]}", "red")

    def classify_market_type(self, market: Dict) -> str:
        """Classify market type from question text"""
        question = (market.get('question') or '').lower()

        if any(x in question for x in ['bitcoin', 'ethereum', 'crypto', 'btc', 'eth', 'xrp', 'solana']):
            return 'crypto'
        elif any(x in question for x in ['game', 'match', 'win', 'beat', 'score', 'playoff', 'championship', 'vs.', 'vs ']):
            return 'sports'
        elif any(x in question for x in ['trump', 'biden', 'election', 'president', 'congress', 'vote']):
            return 'politics'
        elif any(x in question for x in ['earnings', 'stock', 'gdp', 'fed', 'rate', 'market']):
            return 'finance'
        else:
            return 'other'

    def analyze_market(self, market: Dict) -> Dict:
        """Analyze a single market for edge"""
        question = market.get('question', 'Unknown')[:50]
        market_type = self.classify_market_type(market)

        # Get prices
        try:
            prices = market.get('outcomePrices', [])
            if isinstance(prices, str):
                import json
                prices = json.loads(prices)
            yes_price = float(prices[0]) if prices else 0.5
        except:
            yes_price = 0.5

        # Check edge from historical data
        edge_info = self.edge_by_type.get(market_type, {})
        has_edge = edge_info.get('has_edge', False)
        win_rate = edge_info.get('win_rate', 0)
        avg_pnl = edge_info.get('avg_pnl', 0)

        # Calculate theoretical edge
        # Edge = (our predicted prob) - (market price)
        # Without AI prediction, we use historical win rate as proxy
        implied_edge = (win_rate / 100) - yes_price if win_rate > 0 else 0

        # Determine signal
        if has_edge and implied_edge > 0.05:
            signal = "BUY YES"
            signal_color = "green"
        elif has_edge and implied_edge < -0.05:
            signal = "BUY NO"
            signal_color = "red"
        else:
            signal = "PASS"
            signal_color = "yellow"

        return {
            "question": question,
            "market_type": market_type,
            "yes_price": yes_price,
            "has_edge": has_edge,
            "win_rate": win_rate,
            "avg_pnl": avg_pnl,
            "implied_edge": implied_edge,
            "signal": signal,
            "signal_color": signal_color
        }

    def scan_next_market(self):
        """Scan the next market in the list"""
        self.fetch_markets()

        if not self.markets:
            self.add_log("⏳ Waiting for market data...", "yellow")
            return

        # Get next market
        market = self.markets[self.market_index]
        self.market_index = (self.market_index + 1) % len(self.markets)

        self.scan_count += 1
        self.markets_analyzed += 1

        # Analyze it
        self.edge_data = self.analyze_market(market)
        self.current_market = market

        if self.edge_data['signal'] != 'PASS':
            self.opportunities_found += 1
            self.add_log(f"🎯 {self.edge_data['signal']}: {self.edge_data['question'][:25]}...", "green bold")
        else:
            self.add_log(f"📊 {self.edge_data['question'][:30]}... [PASS]", "dim")

    def generate_display(self):
        """Generate the scanner display"""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=10),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        layout["main"].split_row(
            Layout(name="scanner", ratio=2),
            Layout(name="sidebar")
        )

        layout["sidebar"].split_column(
            Layout(name="edge", size=14),
            Layout(name="log")
        )

        # Header
        header_text = Text.from_markup(HEADER.strip())
        layout["header"].update(Panel(Align.center(header_text), border_style="green"))

        # Scanner Panel
        scanner_content = self._build_scanner_panel()
        layout["scanner"].update(Panel(
            scanner_content,
            title="[bold green]🔍 ACTIVE SCAN[/bold green]",
            border_style="green",
            box=box.DOUBLE
        ))

        # Edge Detection Panel
        edge_content = self._build_edge_panel()
        layout["edge"].update(Panel(
            edge_content,
            title="[bold cyan]📊 EDGE BY TYPE[/bold cyan]",
            border_style="cyan"
        ))

        # Log Panel
        log_content = "\n".join(self.log_lines) if self.log_lines else "[dim]Waiting for activity...[/dim]"
        layout["log"].update(Panel(
            log_content,
            title="[bold yellow]📜 ACTIVITY LOG[/bold yellow]",
            border_style="yellow"
        ))

        # Footer
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        api_status = "[green]●[/green] LIVE" if self.api_available else "[red]●[/red] OFFLINE"
        layout["footer"].update(Panel(
            f"[dim]⏱️  {now} | {api_status} | Markets: {len(self.markets)} | Scan #{self.scan_count} | Ctrl+C to exit[/dim]",
            border_style="dim"
        ))

        return layout

    def _build_scanner_panel(self):
        """Build the scanner visualization"""
        if not self.edge_data:
            return Align.center(Text.from_markup("""
[bold yellow]
   ⣾⣿⣿⣿⣿⣷
   ⣿⣿⣿⣿⣿⣿
   ⣿⣿⣿⣿⣿⣿     INITIALIZING SCANNER...
   ⣿⣿⣿⣿⣿⣿
   ⢿⣿⣿⣿⣿⡿
[/bold yellow]
"""))

        e = self.edge_data

        edge_bar = self._make_edge_bar(e['implied_edge'])
        winrate_bar = self._make_winrate_bar(e['win_rate'])

        signal_color = e['signal_color']

        content = f"""
[bold white]CURRENT MARKET:[/bold white]
[cyan]╔{'═' * 60}╗
║ {e['question']:<58} ║
╚{'═' * 60}╝[/cyan]

[bold]Category:[/bold] [magenta]{e['market_type'].upper()}[/magenta]
[bold]Yes Price:[/bold] [yellow]${e['yes_price']:.2f}[/yellow]
[bold]Historical Edge:[/bold] {'[green]YES[/green]' if e['has_edge'] else '[red]NO[/red]'}

[bold white]═══════════════ EDGE ANALYSIS ═══════════════[/bold white]

  Historical Win Rate: {winrate_bar}  [{e['win_rate']:.1f}%]
  Implied Edge:        {edge_bar}  [{'+' if e['implied_edge'] > 0 else ''}{e['implied_edge']*100:.1f}%]
  Avg P&L per Trade:   [{'green' if e['avg_pnl'] >= 0 else 'red'}]${e['avg_pnl']:.2f}[/{'green' if e['avg_pnl'] >= 0 else 'red'}]

[bold white]═══════════════════════════════════════════[/bold white]

                    ╔═══════════════════╗
                    ║ [{signal_color}]SIGNAL: {e['signal']:^8}[/{signal_color}] ║
                    ╚═══════════════════╝
"""
        return content

    def _make_edge_bar(self, edge):
        """Create edge visualization bar"""
        width = 30
        center = width // 2

        if edge > 0:
            fill = min(int(edge * 200), center)
            bar = "░" * center + "[green]" + "█" * fill + "[/green]" + "░" * (center - fill)
        else:
            fill = min(int(abs(edge) * 200), center)
            bar = "░" * (center - fill) + "[red]" + "█" * fill + "[/red]" + "░" * center

        return f"[{bar}]"

    def _make_winrate_bar(self, winrate):
        """Create win rate bar"""
        width = 30
        filled = int(winrate / 100 * width)

        if winrate >= 55:
            color = "green"
        elif winrate >= 45:
            color = "yellow"
        else:
            color = "red"

        bar = f"[{color}]" + "█" * filled + f"[/{color}]" + "░" * (width - filled)
        return f"[{bar}]"

    def _build_edge_panel(self):
        """Build edge detection summary"""
        if not self.edge_by_type:
            return "[dim]No historical data yet[/dim]"

        lines = []
        for mtype, data in sorted(self.edge_by_type.items()):
            edge_icon = "[green]✓[/green]" if data['has_edge'] else "[red]✗[/red]"
            pnl_color = "green" if data['avg_pnl'] >= 0 else "red"

            lines.append(
                f"{edge_icon} [cyan]{mtype:12}[/cyan] "
                f"{data['win_rate']:5.1f}% "
                f"[{pnl_color}]${data['avg_pnl']:+.2f}[/{pnl_color}]"
            )

        return "\n".join(lines) if lines else "[dim]No data[/dim]"


def main():
    console.clear()
    scanner = RealMarketScanner()

    with Live(scanner.generate_display(), refresh_per_second=2, screen=True) as live:
        try:
            while True:
                time.sleep(2)
                scanner.scan_next_market()
                live.update(scanner.generate_display())

        except KeyboardInterrupt:
            pass

    console.print(f"\n[bold green]Scanner stopped. Found {scanner.opportunities_found} opportunities! 🎯[/bold green]")


if __name__ == "__main__":
    main()
