"""
Continuous 24/7 Polymarket Trading Bot

Runs indefinitely with:
- Real-time arbitrage scanning (every 30 seconds)
- Periodic AI prediction (every 5 minutes)
- Error recovery and logging
- Graceful shutdown on Ctrl+C

Production-ready for autonomous operation.
"""

import os
import sys
import time
import signal
import traceback
import random
from datetime import datetime, timedelta
from decimal import Decimal

os.chdir('/home/tony/Dev/agents')
sys.path.insert(0, '/home/tony/Dev/agents')

# Import both strategies
from scripts.python.hybrid_autonomous_trader import HybridAutonomousTrader
from scripts.python.test_autonomous_trader import SafeAutonomousTrader

# Import position manager for exit strategies
from agents.application.position_manager import PositionManager

# CONFIGURATION
ARBITRAGE_SCAN_INTERVAL = 30  # Scan for arbitrage every 30 seconds
AI_PREDICTION_INTERVAL = 1800  # Run AI prediction every 30 minutes (Phase 0 optimization)
POSITION_CHECK_INTERVAL = 30  # Check positions for exits every 30 seconds
ERROR_COOLDOWN = 60  # Wait 60 seconds after errors
MAX_CONSECUTIVE_ERRORS = 5  # Shutdown after 5 consecutive errors

# Logging
LOG_FILE = '/tmp/continuous_trader.log'


class ContinuousTrader:
    """
    24/7 trading bot with multi-strategy execution.

    Strategy priority:
    1. Arbitrage (scanned frequently) - fast, risk-free
    2. AI Prediction (scanned periodically) - slower, higher risk
    """

    def __init__(self):
        self.running = False
        self.arbitrage_trader = None
        self.ai_trader = None
        self.position_manager = None
        self.last_ai_scan = None
        self.last_position_check = None
        self.consecutive_errors = 0

        # Statistics
        self.stats = {
            'started_at': datetime.now().isoformat(),
            'arbitrage_scans': 0,
            'ai_scans': 0,
            'position_checks': 0,
            'trades_executed': 0,
            'exits_executed': 0,
            'errors': 0
        }

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C and shutdown signals."""
        print(f"\n\n{'='*60}")
        print("🛑 SHUTDOWN SIGNAL RECEIVED")
        print(f"{'='*60}")
        self._print_stats()
        self.running = False
        sys.exit(0)

    def _log(self, message: str, level: str = "INFO"):
        """Log message to both console and file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"

        # Print to console
        print(log_msg)

        # Write to log file
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(log_msg + '\n')
        except Exception as e:
            print(f"⚠️ Failed to write to log file: {e}")

    def _print_stats(self):
        """Print current statistics."""
        runtime = datetime.now() - datetime.fromisoformat(self.stats['started_at'])

        print(f"\n{'='*60}")
        print("📊 STATISTICS")
        print(f"{'='*60}")
        print(f"Runtime: {runtime}")
        print(f"Arbitrage scans: {self.stats['arbitrage_scans']}")
        print(f"AI scans: {self.stats['ai_scans']}")
        print(f"Position checks: {self.stats['position_checks']}")
        print(f"Trades executed: {self.stats['trades_executed']}")
        print(f"Exits executed: {self.stats['exits_executed']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"{'='*60}\n")

        # Print position manager metrics
        if self.position_manager:
            metrics = self.position_manager.get_performance_metrics()
            if metrics['total_positions'] > 0:
                print(f"\n{'='*60}")
                print("💰 POSITION PERFORMANCE")
                print(f"{'='*60}")
                print(f"Total closed: {metrics['total_positions']}")
                print(f"Win rate: {metrics['win_rate']:.1f}%")
                print(f"Total PnL: ${metrics['total_pnl']:+.2f}")
                print(f"Avg PnL: {metrics['avg_pnl_pct']:+.2f}%")
                print(f"Best trade: ${metrics['best_trade']:+.2f}")
                print(f"Worst trade: ${metrics['worst_trade']:+.2f}")
                print(f"{'='*60}\n")

    def _initialize_traders(self):
        """Initialize trading bot instances."""
        try:
            self._log("Initializing position manager...")
            self.position_manager = PositionManager()

            self._log("Initializing arbitrage trader...")
            self.arbitrage_trader = HybridAutonomousTrader()

            self._log("Initializing AI prediction trader...")
            self.ai_trader = SafeAutonomousTrader()

            self._log("✅ All traders initialized successfully")
            self.consecutive_errors = 0

        except Exception as e:
            self._log(f"❌ Initialization error: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            raise

    def _scan_arbitrage(self):
        """Scan for arbitrage opportunities."""
        try:
            self._log("🔍 Scanning for arbitrage...")
            self.stats['arbitrage_scans'] += 1

            result = self.arbitrage_trader.scan_for_arbitrage()

            if result:
                self.stats['trades_executed'] += 1
                self._log(f"✅ Arbitrage executed: {result['opportunity_type']} - {result['expected_profit_pct']:.2f}% profit", "TRADE")
                self.consecutive_errors = 0
                return True
            else:
                self._log("No arbitrage opportunities found")
                return False

        except Exception as e:
            self.consecutive_errors += 1
            self.stats['errors'] += 1
            self._log(f"❌ Arbitrage scan error: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    def _run_ai_prediction(self):
        """Run AI prediction strategy."""
        try:
            self._log("🤖 Running AI prediction analysis...")
            self.stats['ai_scans'] += 1
            self.last_ai_scan = datetime.now()

            result = self.ai_trader.execute_safe_trade()

            if result:
                self.stats['trades_executed'] += 1
                self._log(f"✅ AI trade executed: {result['market_question'][:60]}", "TRADE")
                self.consecutive_errors = 0
                return True
            else:
                self._log("No AI prediction trades executed")
                return False

        except Exception as e:
            self.consecutive_errors += 1
            self.stats['errors'] += 1
            self._log(f"❌ AI prediction error: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")
            return False

    def _should_run_ai_scan(self):
        """Check if it's time to run AI prediction scan."""
        if self.last_ai_scan is None:
            return True

        elapsed = (datetime.now() - self.last_ai_scan).total_seconds()
        return elapsed >= AI_PREDICTION_INTERVAL

    def _should_check_positions(self):
        """Check if it's time to check positions for exits."""
        if self.last_position_check is None:
            return True

        elapsed = (datetime.now() - self.last_position_check).total_seconds()
        return elapsed >= POSITION_CHECK_INTERVAL

    def _check_positions(self):
        """Check all open positions for exit conditions."""
        try:
            self._log("🔍 Checking open positions for exits...")
            self.stats['position_checks'] += 1
            self.last_position_check = datetime.now()

            open_positions = self.position_manager.get_open_positions()

            if not open_positions:
                self._log("No open positions to check")
                return

            # TODO: Get current prices from Polymarket API
            # For now, just print status
            for pos in open_positions:
                self._log(f"   Tracking: {pos.market_question[:50]}... | "
                         f"Entry: ${pos.entry_price:.4f} | "
                         f"PnL: {pos.unrealized_pnl_pct:+.1f}%")

            # Print status every 10 checks
            if self.stats['position_checks'] % 10 == 0:
                self.position_manager.print_status()

            self.consecutive_errors = 0

        except Exception as e:
            self.consecutive_errors += 1
            self.stats['errors'] += 1
            self._log(f"❌ Position check error: {e}", "ERROR")
            self._log(traceback.format_exc(), "ERROR")

    def _check_error_threshold(self):
        """Check if too many consecutive errors."""
        if self.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            self._log(f"⛔ Too many consecutive errors ({self.consecutive_errors}). Shutting down.", "CRITICAL")
            self._print_stats()
            return False
        return True

    def run(self):
        """Main continuous trading loop."""
        self._log("🚀 Starting continuous 24/7 trading bot")
        self._log(f"Arbitrage scan interval: {ARBITRAGE_SCAN_INTERVAL}s")
        self._log(f"AI prediction interval: {AI_PREDICTION_INTERVAL}s")
        self._log(f"Log file: {LOG_FILE}")

        # Initialize
        self._initialize_traders()

        self.running = True
        iteration = 0

        try:
            while self.running:
                iteration += 1

                # Print iteration header
                print(f"\n{'='*60}")
                print(f"ITERATION {iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}")

                # Check error threshold
                if not self._check_error_threshold():
                    break

                # PRIORITY 0: Check positions for exits (critical!)
                if self._should_check_positions():
                    self._check_positions()

                # PRIORITY 1: Scan for arbitrage (fast, frequent)
                self._scan_arbitrage()

                # PRIORITY 2: Run AI prediction if interval elapsed
                if self._should_run_ai_scan():
                    self._run_ai_prediction()

                # Print stats every 10 iterations
                if iteration % 10 == 0:
                    self._print_stats()

                # Handle errors with exponential backoff + jitter
                if self.consecutive_errors > 0:
                    # Exponential backoff: 2^(min(errors, 8)) capped at 300s, with jitter
                    base_sleep = min(300, (2 ** min(self.consecutive_errors, 8)))
                    jitter = random.random() * 3  # 0-3 seconds jitter
                    total_sleep = base_sleep + jitter
                    self._log(f"⏸️ Error backoff: waiting {total_sleep:.1f}s (consecutive={self.consecutive_errors})")
                    time.sleep(total_sleep)
                else:
                    # Normal interval between arbitrage scans
                    self._log(f"⏸️ Waiting {ARBITRAGE_SCAN_INTERVAL}s until next scan...")
                    time.sleep(ARBITRAGE_SCAN_INTERVAL)

        except KeyboardInterrupt:
            self._log("🛑 Keyboard interrupt received")
        except Exception as e:
            self._log(f"💥 Fatal error: {e}", "CRITICAL")
            self._log(traceback.format_exc(), "CRITICAL")
        finally:
            self._log("Shutting down continuous trader...")
            self._print_stats()
            self.running = False


def main():
    """Run continuous 24/7 trading bot."""
    print(f"\n{'='*60}")
    print("CONTINUOUS 24/7 POLYMARKET TRADING BOT")
    print(f"{'='*60}")
    print(f"\nStrategies:")
    print(f"  🥇 Arbitrage (every {ARBITRAGE_SCAN_INTERVAL}s)")
    print(f"  🥈 AI Prediction (every {AI_PREDICTION_INTERVAL}s)")
    print(f"\nPress Ctrl+C to stop gracefully")
    print(f"{'='*60}\n")

    trader = ContinuousTrader()
    trader.run()


if __name__ == "__main__":
    main()
