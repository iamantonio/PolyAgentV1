#!/home/tony/Dev/agents/.venv/bin/python
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🖥️  SYSTEM MATRIX 🖥️                                       ║
║                    Cyberpunk system monitor                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import random
import psutil
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.table import Table
from rich.align import Align
from rich import box

console = Console()

# Matrix-style header
HEADER = """
[bold green]
░██████╗██╗░░░██╗░██████╗████████╗███████╗███╗░░░███╗
██╔════╝╚██╗░██╔╝██╔════╝╚══██╔══╝██╔════╝████╗░████║
╚█████╗░░╚████╔╝░╚█████╗░░░░██║░░░█████╗░░██╔████╔██║
░╚═══██╗░░╚██╔╝░░░╚═══██╗░░░██║░░░██╔══╝░░██║╚██╔╝██║
██████╔╝░░░██║░░░██████╔╝░░░██║░░░███████╗██║░╚═╝░██║
╚═════╝░░░░╚═╝░░░╚═════╝░░░░╚═╝░░░╚══════╝╚═╝░░░░░╚═╝
[/bold green]
[bold green]███╗░░░███╗░█████╗░████████╗██████╗░██╗██╗░░██╗[/bold green]
[bold green]████╗░████║██╔══██╗╚══██╔══╝██╔══██╗██║╚██╗██╔╝[/bold green]
[bold green]██╔████╔██║███████║░░░██║░░░██████╔╝██║░╚███╔╝░[/bold green]
[bold green]██║╚██╔╝██║██╔══██║░░░██║░░░██╔══██╗██║░██╔██╗░[/bold green]
[bold green]██║░╚═╝░██║██║░░██║░░░██║░░░██║░░██║██║██╔╝╚██╗[/bold green]
[bold green]╚═╝░░░░░╚═╝╚═╝░░╚═╝░░░╚═╝░░░╚═╝░░╚═╝╚═╝╚═╝░░╚═╝[/bold green]
"""


class SystemMatrix:
    def __init__(self):
        self.matrix_rain = []
        self.width = 60
        self.height = 15
        self.tick = 0

        # Initialize matrix rain columns
        for _ in range(self.width):
            self.matrix_rain.append({
                "pos": random.randint(-self.height, 0),
                "speed": random.randint(1, 3),
                "chars": [random.choice("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789") for _ in range(self.height)]
            })

        self.cpu_history = []
        self.mem_history = []
        self.net_history = []

    def update_matrix(self):
        """Update matrix rain animation"""
        for col in self.matrix_rain:
            col["pos"] += col["speed"]
            if col["pos"] > self.height + 5:
                col["pos"] = random.randint(-self.height, -5)
                col["speed"] = random.randint(1, 3)
                col["chars"] = [random.choice("アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789") for _ in range(self.height)]

    def render_matrix(self):
        """Render matrix rain"""
        lines = []
        for y in range(self.height):
            line = ""
            for x, col in enumerate(self.matrix_rain[:self.width]):
                char_idx = y - col["pos"]
                if 0 <= char_idx < len(col["chars"]):
                    if char_idx == 0:
                        line += f"[bold white]{col['chars'][char_idx]}[/bold white]"
                    elif char_idx < 3:
                        line += f"[bold green]{col['chars'][char_idx]}[/bold green]"
                    elif char_idx < 6:
                        line += f"[green]{col['chars'][char_idx]}[/green]"
                    else:
                        line += f"[dim green]{col['chars'][char_idx]}[/dim green]"
                else:
                    line += " "
            lines.append(line)
        return "\n".join(lines)

    def get_system_stats(self):
        """Get real system statistics"""
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()

        self.cpu_history.append(cpu)
        self.mem_history.append(mem.percent)

        if len(self.cpu_history) > 30:
            self.cpu_history.pop(0)
            self.mem_history.pop(0)

        try:
            net = psutil.net_io_counters()
            net_sent = net.bytes_sent / 1024 / 1024  # MB
            net_recv = net.bytes_recv / 1024 / 1024  # MB
        except:
            net_sent = net_recv = 0

        return {
            "cpu": cpu,
            "mem_percent": mem.percent,
            "mem_used": mem.used / 1024 / 1024 / 1024,  # GB
            "mem_total": mem.total / 1024 / 1024 / 1024,  # GB
            "net_sent": net_sent,
            "net_recv": net_recv,
        }

    def make_sparkline(self, values, width=20):
        """Create sparkline"""
        if not values:
            return "─" * width

        chars = "▁▂▃▄▅▆▇█"
        min_v = min(values)
        max_v = max(values)

        if max_v == min_v:
            return chars[4] * min(len(values), width)

        result = ""
        for v in values[-width:]:
            idx = int((v - min_v) / (max_v - min_v) * (len(chars) - 1))
            result += chars[idx]

        return result

    def make_bar(self, value, max_val=100, width=25):
        """Create progress bar"""
        filled = int((value / max_val) * width)

        if value > 80:
            color = "red"
        elif value > 60:
            color = "yellow"
        else:
            color = "green"

        bar = f"[{color}]{'█' * filled}[/{color}]{'░' * (width - filled)}"
        return bar

    def generate_display(self):
        """Generate the display"""
        self.tick += 1
        self.update_matrix()
        stats = self.get_system_stats()

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=6),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )

        layout["main"].split_row(
            Layout(name="matrix", ratio=2),
            Layout(name="stats")
        )

        layout["stats"].split_column(
            Layout(name="system", size=16),
            Layout(name="processes")
        )

        # Header
        header_text = f"""
[bold green]╔═══════════════════════════════════════════════════════════════════╗
║  SYSTEM MATRIX v2.0  │  NEURAL INTERFACE ACTIVE  │  ⚡ LIVE      ║
╚═══════════════════════════════════════════════════════════════════╝[/bold green]
"""
        layout["header"].update(Panel(header_text, border_style="green"))

        # Matrix rain
        matrix_content = self.render_matrix()
        layout["matrix"].update(Panel(
            matrix_content,
            title="[bold green]◉ NEURAL DATASTREAM[/bold green]",
            border_style="green",
            box=box.DOUBLE
        ))

        # System stats
        cpu_spark = self.make_sparkline(self.cpu_history)
        mem_spark = self.make_sparkline(self.mem_history)

        stats_content = f"""
[bold cyan]┌─ CPU ────────────────────────┐[/bold cyan]
│ {self.make_bar(stats['cpu'])} {stats['cpu']:5.1f}%
│ [green]{cpu_spark}[/green]
[bold cyan]└──────────────────────────────┘[/bold cyan]

[bold magenta]┌─ MEMORY ─────────────────────┐[/bold magenta]
│ {self.make_bar(stats['mem_percent'])} {stats['mem_percent']:5.1f}%
│ [magenta]{mem_spark}[/magenta]
│ {stats['mem_used']:.1f} GB / {stats['mem_total']:.1f} GB
[bold magenta]└──────────────────────────────┘[/bold magenta]

[bold yellow]┌─ NETWORK ────────────────────┐[/bold yellow]
│ ▲ {stats['net_sent']:,.0f} MB sent
│ ▼ {stats['net_recv']:,.0f} MB recv
[bold yellow]└──────────────────────────────┘[/bold yellow]
"""
        layout["system"].update(Panel(
            stats_content,
            title="[bold cyan]⚙ SYSTEM[/bold cyan]",
            border_style="cyan"
        ))

        # Top processes
        proc_table = Table(
            show_header=True,
            header_style="bold green",
            border_style="green",
            box=box.SIMPLE
        )
        proc_table.add_column("PID", style="dim")
        proc_table.add_column("Process", style="green")
        proc_table.add_column("CPU%", justify="right")
        proc_table.add_column("MEM%", justify="right")

        try:
            procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    if info['cpu_percent'] is not None:
                        procs.append(info)
                except:
                    pass

            # Sort by CPU and get top 5
            procs.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)

            for p in procs[:5]:
                proc_table.add_row(
                    str(p['pid']),
                    (p['name'] or "")[:15],
                    f"{p['cpu_percent']:.1f}",
                    f"{p['memory_percent']:.1f}"
                )
        except:
            proc_table.add_row("--", "Unable to read", "--", "--")

        layout["processes"].update(Panel(
            proc_table,
            title="[bold green]◎ TOP PROCESSES[/bold green]",
            border_style="green"
        ))

        # Footer
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uptime = ""
        try:
            boot = datetime.fromtimestamp(psutil.boot_time())
            uptime_delta = datetime.now() - boot
            hours = int(uptime_delta.total_seconds() // 3600)
            mins = int((uptime_delta.total_seconds() % 3600) // 60)
            uptime = f"Uptime: {hours}h {mins}m"
        except:
            pass

        layout["footer"].update(Panel(
            f"[dim green]⏱️  {now} | {uptime} | Tick: {self.tick} | Press Ctrl+C to exit[/dim green]",
            border_style="green"
        ))

        return layout


def main():
    console.clear()
    matrix = SystemMatrix()

    with Live(matrix.generate_display(), refresh_per_second=10, screen=True) as live:
        try:
            while True:
                time.sleep(0.1)
                live.update(matrix.generate_display())
        except KeyboardInterrupt:
            pass

    console.print("\n[bold green]System Matrix disconnected. ◉[/bold green]")


if __name__ == "__main__":
    main()
