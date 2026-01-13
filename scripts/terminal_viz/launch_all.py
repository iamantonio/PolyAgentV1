#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 TERMINAL VIZ LAUNCHER 🚀                                ║
║                    Opens each visualization in its own terminal               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python launch_all.py           # Launch all visualizations
    python launch_all.py --select  # Interactive selection
    python launch_all.py --list    # List available visualizations
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Get the directory of this script
SCRIPT_DIR = Path(__file__).parent

# Available visualizations
VISUALIZATIONS = {
    "1": {
        "name": "Live Dashboard",
        "file": "live_dashboard.py",
        "description": "Real-time trading performance metrics",
        "icon": "📊"
    },
    "2": {
        "name": "Market Scanner",
        "file": "market_scanner.py",
        "description": "Live market analysis visualization",
        "icon": "🔍"
    },
    "3": {
        "name": "Neural Training",
        "file": "neural_training.py",
        "description": "ML model training visualization",
        "icon": "🧠"
    },
    "4": {
        "name": "Position Monitor",
        "file": "position_monitor.py",
        "description": "Live position & P&L tracking",
        "icon": "💰"
    },
    "5": {
        "name": "Calibration Chart",
        "file": "calibration_chart.py",
        "description": "Prediction accuracy analysis",
        "icon": "📈"
    },
    "6": {
        "name": "System Matrix",
        "file": "system_matrix.py",
        "description": "Cyberpunk system monitor",
        "icon": "🖥️"
    }
}


def detect_terminal():
    """Detect available terminal emulators"""
    terminals = [
        ("gnome-terminal", ["gnome-terminal", "--", "bash", "-c"]),
        ("konsole", ["konsole", "-e", "bash", "-c"]),
        ("xfce4-terminal", ["xfce4-terminal", "-e"]),
        ("xterm", ["xterm", "-e", "bash", "-c"]),
        ("terminator", ["terminator", "-e"]),
        ("alacritty", ["alacritty", "-e", "bash", "-c"]),
        ("kitty", ["kitty", "bash", "-c"]),
        ("tilix", ["tilix", "-e", "bash", "-c"]),
        ("urxvt", ["urxvt", "-e", "bash", "-c"]),
    ]

    for name, cmd in terminals:
        if shutil.which(name):
            return name, cmd

    return None, None


def launch_in_terminal(script_path: str, title: str, terminal_cmd: list):
    """Launch a script in a new terminal window"""
    python_cmd = sys.executable
    full_cmd = f"echo -e '\\033]0;{title}\\007'; {python_cmd} {script_path}; read -p 'Press Enter to close...'"

    if "gnome-terminal" in terminal_cmd[0]:
        # gnome-terminal has different syntax
        cmd = ["gnome-terminal", f"--title={title}", "--", "bash", "-c", full_cmd]
    elif "konsole" in terminal_cmd[0]:
        cmd = ["konsole", f"--title={title}", "-e", "bash", "-c", full_cmd]
    elif "kitty" in terminal_cmd[0]:
        cmd = ["kitty", "--title", title, "bash", "-c", full_cmd]
    elif "alacritty" in terminal_cmd[0]:
        cmd = ["alacritty", "--title", title, "-e", "bash", "-c", full_cmd]
    else:
        # Generic fallback
        cmd = terminal_cmd + [full_cmd]

    try:
        subprocess.Popen(cmd, start_new_session=True)
        return True
    except Exception as e:
        print(f"  ❌ Failed to launch: {e}")
        return False


def print_header():
    """Print fancy header"""
    print("\033[36m")  # Cyan
    print("╔" + "═" * 60 + "╗")
    print("║" + " 🚀 TERMINAL VISUALIZATION LAUNCHER 🚀 ".center(60) + "║")
    print("║" + " " * 60 + "║")
    print("║" + " Launch trading bot visualizations in separate terminals ".center(60) + "║")
    print("╚" + "═" * 60 + "╝")
    print("\033[0m")  # Reset


def list_visualizations():
    """List all available visualizations"""
    print_header()
    print("\n\033[33mAvailable Visualizations:\033[0m\n")

    for key, viz in VISUALIZATIONS.items():
        print(f"  \033[36m[{key}]\033[0m {viz['icon']} {viz['name']}")
        print(f"      \033[90m{viz['description']}\033[0m")
        print()


def interactive_select():
    """Interactive visualization selector"""
    print_header()
    print("\n\033[33mSelect visualizations to launch:\033[0m\n")

    for key, viz in VISUALIZATIONS.items():
        print(f"  \033[36m[{key}]\033[0m {viz['icon']} {viz['name']} - {viz['description']}")

    print(f"\n  \033[36m[a]\033[0m 🎯 Launch ALL")
    print(f"  \033[36m[q]\033[0m ❌ Quit")

    print("\n\033[33mEnter your choice (e.g., '123' for multiple, 'a' for all):\033[0m ", end="")
    choice = input().strip().lower()

    if choice == 'q':
        print("\n\033[90mExiting...\033[0m")
        return []
    elif choice == 'a':
        return list(VISUALIZATIONS.keys())
    else:
        return [c for c in choice if c in VISUALIZATIONS]


def launch_visualizations(selections: list, terminal_name: str, terminal_cmd: list):
    """Launch selected visualizations"""
    print(f"\n\033[32m🖥️  Using terminal: {terminal_name}\033[0m\n")

    launched = 0
    for key in selections:
        viz = VISUALIZATIONS.get(key)
        if viz:
            script_path = SCRIPT_DIR / viz["file"]
            if script_path.exists():
                print(f"  {viz['icon']} Launching {viz['name']}...", end=" ")
                if launch_in_terminal(str(script_path), viz['name'], terminal_cmd):
                    print("\033[32m✓\033[0m")
                    launched += 1
            else:
                print(f"  ❌ Script not found: {script_path}")

    print(f"\n\033[32m✅ Launched {launched} visualization(s)\033[0m")
    print("\033[90mEach visualization runs in its own terminal window.\033[0m")
    print("\033[90mPress Ctrl+C in any window to close it.\033[0m\n")


def main():
    # Detect terminal
    terminal_name, terminal_cmd = detect_terminal()

    if not terminal_name:
        print("\033[31m❌ No supported terminal emulator found!\033[0m")
        print("\033[90mSupported: gnome-terminal, konsole, xterm, alacritty, kitty, xfce4-terminal, terminator\033[0m")
        print("\nYou can run visualizations directly:")
        for key, viz in VISUALIZATIONS.items():
            print(f"  python {SCRIPT_DIR}/{viz['file']}")
        sys.exit(1)

    # Parse arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == "--list":
            list_visualizations()
            return

        elif arg == "--select":
            selections = interactive_select()
            if selections:
                launch_visualizations(selections, terminal_name, terminal_cmd)

        elif arg.isdigit():
            # Direct number selection
            selections = [c for c in arg if c in VISUALIZATIONS]
            if selections:
                launch_visualizations(selections, terminal_name, terminal_cmd)
            else:
                print("\033[31m❌ Invalid selection\033[0m")
                list_visualizations()

        else:
            print(f"\033[31m❌ Unknown argument: {arg}\033[0m")
            print("\nUsage:")
            print("  python launch_all.py           # Launch all")
            print("  python launch_all.py --select  # Interactive selection")
            print("  python launch_all.py --list    # List available")
            print("  python launch_all.py 123       # Launch specific (by number)")

    else:
        # Launch all by default
        print_header()
        print(f"\n\033[33mLaunching all visualizations...\033[0m")
        launch_visualizations(list(VISUALIZATIONS.keys()), terminal_name, terminal_cmd)


if __name__ == "__main__":
    main()
