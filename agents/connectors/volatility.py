"""
Volatility calculator for market opportunity scoring.

Fetches price history and calculates volatility metrics to identify
high-value trading opportunities.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import statistics
import math


class VolatilityCalculator:
    """
    Calculate market volatility from price history.

    Higher volatility = more trading opportunities.
    Used by OpportunityScorer to prioritize markets.
    """

    def __init__(self, lookback_hours: int = 24):
        """
        Initialize volatility calculator.

        Args:
            lookback_hours: Hours of price history to analyze (default: 24)
        """
        self.lookback_hours = lookback_hours

    def calculate_volatility(self, price_history: List[Dict[str, Any]]) -> float:
        """
        Calculate price volatility as normalized standard deviation.

        Args:
            price_history: List of price points [{"timestamp": ..., "price": ...}, ...]

        Returns:
            Volatility score (0.0-1.0+), where:
            - 0.0 = no volatility
            - 0.05 = low volatility
            - 0.15 = high volatility
            - 0.30+ = extreme volatility
        """
        if not price_history or len(price_history) < 2:
            return 0.0

        try:
            prices = [float(p["price"]) for p in price_history]

            # Handle edge cases
            if len(prices) < 2:
                return 0.0

            # Calculate standard deviation
            mean_price = statistics.mean(prices)

            # Avoid division by zero
            if mean_price == 0:
                return 0.0

            std_dev = statistics.stdev(prices)

            # Normalize by mean (coefficient of variation)
            volatility = std_dev / mean_price

            return volatility

        except (ValueError, ZeroDivisionError, KeyError) as e:
            print(f"  ⚠️ Volatility calculation error: {e}")
            return 0.0

    def detect_price_spike(
        self,
        price_history: List[Dict[str, Any]],
        threshold_std: float = 2.0
    ) -> bool:
        """
        Detect if there's been a recent price spike (news event).

        A spike is defined as the most recent price being >2 standard deviations
        from the mean.

        Args:
            price_history: Price history with timestamps
            threshold_std: Number of std deviations for spike detection (default: 2.0)

        Returns:
            True if recent spike detected, False otherwise
        """
        if not price_history or len(price_history) < 3:
            return False

        try:
            prices = [float(p["price"]) for p in price_history]

            # Need at least 3 points
            if len(prices) < 3:
                return False

            # Calculate statistics from all but most recent
            historical_prices = prices[:-1]
            recent_price = prices[-1]

            mean = statistics.mean(historical_prices)
            std_dev = statistics.stdev(historical_prices) if len(historical_prices) > 1 else 0

            # Check if recent price is an outlier
            if std_dev == 0:
                return False

            z_score = abs(recent_price - mean) / std_dev

            return z_score > threshold_std

        except (ValueError, ZeroDivisionError, KeyError):
            return False

    def calculate_trend_strength(self, price_history: List[Dict[str, Any]]) -> float:
        """
        Calculate strength of price trend (momentum).

        Uses simple linear regression slope.

        Args:
            price_history: Price history with timestamps

        Returns:
            Trend strength (-1.0 to 1.0):
            - Positive = upward trend
            - Negative = downward trend
            - Close to 0 = no trend
        """
        if not price_history or len(price_history) < 3:
            return 0.0

        try:
            # Extract prices and create time indices
            prices = [float(p["price"]) for p in price_history]
            n = len(prices)
            x = list(range(n))  # Time indices

            # Calculate linear regression slope
            x_mean = statistics.mean(x)
            y_mean = statistics.mean(prices)

            numerator = sum((x[i] - x_mean) * (prices[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                return 0.0

            slope = numerator / denominator

            # Normalize slope to roughly -1 to 1 range
            # (assuming price changes are typically < 0.1 per time step)
            normalized_slope = slope * n / max(abs(y_mean), 0.01)

            return max(-1.0, min(1.0, normalized_slope))

        except (ValueError, ZeroDivisionError, KeyError):
            return 0.0

    def get_price_range(self, price_history: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Get min, max, and range of prices in history.

        Args:
            price_history: Price history

        Returns:
            Dict with min, max, and range
        """
        if not price_history:
            return {"min": 0.0, "max": 0.0, "range": 0.0}

        try:
            prices = [float(p["price"]) for p in price_history]
            min_price = min(prices)
            max_price = max(prices)

            return {
                "min": min_price,
                "max": max_price,
                "range": max_price - min_price
            }
        except (ValueError, KeyError):
            return {"min": 0.0, "max": 0.0, "range": 0.0}

    def simulate_price_history(
        self,
        current_price: float,
        volatility: float = 0.05,
        num_points: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Generate simulated price history for testing.

        Uses random walk with given volatility.

        Args:
            current_price: Current market price
            volatility: Volatility parameter (std dev of changes)
            num_points: Number of historical points to generate

        Returns:
            Simulated price history
        """
        import random

        history = []
        price = current_price

        # Walk backwards in time
        now = datetime.now()

        for i in range(num_points):
            timestamp = now - timedelta(hours=num_points - i)

            # Random walk
            change = random.gauss(0, volatility)
            price = max(0.01, min(0.99, price + change))  # Keep in valid range

            history.append({
                "timestamp": timestamp.isoformat(),
                "price": price
            })

        return history

    def format_volatility_metrics(
        self,
        price_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate all volatility metrics in one pass.

        Args:
            price_history: Price history

        Returns:
            Dict with all metrics: volatility, spike_detected, trend_strength, price_range
        """
        return {
            "volatility": self.calculate_volatility(price_history),
            "spike_detected": self.detect_price_spike(price_history),
            "trend_strength": self.calculate_trend_strength(price_history),
            "price_range": self.get_price_range(price_history),
            "data_points": len(price_history),
            "lookback_hours": self.lookback_hours
        }
