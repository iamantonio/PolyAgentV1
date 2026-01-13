# Terminal Visualization Guidelines

## CRITICAL: No Mock Data - Ever

**User preference (added 2025-01-12):**
- NEVER use mock/simulated/fake data in visualizations or tools
- ALL data must come from real sources:
  - Real Polymarket API (Gamma API) for market data
  - Real database (`~/.polymarket/learning_trader.db`) for trading data
  - Real system metrics (psutil) for system stats
  - Real training from actual prediction history

## Available Visualizations

All in `/scripts/terminal_viz/`:

1. **live_dashboard.py** - Real P&L, positions, trades from DB
2. **market_scanner.py** - Real markets from Polymarket Gamma API + edge from DB
3. **neural_training.py** - Real isotonic calibration training on actual trades
4. **position_monitor.py** - Real positions from DB
5. **calibration_chart.py** - Real calibration curve from DB
6. **system_matrix.py** - Real CPU/memory/processes via psutil

## Launch Commands

```bash
# Launch all
./scripts/terminal_viz/launch.sh --all

# Interactive menu
./scripts/terminal_viz/launch.sh

# Specific ones
./scripts/terminal_viz/launch.sh 136
```
