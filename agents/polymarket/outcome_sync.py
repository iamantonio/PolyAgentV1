"""
Polymarket Outcome Resolution Module

Syncs resolved market outcomes from Polymarket Data API to local database.
Uses REDEEM activity events to determine wins and losses.

This fixes BUG-002: outcomes were never being recorded, causing edge detection
to use empty/stale data and make inverted trading decisions.

Author: Auto-generated fix
Date: 2026-01-12
"""

import os
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()


class OutcomeSync:
    """
    Syncs market resolution outcomes from Polymarket to local database.

    REDEEM events indicate:
    - usdcSize > 0: WIN (received payout)
    - usdcSize = 0: LOSS (position worthless)
    """

    DATA_API_BASE = "https://data-api.polymarket.com"

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = os.path.expanduser("~/.polymarket")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "learning_trader.db")
        self.db_path = db_path
        self.proxy_address = os.getenv("POLYMARKET_PROXY_ADDRESS")
        if not self.proxy_address:
            raise ValueError("POLYMARKET_PROXY_ADDRESS not set in environment")

    def get_redeem_events(self, limit: int = 500) -> List[Dict]:
        """
        Fetch REDEEM events (resolved markets) from Polymarket Data API.

        REDEEM events show:
        - assetId: The token ID of the resolved position
        - usdcSize: The payout amount (0 = loss, >0 = win)
        - timestamp: When the redemption occurred
        """
        url = f"{self.DATA_API_BASE}/activity"
        params = {
            "user": self.proxy_address,
            "type": "REDEEM",
            "limit": limit
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching REDEEM events: {e}")
            return []

    def get_trade_events(self, limit: int = 500) -> List[Dict]:
        """Fetch TRADE events to match with REDEEMs."""
        url = f"{self.DATA_API_BASE}/activity"
        params = {
            "user": self.proxy_address,
            "type": "TRADE",
            "limit": limit
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Error fetching TRADE events: {e}")
            return []

    def sync_outcomes(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Main sync function: Match REDEEM events to database trades and record outcomes.

        Strategy: Match by title (question) since REDEEM events don't have asset IDs.
        Also builds conditionId mapping from TRADE events for precise matching.

        Returns stats about what was synced.
        """
        redeems = self.get_redeem_events(limit=1000)
        trades_api = self.get_trade_events(limit=1000)

        if verbose:
            print(f"Found {len(redeems)} REDEEM events from Polymarket")

        # Build lookup by conditionId from TRADE events (conditionId -> asset/token_id)
        condition_to_asset = {}
        for t in trades_api:
            cond_id = t.get("conditionId", "")
            asset = t.get("asset", "")
            if cond_id and asset:
                condition_to_asset[cond_id] = asset

        # Build lookup by title (normalized) and by conditionId
        redeem_by_title = {}
        redeem_by_condition = {}
        for r in redeems:
            title = (r.get("title") or "").strip().lower()
            cond_id = r.get("conditionId", "")
            if title:
                if title not in redeem_by_title:
                    redeem_by_title[title] = []
                redeem_by_title[title].append(r)
            if cond_id:
                if cond_id not in redeem_by_condition:
                    redeem_by_condition[cond_id] = []
                redeem_by_condition[cond_id].append(r)

        # Connect to database
        if not os.path.exists(self.db_path):
            print(f"Database not found at {self.db_path}")
            return {"error": "database_not_found"}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check if required columns exist, add if missing
        try:
            cursor.execute("SELECT resolved_at FROM predictions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE predictions ADD COLUMN resolved_at TEXT")
            print("Added resolved_at column")

        # Check which columns exist (schema varies between versions)
        cursor.execute("PRAGMA table_info(predictions)")
        columns = {row[1] for row in cursor.fetchall()}

        size_col = "trade_size_usdc" if "trade_size_usdc" in columns else "position_size"
        price_col = "trade_price" if "trade_price" in columns else "entry_price"

        # Handle case where neither size/price column exists
        if size_col not in columns:
            size_col = "1.0"  # Default size
        if price_col not in columns:
            price_col = "0.5"  # Default price

        # Get trades without recorded outcomes
        cursor.execute(f'''
            SELECT id, token_id, question,
                   {size_col} as size,
                   {price_col} as price,
                   market_type
            FROM predictions
            WHERE trade_executed = 1
            AND (actual_outcome IS NULL OR profit_loss_usdc IS NULL)
        ''')
        pending = cursor.fetchall()

        if verbose:
            print(f"Found {len(pending)} trades without recorded outcomes")

        matched = 0
        wins = 0
        losses = 0
        total_pnl = 0.0

        for trade_id, token_id, question, size, entry_price, market_type in pending:
            redeem = None

            # Strategy 1: Match by token_id -> conditionId -> REDEEM
            if token_id:
                for cond_id, asset in condition_to_asset.items():
                    if asset == token_id and cond_id in redeem_by_condition:
                        redeem = redeem_by_condition[cond_id][0]
                        break

            # Strategy 2: Match by title (fallback)
            if not redeem and question:
                title_normalized = question.strip().lower()
                # Try exact match
                if title_normalized in redeem_by_title:
                    redeem = redeem_by_title[title_normalized][0]
                else:
                    # Try partial match (first 40 chars)
                    title_prefix = title_normalized[:40]
                    for t, r_list in redeem_by_title.items():
                        if t.startswith(title_prefix) or title_prefix in t:
                            redeem = r_list[0]
                            break

            if redeem:
                usdc_payout = float(redeem.get("usdcSize", 0))

                # P&L calculation:
                # cost = trade_size_usdc (the USDC spent to buy shares)
                # If WIN: pnl = payout - cost
                # If LOSS: pnl = -cost (lost entire stake)
                cost = float(size or 0)

                if usdc_payout > 0:
                    outcome = "YES"  # Won the position
                    was_correct = 1
                    pnl = usdc_payout - cost
                    wins += 1
                else:
                    outcome = "NO"  # Lost the position
                    was_correct = 0
                    pnl = -cost
                    losses += 1

                total_pnl += pnl

                # Update database - use profit_loss_usdc column
                cursor.execute('''
                    UPDATE predictions
                    SET actual_outcome = ?,
                        was_correct = ?,
                        profit_loss_usdc = ?,
                        position_open = 0,
                        resolved_at = ?
                    WHERE id = ?
                ''', (outcome, was_correct, pnl, datetime.now().isoformat(), trade_id))

                matched += 1

                if verbose:
                    result = "WIN" if was_correct else "LOSS"
                    q_short = (question or "Unknown")[:50]
                    print(f"   {result}: {q_short}... P&L: ${pnl:.2f}")

        conn.commit()
        conn.close()

        result = {
            "redeem_events": len(redeems),
            "pending_trades": len(pending),
            "matched": matched,
            "wins": wins,
            "losses": losses,
            "total_pnl": total_pnl,
            "synced_at": datetime.now().isoformat()
        }

        if verbose:
            print(f"\nSync complete: {wins}W/{losses}L, Total P&L: ${total_pnl:.2f}")

        return result

    def get_pnl_by_market_type(self) -> Dict[str, Dict]:
        """
        Calculate P&L statistics by market type from recorded outcomes.

        Returns edge information for each market type.
        """
        if not os.path.exists(self.db_path):
            return {}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT market_type,
                   COUNT(*) as trades,
                   SUM(CASE WHEN actual_outcome = 1 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN actual_outcome = 0 THEN 1 ELSE 0 END) as losses,
                   SUM(pnl) as total_pnl,
                   AVG(pnl) as avg_pnl
            FROM predictions
            WHERE trade_executed = 1
            AND actual_outcome IS NOT NULL
            AND pnl IS NOT NULL
            GROUP BY market_type
        ''')

        results = {}
        for row in cursor.fetchall():
            market_type, trades, wins, losses, total_pnl, avg_pnl = row
            results[market_type or "unknown"] = {
                "trades": trades,
                "wins": wins or 0,
                "losses": losses or 0,
                "win_rate": (wins or 0) / trades if trades > 0 else 0,
                "total_pnl": total_pnl or 0,
                "avg_pnl": avg_pnl or 0,
                "has_edge": (avg_pnl or 0) > 0
            }

        conn.close()
        return results

    def calculate_historical_pnl(self) -> Dict[str, Any]:
        """
        Calculate P&L from all REDEEM events (for backfill/verification).

        This uses raw Polymarket data, not the database.
        """
        redeems = self.get_redeem_events(limit=1000)
        trades = self.get_trade_events(limit=1000)

        # Build trade lookup by asset
        trade_by_asset = {}
        for t in trades:
            asset_id = t.get("assetId", "")
            if asset_id and t.get("side") == "BUY":
                if asset_id not in trade_by_asset:
                    trade_by_asset[asset_id] = []
                trade_by_asset[asset_id].append(t)

        # Match redeems to trades
        total_cost = 0.0
        total_payout = 0.0
        wins = 0
        losses = 0

        for r in redeems:
            asset_id = r.get("assetId", "")
            payout = float(r.get("usdcSize", 0))

            if payout > 0:
                wins += 1
            else:
                losses += 1

            total_payout += payout

            # Find original trade cost
            if asset_id in trade_by_asset:
                for trade in trade_by_asset[asset_id]:
                    cost = float(trade.get("usdcSize", 0))
                    total_cost += cost
                    break  # Only count first trade

        return {
            "total_resolved": len(redeems),
            "wins": wins,
            "losses": losses,
            "win_rate": wins / len(redeems) if redeems else 0,
            "total_cost": total_cost,
            "total_payout": total_payout,
            "net_pnl": total_payout - total_cost
        }


def test():
    """Test the outcome sync module."""
    print("=" * 60)
    print("OUTCOME SYNC TEST")
    print("=" * 60)

    sync = OutcomeSync()

    # Get historical P&L from API
    print("\n1. Historical P&L from Polymarket API:")
    historical = sync.calculate_historical_pnl()
    print(f"   Total resolved: {historical['total_resolved']}")
    print(f"   Wins: {historical['wins']}, Losses: {historical['losses']}")
    print(f"   Win rate: {historical['win_rate']:.1%}")
    print(f"   Net P&L: ${historical['net_pnl']:.2f}")

    # Sync to database
    print("\n2. Syncing outcomes to database:")
    result = sync.sync_outcomes(verbose=True)

    # Show P&L by market type
    print("\n3. P&L by market type:")
    by_type = sync.get_pnl_by_market_type()
    for market_type, stats in by_type.items():
        edge = "EDGE" if stats["has_edge"] else "NO EDGE"
        print(f"   {market_type}: {stats['trades']} trades, "
              f"{stats['win_rate']:.1%} win rate, "
              f"${stats['avg_pnl']:.2f} avg P&L - {edge}")


if __name__ == "__main__":
    test()
