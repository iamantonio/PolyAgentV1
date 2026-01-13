"""
Polymarket Position Synchronization Module

Uses the official Polymarket Data API to sync local database with on-chain positions.
Endpoints from: https://docs.polymarket.com/developers/misc-endpoints/

Data API Base URL: https://data-api.polymarket.com/
"""

import os
import sqlite3
import requests
from datetime import datetime
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()


class PositionSync:
    """Syncs local position database with Polymarket on-chain data."""

    DATA_API_BASE = "https://data-api.polymarket.com"

    def __init__(self, db_path: str = None):
        # Use persistent storage by default
        if db_path is None:
            db_dir = os.path.expanduser("~/.polymarket")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "learning_trader.db")

        self.db_path = db_path
        self.proxy_address = os.getenv("POLYMARKET_PROXY_ADDRESS")
        if not self.proxy_address:
            raise ValueError("POLYMARKET_PROXY_ADDRESS not set in environment")

    def get_actual_positions(self, size_threshold: float = 0.1) -> List[Dict]:
        """
        Fetch actual open positions from Polymarket Data API.

        Endpoint: GET /positions
        Docs: https://docs.polymarket.com/developers/misc-endpoints/data-api-get-positions
        """
        url = f"{self.DATA_API_BASE}/positions"
        params = {
            "user": self.proxy_address,
            "sizeThreshold": size_threshold,
            "limit": 500
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

    def get_trade_history(self, limit: int = 500) -> List[Dict]:
        """
        Fetch trade history from Polymarket Data API.

        Endpoint: GET /trades
        Docs: https://gist.github.com/shaunlebron/0dd3338f7dea06b8e9f8724981bb13bf
        """
        url = f"{self.DATA_API_BASE}/trades"
        params = {
            "user": self.proxy_address,
            "limit": limit,
            "takerOnly": "true"
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching trades: {e}")
            return []

    def get_activity(self, activity_type: Optional[str] = None, limit: int = 500) -> List[Dict]:
        """
        Fetch on-chain activity (trades, redeems, etc).

        Endpoint: GET /activity
        Types: TRADE, SPLIT, MERGE, REDEEM, REWARD, CONVERSION, MAKER_REBATE
        Docs: https://docs.polymarket.com/developers/misc-endpoints/data-api-activity
        """
        url = f"{self.DATA_API_BASE}/activity"
        params = {
            "user": self.proxy_address,
            "limit": limit
        }
        if activity_type:
            params["type"] = activity_type

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching activity: {e}")
            return []

    def get_portfolio_value(self) -> float:
        """
        Get total USD value of positions.

        Endpoint: GET /value
        """
        url = f"{self.DATA_API_BASE}/value"
        params = {"user": self.proxy_address}

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("value", 0))
        except Exception as e:
            print(f"Error fetching portfolio value: {e}")
            return 0.0

    def reconcile_positions(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Sync local database with actual on-chain positions.

        Uses token_id matching for accuracy (not fragile string matching).
        Returns stats about what was changed.
        """
        # Get actual positions from API
        actual_positions = self.get_actual_positions()

        # Build set of actual asset IDs (token IDs) for reliable matching
        actual_asset_ids = set()
        actual_titles = {}  # For fallback matching
        for p in actual_positions:
            asset_id = p.get("asset", "") or p.get("assetId", "")
            if asset_id:
                actual_asset_ids.add(asset_id)
            title = p.get("title", "")[:50]
            if title:
                actual_titles[title] = True

        if verbose:
            print(f"📊 Actual positions from Polymarket API: {len(actual_positions)}")
            for p in actual_positions:
                print(f"   ✓ {p.get('title', 'Unknown')[:55]}... | {p.get('outcome')} | ${p.get('currentValue', 0):.2f}")

        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all DB positions marked as open (include token_id for matching)
        cursor.execute('''
            SELECT id, token_id, question FROM predictions
            WHERE trade_executed = 1 AND position_open = 1
        ''')
        db_positions = cursor.fetchall()

        if verbose:
            print(f"\n📂 DB positions marked open: {len(db_positions)}")

        # Close positions that don't exist on-chain
        closed_count = 0
        kept_count = 0

        for row in db_positions:
            pid = row[0]
            token_id = row[1] if len(row) > 1 else None
            question = row[2] if len(row) > 2 else (row[1] if len(row) > 1 else "")

            # Primary: Match by token_id (reliable)
            if token_id and token_id in actual_asset_ids:
                kept_count += 1
                continue

            # Fallback: Match by title prefix (less reliable but backwards compatible)
            q_prefix = (question or "")[:50]
            if q_prefix and any(q_prefix in title or title in q_prefix for title in actual_titles):
                kept_count += 1
                continue

            # Position not found on-chain - mark as closed
            cursor.execute(
                'UPDATE predictions SET position_open = 0 WHERE id = ?',
                (pid,)
            )
            closed_count += 1
            if verbose:
                print(f"   ✗ Closed: {(question or 'Unknown')[:50]}...")

        conn.commit()

        # Get final count
        cursor.execute(
            'SELECT COUNT(*) FROM predictions WHERE trade_executed = 1 AND position_open = 1'
        )
        final_open = cursor.fetchone()[0]

        conn.close()

        result = {
            "actual_positions": len(actual_positions),
            "db_positions_before": len(db_positions),
            "closed_stale": closed_count,
            "kept_matching": kept_count,
            "final_open": final_open,
            "synced_at": datetime.now().isoformat()
        }

        if verbose:
            print(f"\n✅ RECONCILIATION COMPLETE")
            print(f"   Closed stale: {closed_count}")
            print(f"   Kept matching: {kept_count}")
            print(f"   Final open in DB: {final_open}")

        return result

    def get_open_exposure(self) -> float:
        """Get total USD exposure from actual on-chain positions."""
        positions = self.get_actual_positions()
        return sum(float(p.get("currentValue", 0)) for p in positions)

    def get_unrealized_pnl(self) -> float:
        """Get total unrealized P&L from actual positions."""
        positions = self.get_actual_positions()
        return sum(float(p.get("cashPnl", 0)) for p in positions)


def test():
    """Test the position sync module."""
    sync = PositionSync()

    print("=" * 60)
    print("POLYMARKET POSITION SYNC TEST")
    print("=" * 60)

    # Get positions
    positions = sync.get_actual_positions()
    print(f"\nActual positions: {len(positions)}")

    # Get portfolio value
    value = sync.get_portfolio_value()
    print(f"Portfolio value: ${value:.2f}")

    # Get recent trades
    trades = sync.get_trade_history(limit=5)
    print(f"\nRecent trades: {len(trades)}")
    for t in trades[:3]:
        print(f"  {t.get('side')} {t.get('outcome', 'Unknown')} @ ${t.get('price', 0)}")

    # Reconcile
    print("\n" + "=" * 60)
    result = sync.reconcile_positions()
    print(f"\nExposure: ${sync.get_open_exposure():.2f}")
    print(f"Unrealized P&L: ${sync.get_unrealized_pnl():.2f}")


if __name__ == "__main__":
    test()
