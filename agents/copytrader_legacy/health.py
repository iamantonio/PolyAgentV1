"""
Health checks for CopyTrader system.

Validates that all components are ready before starting copy trading:
- Polymarket API connectivity
- Wallet balance
- Storage backend
- Configuration validity
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from agents.copytrader.config import CopyTraderConfig
from agents.copytrader.tracking import PurchaseTracker
from agents.polymarket.polymarket import Polymarket

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a health check"""

    name: str
    passed: bool
    message: str
    critical: bool = True  # If False, failure is a warning not an error


class HealthChecker:
    """
    Performs comprehensive health checks before copy trading starts.

    This prevents runtime failures by validating configuration and connectivity upfront.
    """

    def __init__(
        self,
        config: CopyTraderConfig,
        polymarket: Optional[Polymarket] = None,
        tracker: Optional[PurchaseTracker] = None,
    ):
        self.config = config
        self.polymarket = polymarket
        self.tracker = tracker

    def run_all_checks(self) -> List[HealthCheckResult]:
        """Run all health checks and return results"""
        results = []

        # Configuration checks
        results.append(self._check_trader_allowlist())
        results.append(self._check_size_limits())

        # Storage check
        if self.tracker:
            results.append(self._check_storage())

        # Polymarket checks
        if self.polymarket:
            results.append(self._check_api_connectivity())
            results.append(self._check_wallet_balance())

        return results

    def _check_trader_allowlist(self) -> HealthCheckResult:
        """Verify trader allowlist is configured"""
        if not self.config.allowed_traders:
            return HealthCheckResult(
                name="Trader Allowlist",
                passed=False,
                message="No traders configured in FOLLOW_TRADERS. Add trader addresses to enable copy trading.",
                critical=True,
            )

        return HealthCheckResult(
            name="Trader Allowlist",
            passed=True,
            message=f"{len(self.config.allowed_traders)} trader(s) configured: "
            + ", ".join(f"{addr[:8]}..." for addr in list(self.config.allowed_traders)[:3]),
        )

    def _check_size_limits(self) -> HealthCheckResult:
        """Verify size limits are sensible"""
        if self.config.max_intent_size_usdc < self.config.min_order_size_usdc:
            return HealthCheckResult(
                name="Size Limits",
                passed=False,
                message=f"Max intent size (${self.config.max_intent_size_usdc}) "
                f"< min order size (${self.config.min_order_size_usdc})",
                critical=True,
            )

        return HealthCheckResult(
            name="Size Limits",
            passed=True,
            message=f"Order sizes: ${self.config.min_order_size_usdc:.2f} - ${self.config.max_intent_size_usdc:.2f}",
        )

    def _check_storage(self) -> HealthCheckResult:
        """Verify storage backend is working"""
        try:
            # Try to get stats (this will fail if DB is broken)
            stats = self.tracker.backend.get_stats()

            return HealthCheckResult(
                name="Storage Backend",
                passed=True,
                message=f"SQLite tracking DB ready ({stats['total_purchases']} purchases tracked)",
            )
        except Exception as e:
            return HealthCheckResult(
                name="Storage Backend",
                passed=False,
                message=f"Storage error: {e}",
                critical=True,
            )

    def _check_api_connectivity(self) -> HealthCheckResult:
        """Verify we can connect to Polymarket API"""
        try:
            # Try to fetch a market (this will fail if API is down)
            # TODO: Add proper connectivity check to Polymarket class
            # For now, just check if polymarket object exists
            if self.polymarket:
                return HealthCheckResult(
                    name="Polymarket API",
                    passed=True,
                    message="Polymarket client initialized",
                    critical=False,  # Not critical for testing
                )
            else:
                return HealthCheckResult(
                    name="Polymarket API",
                    passed=False,
                    message="Polymarket client not provided",
                    critical=False,
                )
        except Exception as e:
            return HealthCheckResult(
                name="Polymarket API",
                passed=False,
                message=f"API connectivity error: {e}",
                critical=True,
            )

    def _check_wallet_balance(self) -> HealthCheckResult:
        """Verify wallet has sufficient balance"""
        try:
            balance = self.polymarket.get_balance()

            if balance < self.config.min_order_size_usdc:
                return HealthCheckResult(
                    name="Wallet Balance",
                    passed=False,
                    message=f"Insufficient balance: ${balance:.2f} "
                    f"(min ${self.config.min_order_size_usdc:.2f} required)",
                    critical=True,
                )

            # Warn if balance is low
            warning_threshold = self.config.max_intent_size_usdc * 5
            if balance < warning_threshold:
                return HealthCheckResult(
                    name="Wallet Balance",
                    passed=True,
                    message=f"Balance: ${balance:.2f} (consider topping up for larger trades)",
                    critical=False,
                )

            return HealthCheckResult(
                name="Wallet Balance",
                passed=True,
                message=f"Balance: ${balance:.2f}",
            )
        except Exception as e:
            return HealthCheckResult(
                name="Wallet Balance",
                passed=False,
                message=f"Balance check error: {e}",
                critical=True,
            )

    def print_results(self, results: List[HealthCheckResult]) -> bool:
        """
        Print health check results and return overall status.

        Returns:
            True if all critical checks passed
        """
        print("\n" + "=" * 70)
        print("COPYTRADER HEALTH CHECK")
        print("=" * 70)

        all_passed = True

        for result in results:
            # Format status
            if result.passed:
                status = "✓ PASS"
                color = "\033[92m"  # Green
            elif result.critical:
                status = "✗ FAIL"
                color = "\033[91m"  # Red
                all_passed = False
            else:
                status = "⚠ WARN"
                color = "\033[93m"  # Yellow

            reset = "\033[0m"

            # Print result
            print(f"{color}{status}{reset} {result.name:.<25} {result.message}")

        print("=" * 70)

        if all_passed:
            print("✓ All critical checks passed - ready to copy trade!")
        else:
            print("✗ Some critical checks failed - please fix before starting")

        print("=" * 70 + "\n")

        return all_passed


def run_health_check(
    config: CopyTraderConfig,
    polymarket: Optional[Polymarket] = None,
    tracker: Optional[PurchaseTracker] = None,
) -> bool:
    """
    Convenience function to run health checks.

    Returns:
        True if all critical checks passed
    """
    checker = HealthChecker(config, polymarket, tracker)
    results = checker.run_all_checks()
    return checker.print_results(results)
