# Position Manager & Exit Strategy System

## Overview

The Position Manager implements comprehensive exit strategies to prevent massive losses and lock in profits. It tracks all open positions in real-time and automatically executes exits based on configurable conditions.

## Features

### 1. Real-Time Position Tracking
- Tracks entry price, current price, PnL
- Monitors hold duration
- Updates highest price for trailing stops
- Persistent storage (survives restarts)

### 2. Multiple Exit Strategies

#### Take Profit
- Exit when profit reaches target percentage
- Default: +20%
- Configurable via `TAKE_PROFIT_PCT`

#### Stop Loss
- Exit when loss reaches maximum limit
- Default: -10%
- Configurable via `STOP_LOSS_PCT`

#### Time-Based Exit
- Exit after holding for maximum duration
- Default: 72 hours
- Configurable via `MAX_HOLD_HOURS`

#### Trailing Stop
- Lock in profits as price moves up
- Exit if price drops from peak
- Default: -5% from highest price
- Configurable via `TRAILING_STOP_PCT`

#### Target Price
- Exit when specific price reached
- Useful for event-based markets
- Set per-position

### 3. Performance Metrics
- Win rate
- Average profit/loss
- Total PnL
- Best/worst trades
- Average hold duration

## Configuration

Add to `.env`:

```bash
# Exit Strategy Configuration
TAKE_PROFIT_PCT="20.0"      # Exit at +20% profit
STOP_LOSS_PCT="10.0"        # Exit at -10% loss
MAX_HOLD_HOURS="72"         # Exit after 72 hours
TRAILING_STOP_PCT="5.0"     # Trail by 5%
ENABLE_AUTO_EXIT="true"     # Auto-execute exits
```

## Usage

### Basic Example

```python
from agents.application.position_manager import PositionManager

# Initialize
manager = PositionManager()

# Open position (after placing order)
position = manager.open_position(
    market_id="0x123...",
    market_question="Will Bitcoin reach $100k in 2024?",
    outcome="YES",
    entry_price=0.65,
    quantity=100,
    order_id="order_123"
)

# Update with current price (in main loop)
exit_signal = manager.update_position("0x123...", 0.78)

if exit_signal and exit_signal[0]:
    print(f"Exit triggered: {exit_signal[1]}")
    # Position automatically closed if ENABLE_AUTO_EXIT=true

# Check performance
metrics = manager.get_performance_metrics()
print(f"Win rate: {metrics['win_rate']:.1f}%")
print(f"Total PnL: ${metrics['total_pnl']:+.2f}")
```

### Integration with Continuous Trader

The position manager is integrated into `continuous_trader.py`:

1. **Initialize** on startup
2. **Track** positions from trades
3. **Check** every 30 seconds for exits
4. **Execute** exits automatically
5. **Report** metrics every 10 iterations

## Exit Strategy Presets

### Aggressive (Fast Profits, Tight Stops)
```python
from agents.application.exit_strategies import AggressiveExitStrategy

strategy = AggressiveExitStrategy()
# Take Profit: +10%
# Stop Loss: -5%
# Max Hold: 24h
# Trailing Stop: 3%
```

### Balanced (Moderate Risk/Reward)
```python
from agents.application.exit_strategies import BalancedExitStrategy

strategy = BalancedExitStrategy()
# Take Profit: +20%
# Stop Loss: -10%
# Max Hold: 72h
# Trailing Stop: 5%
```

### Conservative (Patient Approach)
```python
from agents.application.exit_strategies import ConservativeExitStrategy

strategy = ConservativeExitStrategy()
# Take Profit: +30%
# Stop Loss: -15%
# Max Hold: 168h (7 days)
# Trailing Stop: 10%
```

## Data Storage

Positions are persisted to `data/positions.json`:

```json
{
  "open_positions": [
    {
      "market_id": "0x123...",
      "market_question": "Will Bitcoin reach $100k?",
      "outcome": "YES",
      "entry_price": 0.65,
      "quantity": 100,
      "entry_timestamp": "2024-01-08T10:30:00",
      "current_price": 0.70,
      "unrealized_pnl": 5.0,
      "unrealized_pnl_pct": 7.69
    }
  ],
  "closed_positions": [...]
}
```

## Performance Impact

### Expected Improvements
- **Cuts losses early**: Stop loss prevents -50% losses
- **Takes profits**: Captures gains before market reverses
- **Prevents time decay**: Exits stale positions
- **Locks profits**: Trailing stop protects gains

### Real-World Example
**Without Position Manager:**
- Entry: $0.50, Hold until resolution at $0.35
- Loss: -$15 (-30%)

**With Position Manager:**
- Entry: $0.50, Stop Loss at $0.45
- Loss: -$5 (-10%)
- **Saves: $10 (67% loss reduction!)**

## Testing

Run comprehensive tests:

```bash
cd /home/tony/Dev/agents
python tests/test_position_manager.py
```

Tests cover:
- Position tracking
- Exit strategy logic
- Performance metrics
- Persistence
- Edge cases

## Monitoring

The position manager provides detailed logging:

```
📈 POSITION OPENED
   Market: Will Bitcoin reach $100k in 2024?...
   Outcome: YES
   Entry: $0.6500 x 100 shares
   Cost: $65.00

🚨 EXIT SIGNAL TRIGGERED
   Market: Will Bitcoin reach $100k in 2024?...
   Reason: Take Profit: +20.0% (target: +20%)
   PnL: $13.00 (+20.0%)

✅ POSITION CLOSED
   Market: Will Bitcoin reach $100k in 2024?...
   Entry: $0.6500
   Exit: $0.7800
   PnL: $13.00 (+20.0%)
   Reason: Take Profit
   Duration: 12.5h
```

## Next Steps

### Phase 1: API Integration
- Connect to Polymarket API for real-time prices
- Execute sell orders automatically
- Handle order failures and retries

### Phase 2: Advanced Features
- Dynamic stop loss adjustment
- Partial position exits
- Position sizing based on confidence
- Risk-adjusted exits

### Phase 3: Machine Learning
- Learn optimal exit timing
- Predict reversal points
- Adaptive strategy selection

## Troubleshooting

### Positions Not Exiting
- Check `ENABLE_AUTO_EXIT=true` in `.env`
- Verify position manager is initialized
- Check logs for errors

### Wrong Exit Prices
- Ensure current prices are updated
- Verify exit logic with tests
- Check for API price delays

### Performance Issues
- Use `position_manager.print_status()` to debug
- Check storage file permissions
- Monitor for memory leaks

## Support

For issues or questions:
1. Check logs in `/tmp/continuous_trader.log`
2. Run tests to verify functionality
3. Review position data in `data/positions.json`
4. Enable debug logging if needed

## License

MIT License - See LICENSE file for details
