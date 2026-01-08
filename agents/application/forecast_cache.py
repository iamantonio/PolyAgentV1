"""
Forecast cache with market change detection.

Prevents redundant LLM calls by:
1. Caching forecasts keyed on market state
2. Skipping markets with minimal price movement
3. Time-based cache expiration
"""

import os
import json
import time
from typing import Optional, Dict, Tuple
from pathlib import Path
from decimal import Decimal


class ForecastCache:
    """
    Cache forecasts and track market state changes.

    Cache key: (market_id, price_bucket, time_bucket)
    """

    STATE_FILE = "data/forecast_cache.json"

    def __init__(
        self,
        price_change_threshold_pct: float = 1.0,  # Skip if price moved < 1%
        cache_ttl_seconds: int = 1800,  # 30 minutes
        price_bucket_size: float = 0.01  # Round to nearest 1 cent
    ):
        self.price_change_threshold = Decimal(str(price_change_threshold_pct / 100))
        self.cache_ttl = cache_ttl_seconds
        self.price_bucket_size = Decimal(str(price_bucket_size))

        # Load persistent state
        self.state = self._load_state()

        # Clean up stale entries
        self._cleanup_stale_entries()

    def _load_state(self) -> dict:
        """Load cache state from disk."""
        Path(self.STATE_FILE).parent.mkdir(parents=True, exist_ok=True)

        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load forecast cache: {e}. Starting fresh.")

        return {
            "forecasts": {},  # {cache_key: {forecast, timestamp, price}}
            "last_prices": {}  # {market_id: last_observed_price}
        }

    def _save_state(self):
        """Persist cache state to disk."""
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save forecast cache: {e}")

    def _cleanup_stale_entries(self):
        """Remove expired cache entries."""
        now = time.time()
        cutoff = now - self.cache_ttl

        original_count = len(self.state["forecasts"])

        # Remove expired forecasts
        self.state["forecasts"] = {
            key: value for key, value in self.state["forecasts"].items()
            if value["timestamp"] > cutoff
        }

        removed = original_count - len(self.state["forecasts"])
        if removed > 0:
            print(f"[CACHE] Cleaned up {removed} expired forecasts")
            self._save_state()

    def _bucket_price(self, price: float) -> str:
        """Round price to bucket for cache key."""
        price_decimal = Decimal(str(price))
        bucketed = (price_decimal // self.price_bucket_size) * self.price_bucket_size
        return str(bucketed)

    def _time_bucket(self) -> str:
        """Get current time bucket (30-min intervals)."""
        # Round down to nearest 30 minutes
        bucket_size = 1800  # 30 minutes in seconds
        now = time.time()
        bucket = int(now // bucket_size) * bucket_size
        return str(bucket)

    def _make_cache_key(self, market_id: str, price: float) -> str:
        """Generate cache key from market state."""
        price_bucket = self._bucket_price(price)
        time_bucket = self._time_bucket()
        return f"{market_id}:{price_bucket}:{time_bucket}"

    def should_forecast(self, market_id: str, current_price: float) -> Tuple[bool, Optional[str]]:
        """
        Determine if we should forecast this market.

        Returns:
            (should_forecast, reason_if_skipped)
        """
        self._cleanup_stale_entries()

        # Check if we have a cached forecast for this state
        cache_key = self._make_cache_key(market_id, current_price)
        if cache_key in self.state["forecasts"]:
            cached = self.state["forecasts"][cache_key]
            age_minutes = (time.time() - cached["timestamp"]) / 60
            return False, f"Cached forecast (age: {age_minutes:.1f}min)"

        # Check price movement since last forecast
        if market_id in self.state["last_prices"]:
            last_price = Decimal(str(self.state["last_prices"][market_id]))
            current_price_decimal = Decimal(str(current_price))

            # Calculate percentage change
            if last_price > 0:
                change_pct = abs(current_price_decimal - last_price) / last_price

                if change_pct < self.price_change_threshold:
                    return False, f"Price stable (Δ={change_pct*100:.2f}% < {self.price_change_threshold*100:.1f}%)"

        # Should forecast - significant change or first time seeing this market
        return True, None

    def get_cached_forecast(self, market_id: str, current_price: float) -> Optional[str]:
        """Get cached forecast if available and valid."""
        cache_key = self._make_cache_key(market_id, current_price)

        if cache_key in self.state["forecasts"]:
            cached = self.state["forecasts"][cache_key]
            age = time.time() - cached["timestamp"]

            if age <= self.cache_ttl:
                return cached["forecast"]

        return None

    def cache_forecast(self, market_id: str, current_price: float, forecast: str):
        """Cache a forecast for this market state."""
        cache_key = self._make_cache_key(market_id, current_price)

        self.state["forecasts"][cache_key] = {
            "forecast": forecast,
            "timestamp": time.time(),
            "price": current_price
        }

        # Update last observed price
        self.state["last_prices"][market_id] = current_price

        self._save_state()

    def get_stats(self) -> dict:
        """Get cache statistics."""
        now = time.time()
        valid_forecasts = sum(
            1 for f in self.state["forecasts"].values()
            if (now - f["timestamp"]) <= self.cache_ttl
        )

        return {
            "total_forecasts_cached": len(self.state["forecasts"]),
            "valid_forecasts": valid_forecasts,
            "markets_tracked": len(self.state["last_prices"]),
            "cache_ttl_minutes": self.cache_ttl / 60,
            "price_change_threshold_pct": float(self.price_change_threshold * 100)
        }
