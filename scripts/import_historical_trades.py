#!/usr/bin/env python3
"""
Import Historical Trades from Polymarket API

Fetches all historical trades and redemptions from Polymarket Data API
and populates the database with accurate P&L data for edge detection.

This script:
1. Fetches all TRADE events (your buys)
2. Fetches all REDEEM events (resolved positions)
3. Matches trades to outcomes
4. Classifies by market type (crypto/sports/other)
5. Calculates P&L
6. Inserts into database
"""

import os
import sys
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Set
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Database path
DB_PATH = os.path.expanduser("~/.polymarket/learning_trader.db")
DATA_API_BASE = "https://data-api.polymarket.com"


def get_proxy_address():
    """Get Polymarket proxy address from environment."""
    addr = os.getenv("POLYMARKET_PROXY_ADDRESS")
    if not addr:
        raise ValueError("POLYMARKET_PROXY_ADDRESS not set")
    return addr


def fetch_activity(activity_type: str, limit: int = 1000) -> List[Dict]:
    """Fetch activity events from Polymarket API."""
    url = f"{DATA_API_BASE}/activity"
    params = {
        "user": get_proxy_address(),
        "type": activity_type,
        "limit": limit
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching {activity_type}: {e}")
        return []


def fetch_trades() -> List[Dict]:
    """Fetch all trade events."""
    return fetch_activity("TRADE", limit=1000)


def fetch_redeems() -> List[Dict]:
    """Fetch all redeem events (resolved positions)."""
    return fetch_activity("REDEEM", limit=1000)


def classify_market_type(title: str) -> str:
    """Classify market by type based on title."""
    if not title:
        return "other"

    title_lower = title.lower()

    # Crypto keywords
    crypto_keywords = [
        'bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol',
        'xrp', 'ripple', 'dogecoin', 'doge', 'crypto', 'coin',
        'cardano', 'ada', 'polkadot', 'dot', 'chainlink', 'link',
        'avalanche', 'avax', 'polygon', 'matic', 'shiba', 'pepe',
        'memecoin', 'altcoin', 'defi', 'nft'
    ]

    for keyword in crypto_keywords:
        if keyword in title_lower:
            return "crypto"

    # Sports keywords
    sports_keywords = [
        'nba', 'nfl', 'mlb', 'nhl', 'soccer', 'football', 'basketball',
        'baseball', 'hockey', 'tennis', 'golf', 'ufc', 'mma', 'boxing',
        'f1', 'formula', 'nascar', 'olympics', 'world cup', 'super bowl',
        'playoff', 'finals', 'championship', 'league', 'team', 'player',
        'game', 'match', 'vs', 'score', 'win', 'points', 'quarter',
        'lakers', 'celtics', 'warriors', 'bulls', 'knicks', 'heat',
        'cowboys', 'patriots', 'chiefs', 'eagles', 'yankees', 'dodgers',
        'islanders', 'rangers', 'bruins', 'maple leafs'
    ]

    for keyword in sports_keywords:
        if keyword in title_lower:
            return "sports"

    # Esports keywords
    esports_keywords = [
        'esport', 'e-sport', 'lol', 'league of legends', 'dota',
        'csgo', 'cs2', 'valorant', 'overwatch', 'fortnite',
        'pubg', 'apex', 'rocket league', 'starcraft', 'hearthstone',
        'gaming', 'twitch', 'streamer'
    ]

    for keyword in esports_keywords:
        if keyword in title_lower:
            return "esports"

    return "other"


def import_historical_data():
    """Main import function."""
    print("=" * 60)
    print("IMPORTING HISTORICAL TRADES FROM POLYMARKET")
    print("=" * 60)

    # Fetch data from API
    print("\n1. Fetching trade history from Polymarket API...")
    trades = fetch_trades()
    print(f"   Found {len(trades)} trade events")

    print("\n2. Fetching redemption history...")
    redeems = fetch_redeems()
    print(f"   Found {len(redeems)} redeem events")

    if not trades and not redeems:
        print("\n   No data found. Check POLYMARKET_PROXY_ADDRESS.")
        return

    # Build redeem lookup by conditionId (asset field is empty in redeems)
    # Also track by slug as backup
    redeem_by_condition = {}
    redeem_by_slug = {}
    for r in redeems:
        condition_id = r.get("conditionId", "")
        slug = r.get("slug", "")
        if condition_id:
            redeem_by_condition[condition_id] = r
        if slug:
            redeem_by_slug[slug] = r

    # Process trades and match to redemptions
    print("\n3. Processing trades and matching outcomes...")

    # Group trades by asset ID (multiple buys of same outcome)
    trades_by_asset = defaultdict(list)
    for t in trades:
        if t.get("side") == "BUY":
            asset_id = t.get("asset", "") or t.get("assetId", "")
            if asset_id:
                trades_by_asset[asset_id].append(t)

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure we have the right columns
    try:
        cursor.execute("ALTER TABLE predictions ADD COLUMN imported INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column exists

    # Track statistics
    stats = {
        "total_trades": 0,
        "matched": 0,
        "wins": 0,
        "losses": 0,
        "unresolved": 0,
        "by_type": defaultdict(lambda: {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0})
    }

    imported_assets: Set[str] = set()

    # Check what's already imported
    cursor.execute("SELECT token_id FROM predictions WHERE imported = 1")
    already_imported = {row[0] for row in cursor.fetchall() if row[0]}

    for asset_id, asset_trades in trades_by_asset.items():
        if asset_id in already_imported:
            continue

        # Aggregate all buys for this asset
        total_cost = sum(float(t.get("usdcSize", 0)) for t in asset_trades)
        total_size = sum(float(t.get("size", 0)) for t in asset_trades)

        # Get first trade for metadata
        first_trade = asset_trades[0]
        title = first_trade.get("title", first_trade.get("market", "Unknown"))
        outcome = first_trade.get("outcome", "")
        timestamp = first_trade.get("timestamp", datetime.now().isoformat())

        # Classify market type
        market_type = classify_market_type(title)

        # Check if resolved - try conditionId first, then slug
        condition_id = first_trade.get("conditionId", "")
        slug = first_trade.get("slug", "")
        redeem = redeem_by_condition.get(condition_id) or redeem_by_slug.get(slug)

        if redeem:
            payout = float(redeem.get("usdcSize", 0))
            pnl = payout - total_cost
            actual_outcome = 1.0 if payout > 0 else 0.0
            is_win = payout > 0
            resolved = True
        else:
            pnl = 0
            actual_outcome = None
            is_win = None
            resolved = False

        # Calculate entry price
        entry_price = total_cost / total_size if total_size > 0 else 0.5

        # Insert into database
        cursor.execute('''
            INSERT INTO predictions (
                timestamp, market_id, question, market_type,
                predicted_outcome, predicted_probability, confidence,
                token_id, trade_executed, trade_size_usdc, trade_price,
                position_open, actual_outcome, pnl, imported, strategy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp,
            asset_id[:20] if asset_id else "unknown",
            title,
            market_type,
            outcome,
            entry_price,
            0.6,  # Default confidence
            asset_id,
            1,  # trade_executed
            total_cost,
            entry_price,
            0 if resolved else 1,  # position_open
            actual_outcome,
            pnl if resolved else None,
            1,  # imported flag
            "historical_import"  # strategy
        ))

        imported_assets.add(asset_id)
        stats["total_trades"] += 1
        stats["by_type"][market_type]["trades"] += 1

        if resolved:
            stats["matched"] += 1
            if is_win:
                stats["wins"] += 1
                stats["by_type"][market_type]["wins"] += 1
            else:
                stats["losses"] += 1
                stats["by_type"][market_type]["losses"] += 1
            stats["by_type"][market_type]["pnl"] += pnl
        else:
            stats["unresolved"] += 1

    conn.commit()
    conn.close()

    # Print results
    print(f"\n4. Import complete!")
    print(f"   Total positions imported: {stats['total_trades']}")
    print(f"   Resolved (with outcome): {stats['matched']}")
    print(f"   Still open: {stats['unresolved']}")
    print(f"   Wins: {stats['wins']}, Losses: {stats['losses']}")

    if stats['matched'] > 0:
        win_rate = stats['wins'] / stats['matched'] * 100
        print(f"   Win rate: {win_rate:.1f}%")

    print(f"\n5. P&L by market type:")
    print("-" * 50)

    total_pnl = 0
    for mtype in ["crypto", "sports", "esports", "other"]:
        data = stats["by_type"][mtype]
        if data["trades"] > 0:
            wr = data["wins"] / (data["wins"] + data["losses"]) * 100 if (data["wins"] + data["losses"]) > 0 else 0
            edge = "EDGE" if data["pnl"] > 0 else "NO EDGE"
            print(f"   {mtype:10} | {data['trades']:3} trades | {wr:5.1f}% WR | ${data['pnl']:+8.2f} | {edge}")
            total_pnl += data["pnl"]

    print("-" * 50)
    print(f"   {'TOTAL':10} | {stats['matched']:3} resolved | ${total_pnl:+8.2f}")

    print("\n" + "=" * 60)
    print("EDGE DETECTION NOW HAS ACCURATE DATA!")
    print("=" * 60)
    print("""
Based on your actual P&L:
- Trade markets where you have EDGE (positive P&L)
- Skip markets where you have NO EDGE (negative P&L)

Run the bot to start using this data:
  python scripts/python/learning_autonomous_trader.py --live --continuous
""")


if __name__ == "__main__":
    import_historical_data()
