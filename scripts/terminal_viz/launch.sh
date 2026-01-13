#!/bin/bash
#╔══════════════════════════════════════════════════════════════════════════════╗
#║                    🚀 TERMINAL VIZ LAUNCHER 🚀                                ║
#║                    Opens visualizations in separate terminals                 ║
#╚══════════════════════════════════════════════════════════════════════════════╝

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Detect terminal emulator
detect_terminal() {
    if command -v gnome-terminal &> /dev/null; then
        echo "gnome-terminal"
    elif command -v konsole &> /dev/null; then
        echo "konsole"
    elif command -v xfce4-terminal &> /dev/null; then
        echo "xfce4-terminal"
    elif command -v alacritty &> /dev/null; then
        echo "alacritty"
    elif command -v kitty &> /dev/null; then
        echo "kitty"
    elif command -v xterm &> /dev/null; then
        echo "xterm"
    else
        echo ""
    fi
}

# Launch in new terminal
launch() {
    local script="$1"
    local title="$2"
    local terminal=$(detect_terminal)

    if [[ -z "$terminal" ]]; then
        echo -e "${RED}❌ No terminal emulator found${NC}"
        return 1
    fi

    echo -e "${CYAN}  🖥️  Launching ${title}...${NC}"

    case "$terminal" in
        gnome-terminal)
            gnome-terminal --title="$title" -- bash -c "/home/tony/Dev/agents/.venv/bin/python $script; read -p 'Press Enter to close...'"
            ;;
        konsole)
            konsole --title="$title" -e bash -c "/home/tony/Dev/agents/.venv/bin/python $script; read -p 'Press Enter to close...'"
            ;;
        xfce4-terminal)
            xfce4-terminal --title="$title" -e "bash -c '/home/tony/Dev/agents/.venv/bin/python $script; read -p \"Press Enter to close...\"'"
            ;;
        alacritty)
            alacritty --title "$title" -e bash -c "/home/tony/Dev/agents/.venv/bin/python $script; read -p 'Press Enter to close...'" &
            ;;
        kitty)
            kitty --title "$title" bash -c "/home/tony/Dev/agents/.venv/bin/python $script; read -p 'Press Enter to close...'" &
            ;;
        xterm)
            xterm -title "$title" -e "bash -c '/home/tony/Dev/agents/.venv/bin/python $script; read -p \"Press Enter to close...\"'" &
            ;;
    esac
}

# Print menu
print_menu() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║        🚀 TERMINAL VISUALIZATION LAUNCHER 🚀                ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "${YELLOW}Select visualization(s) to launch:${NC}"
    echo ""
    echo -e "  ${CYAN}[1]${NC} 📊 Live Dashboard      - Trading performance metrics"
    echo -e "  ${CYAN}[2]${NC} 🔍 Market Scanner      - Real-time market analysis"
    echo -e "  ${CYAN}[3]${NC} 🧠 Neural Training     - ML training visualization"
    echo -e "  ${CYAN}[4]${NC} 💰 Position Monitor    - Live P&L tracking"
    echo -e "  ${CYAN}[5]${NC} 📈 Calibration Chart   - Prediction accuracy"
    echo -e "  ${CYAN}[6]${NC} 🖥️  System Matrix       - Cyberpunk system monitor"
    echo ""
    echo -e "  ${CYAN}[a]${NC} 🎯 Launch ALL"
    echo -e "  ${CYAN}[q]${NC} ❌ Quit"
    echo ""
}

# Main
main() {
    local terminal=$(detect_terminal)

    if [[ -z "$terminal" ]]; then
        echo -e "${RED}❌ No supported terminal emulator found!${NC}"
        echo "Supported: gnome-terminal, konsole, xfce4-terminal, alacritty, kitty, xterm"
        exit 1
    fi

    print_menu

    echo -ne "${YELLOW}Enter choice (e.g., '123' for multiple, 'a' for all): ${NC}"
    read -r choice

    if [[ "$choice" == "q" ]]; then
        echo -e "${NC}Goodbye! 👋${NC}"
        exit 0
    fi

    echo ""
    echo -e "${GREEN}🚀 Launching visualizations using $terminal...${NC}"
    echo ""

    # Launch based on choice
    if [[ "$choice" == "a" || "$choice" == "A" ]]; then
        choice="123456"
    fi

    [[ "$choice" == *"1"* ]] && launch "$SCRIPT_DIR/live_dashboard.py" "Live Dashboard"
    [[ "$choice" == *"2"* ]] && launch "$SCRIPT_DIR/market_scanner.py" "Market Scanner"
    [[ "$choice" == *"3"* ]] && launch "$SCRIPT_DIR/neural_training.py" "Neural Training"
    [[ "$choice" == *"4"* ]] && launch "$SCRIPT_DIR/position_monitor.py" "Position Monitor"
    [[ "$choice" == *"5"* ]] && launch "$SCRIPT_DIR/calibration_chart.py" "Calibration Chart"
    [[ "$choice" == *"6"* ]] && launch "$SCRIPT_DIR/system_matrix.py" "System Matrix"

    echo ""
    echo -e "${GREEN}✅ Done! Each visualization runs in its own terminal.${NC}"
    echo -e "${NC}Press Ctrl+C in any window to close it.${NC}"
}

# Run with optional argument
if [[ "$1" == "--all" || "$1" == "-a" ]]; then
    terminal=$(detect_terminal)
    echo -e "${GREEN}🚀 Launching all visualizations...${NC}"
    launch "$SCRIPT_DIR/live_dashboard.py" "Live Dashboard"
    sleep 0.3
    launch "$SCRIPT_DIR/market_scanner.py" "Market Scanner"
    sleep 0.3
    launch "$SCRIPT_DIR/neural_training.py" "Neural Training"
    sleep 0.3
    launch "$SCRIPT_DIR/position_monitor.py" "Position Monitor"
    sleep 0.3
    launch "$SCRIPT_DIR/calibration_chart.py" "Calibration Chart"
    sleep 0.3
    launch "$SCRIPT_DIR/system_matrix.py" "System Matrix"
    echo -e "${GREEN}✅ All visualizations launched!${NC}"
elif [[ -n "$1" ]]; then
    # Direct number selection
    terminal=$(detect_terminal)
    choice="$1"
    [[ "$choice" == *"1"* ]] && launch "$SCRIPT_DIR/live_dashboard.py" "Live Dashboard"
    [[ "$choice" == *"2"* ]] && launch "$SCRIPT_DIR/market_scanner.py" "Market Scanner"
    [[ "$choice" == *"3"* ]] && launch "$SCRIPT_DIR/neural_training.py" "Neural Training"
    [[ "$choice" == *"4"* ]] && launch "$SCRIPT_DIR/position_monitor.py" "Position Monitor"
    [[ "$choice" == *"5"* ]] && launch "$SCRIPT_DIR/calibration_chart.py" "Calibration Chart"
    [[ "$choice" == *"6"* ]] && launch "$SCRIPT_DIR/system_matrix.py" "System Matrix"
else
    main
fi
