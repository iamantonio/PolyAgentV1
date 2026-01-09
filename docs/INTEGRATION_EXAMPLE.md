# Position Manager Integration Example

## How to Integrate with Trading Bots

### Step 1: Initialize Position Manager

Add to your trading bot's `__init__`:

```python
from agents.application.position_manager import PositionManager

class YourTradingBot:
    def __init__(self):
        self.position_manager = PositionManager()
        # ... other initialization
```

### Step 2: Record Positions After Trades

When you place a BUY order:

```python
def execute_trade(self, market_id, market_question, outcome, price, quantity):
    """Execute a trade and record position."""

    # Place order via Polymarket API
    order = self.place_order(
        market_id=market_id,
        outcome=outcome,
        price=price,
        quantity=quantity,
        side="BUY"
    )

    # Record position with manager
    position = self.position_manager.open_position(
        market_id=market_id,
        market_question=market_question,
        outcome=outcome,
        entry_price=price,
        quantity=quantity,
        order_id=order['id']
    )

    print(f"✅ Position opened: {position.market_id}")
    return order
```

### Step 3: Check Positions in Main Loop

Add position checking to your main trading loop:

```python
def main_loop(self):
    """Main trading loop with position management."""

    while True:
        # 1. Check existing positions for exits
        self.check_positions()

        # 2. Look for new opportunities
        self.scan_for_trades()

        # 3. Wait before next iteration
        time.sleep(30)
```

### Step 4: Update Positions with Current Prices

```python
def check_positions(self):
    """Check all open positions and execute exits."""

    open_positions = self.position_manager.get_open_positions()

    for position in open_positions:
        # Get current price from Polymarket API
        current_price = self.get_market_price(position.market_id, position.outcome)

        # Update position and check for exits
        exit_signal = self.position_manager.update_position(
            position.market_id,
            current_price
        )

        if exit_signal and exit_signal[0]:
            # Exit triggered!
            print(f"🚨 Exit signal: {exit_signal[1]}")

            # Position automatically closed if ENABLE_AUTO_EXIT=true
            # Otherwise, manually execute exit:
            if not self.config['enable_auto_exit']:
                self.execute_exit(position, current_price, exit_signal[1])
```

### Step 5: Execute Exit Orders

```python
def execute_exit(self, position, exit_price, reason):
    """Execute exit order for position."""

    try:
        # Place SELL order via Polymarket API
        order = self.place_order(
            market_id=position.market_id,
            outcome=position.outcome,
            price=exit_price,
            quantity=position.quantity,
            side="SELL"
        )

        # Mark position as closed
        self.position_manager.execute_exit(position, exit_price, reason)

        print(f"✅ Exit executed: ${position.realized_pnl:+.2f}")

    except Exception as e:
        print(f"❌ Exit failed: {e}")
```

### Step 6: Monitor Performance

Add performance reporting:

```python
def print_performance(self):
    """Print performance metrics."""

    metrics = self.position_manager.get_performance_metrics()

    print(f"\n📊 PERFORMANCE SUMMARY")
    print(f"Total Trades: {metrics['total_positions']}")
    print(f"Win Rate: {metrics['win_rate']:.1f}%")
    print(f"Total PnL: ${metrics['total_pnl']:+.2f}")
    print(f"Avg Profit: ${metrics['avg_profit']:+.2f}")
    print(f"Avg Loss: ${metrics['avg_loss']:+.2f}")
    print(f"Best Trade: ${metrics['best_trade']:+.2f}")
    print(f"Worst Trade: ${metrics['worst_trade']:+.2f}")
```

## Complete Example

Here's a complete minimal trading bot with position management:

```python
#!/usr/bin/env python3
"""
Simple trading bot with position management.
"""

import os
import time
from agents.application.position_manager import PositionManager

class SimpleTradingBot:
    def __init__(self):
        self.position_manager = PositionManager()
        self.running = False

    def get_market_price(self, market_id, outcome):
        """Get current market price from Polymarket API."""
        # TODO: Implement API call
        # For now, return mock price
        return 0.65

    def place_order(self, market_id, outcome, price, quantity, side):
        """Place order via Polymarket API."""
        # TODO: Implement API call
        return {
            'id': f'order_{int(time.time())}',
            'status': 'filled',
            'filled_price': price
        }

    def scan_for_trades(self):
        """Scan for new trading opportunities."""
        # TODO: Implement your strategy
        pass

    def check_positions(self):
        """Check positions and execute exits."""
        positions = self.position_manager.get_open_positions()

        for position in positions:
            current_price = self.get_market_price(
                position.market_id,
                position.outcome
            )

            exit_signal = self.position_manager.update_position(
                position.market_id,
                current_price
            )

            if exit_signal and exit_signal[0]:
                print(f"Exit triggered: {exit_signal[1]}")

    def run(self):
        """Main trading loop."""
        print("🚀 Starting trading bot...")
        self.running = True

        try:
            while self.running:
                # Check positions for exits
                self.check_positions()

                # Look for new trades
                self.scan_for_trades()

                # Print performance every hour
                if int(time.time()) % 3600 < 30:
                    self.position_manager.print_status()

                # Wait 30 seconds
                time.sleep(30)

        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            self.position_manager.print_status()

if __name__ == "__main__":
    bot = SimpleTradingBot()
    bot.run()
```

## Configuration

Don't forget to set environment variables in `.env`:

```bash
# Exit Strategy Configuration
TAKE_PROFIT_PCT="20.0"      # Exit at +20% profit
STOP_LOSS_PCT="10.0"        # Exit at -10% loss
MAX_HOLD_HOURS="72"         # Exit after 72 hours
TRAILING_STOP_PCT="5.0"     # Trail by 5%
ENABLE_AUTO_EXIT="true"     # Auto-execute exits
```

## Testing

Test your integration:

```bash
# Run tests
python3 tests/test_position_manager.py

# Run demo
python3 agents/application/position_manager.py

# Test with your bot
python3 your_trading_bot.py
```

## Next Steps

1. **API Integration**: Connect to Polymarket API for real prices
2. **Order Execution**: Implement actual order placement
3. **Error Handling**: Add retry logic for failed exits
4. **Monitoring**: Set up alerts for exits
5. **Backtesting**: Test strategies on historical data

## Support

- Check logs in `/tmp/continuous_trader.log`
- Review position data in `data/positions.json`
- Run tests to verify functionality
- See `docs/POSITION_MANAGER.md` for details
