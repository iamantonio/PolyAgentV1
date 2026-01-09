#!/usr/bin/env python3
"""
Historical Data Fetcher for Polymarket

Fetches and stores historical market data from Polymarket API
for backtesting purposes. Stores data efficiently in Parquet format.
"""

import os
import sys
import json
import time
import sqlite3
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


@dataclass
class MarketSnapshot:
    """Single point-in-time snapshot of a market"""
    timestamp: str
    market_slug: str
    condition_id: str
    token_id: str
    question: str
    outcome: str

    # Price data
    best_bid: float
    best_ask: float
    mid_price: float
    last_price: float

    # Volume and liquidity
    volume_24h: float
    liquidity: float
    open_interest: float

    # Market metadata
    category: str
    tags: List[str]
    end_date: Optional[str]

    # Resolution data (if resolved)
    is_resolved: bool
    winning_outcome: Optional[str]
    resolved_at: Optional[str]


class HistoricalDataFetcher:
    """
    Fetches historical market data from Polymarket API

    Data sources:
    1. Gamma API - Market metadata and current prices
    2. CLOB API - Order book snapshots and trades
    3. Event API - Resolution outcomes
    """

    def __init__(self, data_dir: str = "data/backtest"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # API endpoints
        self.gamma_url = "https://gamma-api.polymarket.com"
        self.clob_url = "https://clob.polymarket.com"

        # Cache database for incremental fetching
        self.db_path = self.data_dir / "historical_cache.db"
        self._init_cache_db()

    def _init_cache_db(self):
        """Initialize SQLite cache for efficient incremental updates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                market_slug TEXT NOT NULL,
                token_id TEXT NOT NULL,
                snapshot_data TEXT NOT NULL,
                UNIQUE(timestamp, token_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fetch_metadata (
                market_slug TEXT PRIMARY KEY,
                last_fetch_timestamp TEXT NOT NULL,
                total_snapshots INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_time
            ON market_snapshots(market_slug, timestamp)
        """)

        conn.commit()
        conn.close()

    def fetch_resolved_markets(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100
    ) -> List[Dict]:
        """
        Fetch markets that resolved in the given date range

        These are the best for backtesting since we know the actual outcomes.
        """
        print(f"Fetching resolved markets from {start_date.date()} to {end_date.date()}...")

        url = f"{self.gamma_url}/markets"
        params = {
            "closed": "true",  # Only resolved markets
            "limit": limit,
            "offset": 0
        }

        all_markets = []
        offset = 0

        while True:
            params["offset"] = offset
            response = requests.get(url, params=params)

            if response.status_code != 200:
                print(f"Error fetching markets: {response.status_code}")
                break

            data = response.json()

            if not data:
                break

            for market in data:
                # Check if resolved in our date range
                end_date_str = market.get("end_date_iso")
                if not end_date_str:
                    continue

                market_end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

                if start_date <= market_end <= end_date:
                    all_markets.append(market)

            # Check if we've fetched all
            if len(data) < limit:
                break

            offset += limit
            time.sleep(0.5)  # Rate limiting

        print(f"Found {len(all_markets)} resolved markets")
        return all_markets

    def fetch_market_history(
        self,
        token_id: str,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 60
    ) -> List[MarketSnapshot]:
        """
        Fetch historical price snapshots for a market

        Since Polymarket doesn't provide historical OHLCV, we reconstruct
        it from order book snapshots and trade data.
        """
        snapshots = []
        current_time = start_time

        print(f"Fetching history for token {token_id[:8]}...")

        while current_time < end_time:
            snapshot = self._fetch_market_snapshot(token_id, current_time)
            if snapshot:
                snapshots.append(snapshot)

            current_time += timedelta(minutes=interval_minutes)
            time.sleep(0.2)  # Rate limiting

        return snapshots

    def _fetch_market_snapshot(
        self,
        token_id: str,
        timestamp: datetime
    ) -> Optional[MarketSnapshot]:
        """
        Fetch a single market snapshot at a specific time

        Note: Polymarket API doesn't support historical data queries,
        so we can only get current state. For real backtesting, you'd need:
        1. Historical database (if available)
        2. Archive.org snapshots
        3. Third-party data providers
        """
        try:
            # Get current market state (limitation: no historical data)
            url = f"{self.clob_url}/book"
            params = {"token_id": token_id}

            response = requests.get(url, params=params)
            if response.status_code != 200:
                return None

            book_data = response.json()

            # Calculate mid price
            bids = book_data.get("bids", [])
            asks = book_data.get("asks", [])

            if not bids or not asks:
                return None

            best_bid = float(bids[0]["price"]) if bids else 0.0
            best_ask = float(asks[0]["price"]) if asks else 1.0
            mid_price = (best_bid + best_ask) / 2

            # Get market metadata
            market_info = self._fetch_market_info(token_id)
            if not market_info:
                return None

            snapshot = MarketSnapshot(
                timestamp=timestamp.isoformat(),
                market_slug=market_info.get("slug", ""),
                condition_id=market_info.get("condition_id", ""),
                token_id=token_id,
                question=market_info.get("question", ""),
                outcome=market_info.get("outcome", ""),
                best_bid=best_bid,
                best_ask=best_ask,
                mid_price=mid_price,
                last_price=mid_price,  # Approximation
                volume_24h=market_info.get("volume", 0.0),
                liquidity=market_info.get("liquidity", 0.0),
                open_interest=market_info.get("open_interest", 0.0),
                category=market_info.get("category", ""),
                tags=market_info.get("tags", []),
                end_date=market_info.get("end_date_iso"),
                is_resolved=market_info.get("closed", False),
                winning_outcome=market_info.get("winning_outcome"),
                resolved_at=market_info.get("closed_time")
            )

            return snapshot

        except Exception as e:
            print(f"Error fetching snapshot: {e}")
            return None

    def _fetch_market_info(self, token_id: str) -> Optional[Dict]:
        """Fetch market metadata from Gamma API"""
        try:
            # This is a simplification - real implementation would need
            # proper market lookup by token_id
            url = f"{self.gamma_url}/markets"
            response = requests.get(url, params={"limit": 1})

            if response.status_code == 200:
                markets = response.json()
                # In real implementation, filter by token_id
                return markets[0] if markets else None

        except Exception as e:
            print(f"Error fetching market info: {e}")

        return None

    def save_snapshots_to_parquet(
        self,
        snapshots: List[MarketSnapshot],
        output_file: str
    ):
        """Save snapshots to efficient Parquet format"""
        if not snapshots:
            print("No snapshots to save")
            return

        # Convert to DataFrame
        df = pd.DataFrame([asdict(s) for s in snapshots])

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Convert tags list to JSON string for Parquet
        df['tags'] = df['tags'].apply(json.dumps)

        # Save to Parquet
        output_path = self.data_dir / output_file
        df.to_parquet(output_path, compression='snappy', index=False)

        print(f"Saved {len(snapshots)} snapshots to {output_path}")

        # Also save to cache database
        self._save_to_cache(snapshots)

    def _save_to_cache(self, snapshots: List[MarketSnapshot]):
        """Save snapshots to SQLite cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for snapshot in snapshots:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO market_snapshots
                    (timestamp, market_slug, token_id, snapshot_data)
                    VALUES (?, ?, ?, ?)
                """, (
                    snapshot.timestamp,
                    snapshot.market_slug,
                    snapshot.token_id,
                    json.dumps(asdict(snapshot))
                ))
            except Exception as e:
                print(f"Error saving snapshot: {e}")

        conn.commit()
        conn.close()

    def load_snapshots_from_parquet(
        self,
        input_file: str
    ) -> pd.DataFrame:
        """Load historical snapshots from Parquet file"""
        input_path = self.data_dir / input_file

        if not input_path.exists():
            raise FileNotFoundError(f"No data file found at {input_path}")

        df = pd.read_parquet(input_path)

        # Parse tags back to list
        df['tags'] = df['tags'].apply(json.loads)

        print(f"Loaded {len(df)} snapshots from {input_path}")
        return df

    def create_synthetic_data(
        self,
        num_markets: int = 10,
        days: int = 90
    ) -> pd.DataFrame:
        """
        Create synthetic historical data for testing

        This is a workaround since Polymarket doesn't provide historical API.
        Real backtesting would need actual historical data.
        """
        print(f"Creating synthetic data for {num_markets} markets over {days} days...")

        snapshots = []
        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        for market_id in range(num_markets):
            # Simulate market lifecycle
            num_snapshots = days * 4  # 4 snapshots per day

            for i in range(num_snapshots):
                timestamp = start_date + timedelta(hours=i * 6)

                # Simulate price movement (random walk)
                import random
                base_price = 0.5 + (random.random() - 0.5) * 0.3

                snapshot = MarketSnapshot(
                    timestamp=timestamp.isoformat(),
                    market_slug=f"synthetic-market-{market_id}",
                    condition_id=f"condition-{market_id}",
                    token_id=f"token-{market_id}",
                    question=f"Will synthetic event {market_id} happen?",
                    outcome="Yes",
                    best_bid=base_price - 0.02,
                    best_ask=base_price + 0.02,
                    mid_price=base_price,
                    last_price=base_price,
                    volume_24h=random.random() * 10000,
                    liquidity=random.random() * 50000,
                    open_interest=random.random() * 100000,
                    category="synthetic",
                    tags=["test", "synthetic"],
                    end_date=(timestamp + timedelta(days=30)).isoformat(),
                    is_resolved=i == num_snapshots - 1,
                    winning_outcome="Yes" if random.random() > 0.5 else "No",
                    resolved_at=timestamp.isoformat() if i == num_snapshots - 1 else None
                )

                snapshots.append(snapshot)

        # Convert to DataFrame
        df = pd.DataFrame([asdict(s) for s in snapshots])
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        print(f"Created {len(df)} synthetic snapshots")
        return df


if __name__ == "__main__":
    # Example usage
    fetcher = HistoricalDataFetcher()

    # Create synthetic data for testing
    df = fetcher.create_synthetic_data(num_markets=20, days=180)

    # Save to Parquet
    fetcher.save_snapshots_to_parquet(
        [MarketSnapshot(**row) for _, row in df.iterrows()],
        "synthetic_historical_data.parquet"
    )

    print("\nSynthetic data created successfully!")
    print(f"Data saved to: {fetcher.data_dir / 'synthetic_historical_data.parquet'}")
