# Polymarket Trading Bot - Implementation Roadmap

**Generated:** 2026-01-12
**Objective:** Fix all tracking issues with specific, copy-paste-ready code changes

---

## Step 1: Create Persistent Database Directory

```bash
# Run this first
mkdir -p ~/.polymarket
```

---

## Step 2: Create the Outcome Sync Module

**Create new file:** `agents/polymarket/outcome_sync.py`

```python
"""
Polymarket Outcome Resolution Module

Syncs resolved market outcomes from Polymarket Data API to local database.
Uses REDEEM activity events to determine wins and losses.

Author: Auto-generated fix for BUG-002 (outcomes never recorded)
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
        self.db_path = db_path or os.path.expanduser("~/.polymarket/learning_trader.db")
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

        Returns stats about what was synced.
        """
        redeems = self.get_redeem_events()

        if verbose:
            print(f"Found {len(redeems)} REDEEM events from Polymarket")

        # Build lookup by asset ID
        redeem_by_asset = {}
        for r in redeems:
            asset_id = r.get("assetId", "")
            if asset_id:
                if asset_id not in redeem_by_asset:
                    redeem_by_asset[asset_id] = []
                redeem_by_asset[asset_id].append(r)

        # Connect to database
        if not os.path.exists(self.db_path):
            print(f"Database not found at {self.db_path}")
            return {"error": "database_not_found"}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get trades without recorded outcomes
        cursor.execute('''
            SELECT id, token_id, question, position_size, entry_price, market_type
            FROM predictions
            WHERE trade_executed = 1
            AND (actual_outcome IS NULL OR pnl IS NULL)
        ''')
        pending = cursor.fetchall()

        if verbose:
            print(f"Found {len(pending)} trades without recorded outcomes")

        matched = 0
        wins = 0
        losses = 0
        total_pnl = 0.0

        for trade_id, token_id, question, size, entry_price, market_type in pending:
            if not token_id:
                continue

            # Check if this token has a REDEEM event
            if token_id in redeem_by_asset:
                redeem = redeem_by_asset[token_id][0]  # Take first match
                usdc_payout = float(redeem.get("usdcSize", 0))

                # Calculate outcome and P&L
                cost = size * entry_price if size and entry_price else 0

                if usdc_payout > 0:
                    outcome = 1.0
                    pnl = usdc_payout - cost
                    wins += 1
                else:
                    outcome = 0.0
                    pnl = -cost
                    losses += 1

                total_pnl += pnl

                # Update database
                cursor.execute('''
                    UPDATE predictions
                    SET actual_outcome = ?,
                        pnl = ?,
                        position_open = 0,
                        resolved_at = ?
                    WHERE id = ?
                ''', (outcome, pnl, datetime.now().isoformat(), trade_id))

                matched += 1

                if verbose:
                    result = "WIN" if outcome == 1.0 else "LOSS"
                    print(f"   {result}: {question[:50]}... P&L: ${pnl:.2f}")

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
            results[market_type] = {
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
```

---

## Step 3: Modify Main Trading Script - Database Path

**File:** `scripts/python/learning_autonomous_trader.py`

**Find line 73 (approximately):**
```python
DB_PATH = "/tmp/learning_trader.db"
```

**Replace with:**
```python
import os

# Persistent database location (survives restarts)
DB_DIR = os.path.expanduser("~/.polymarket")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "learning_trader.db")
```

---

## Step 4: Modify Main Trading Script - Add Outcome Sync

**File:** `scripts/python/learning_autonomous_trader.py`

**Add import at top of file (around line 20):**
```python
from agents.polymarket.outcome_sync import OutcomeSync
```

**Add initialization after database setup (around line 150):**
```python
# Initialize outcome sync
outcome_sync = OutcomeSync(db_path=DB_PATH)
```

**Add sync function (add this new function around line 400):**
```python
def sync_resolved_outcomes():
    """
    Sync resolved market outcomes from Polymarket API.

    This is CRITICAL - without this, edge detection uses empty data.
    """
    try:
        result = outcome_sync.sync_outcomes(verbose=False)
        if result.get("matched", 0) > 0:
            logger.info(f"Synced {result['matched']} outcomes: "
                       f"{result['wins']}W/{result['losses']}L, "
                       f"P&L: ${result['total_pnl']:.2f}")
    except Exception as e:
        logger.error(f"Outcome sync failed: {e}")
```

**Add to main loop (find the main trading loop and add this at the start):**
```python
# Sync outcomes before making trading decisions
# This ensures edge detection uses current data
sync_resolved_outcomes()
```

---

## Step 5: Modify Main Trading Script - Fix Bankroll

**File:** `scripts/python/learning_autonomous_trader.py`

**Find the hardcoded BANKROLL (around line 74):**
```python
BANKROLL = 100.0
```

**Replace with:**
```python
def get_actual_bankroll() -> float:
    """Get actual USDC balance + position value from Polymarket."""
    try:
        from agents.polymarket.position_sync import PositionSync
        pos_sync = PositionSync(db_path=DB_PATH)

        usdc = polymarket_connector.get_usdc_balance()
        positions = pos_sync.get_portfolio_value()

        total = usdc + positions
        logger.info(f"Actual bankroll: ${total:.2f} (USDC: ${usdc:.2f}, Positions: ${positions:.2f})")
        return total
    except Exception as e:
        logger.error(f"Failed to get actual bankroll: {e}, using default")
        return 100.0

# Get actual bankroll on startup
BANKROLL = get_actual_bankroll()
```

---

## Step 6: Fix Trade History Database Path

**File:** `agents/learning/trade_history.py`

**Find the __init__ method (around line 35):**
```python
def __init__(self, db_path: str = "/tmp/trade_learning.db"):
```

**Replace with:**
```python
def __init__(self, db_path: str = None):
    if db_path is None:
        import os
        db_dir = os.path.expanduser("~/.polymarket")
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "learning_trader.db")
```

---

## Step 7: Fix Position Sync - Use Token ID Matching

**File:** `agents/polymarket/position_sync.py`

**Find the reconcile_positions method (around line 117):**

**Replace the matching logic (lines 150-165) with:**
```python
    def reconcile_positions(self, verbose: bool = True) -> Dict[str, Any]:
        """
        Sync local database with actual on-chain positions.
        Uses token_id matching for accuracy (not string matching).
        """
        # Get actual positions from API
        actual_positions = self.get_actual_positions()

        # Build set of actual asset IDs (token IDs)
        actual_asset_ids = set()
        for p in actual_positions:
            asset_id = p.get("asset", "") or p.get("assetId", "")
            if asset_id:
                actual_asset_ids.add(asset_id)

        if verbose:
            print(f"Actual positions from Polymarket API: {len(actual_positions)}")
            for p in actual_positions:
                print(f"   {p.get('title', 'Unknown')[:55]}... | {p.get('outcome')} | ${p.get('currentValue', 0):.2f}")

        # Connect to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all DB positions marked as open
        cursor.execute('''
            SELECT id, token_id, question FROM predictions
            WHERE trade_executed = 1 AND position_open = 1
        ''')
        db_positions = cursor.fetchall()

        if verbose:
            print(f"\nDB positions marked open: {len(db_positions)}")

        # Close positions that don't exist on-chain (using token_id)
        closed_count = 0
        kept_count = 0

        for pid, token_id, question in db_positions:
            # Match by token_id if available
            if token_id and token_id not in actual_asset_ids:
                cursor.execute(
                    'UPDATE predictions SET position_open = 0 WHERE id = ?',
                    (pid,)
                )
                closed_count += 1
                if verbose:
                    print(f"   Closed: {question[:50]}...")
            else:
                kept_count += 1

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
            print(f"\nReconciliation complete:")
            print(f"   Closed stale: {closed_count}")
            print(f"   Kept matching: {kept_count}")
            print(f"   Final open in DB: {final_open}")

        return result
```

---

## Step 8: Add Database Migration Script

**Create new file:** `scripts/migrate_database.py`

```python
#!/usr/bin/env python3
"""
Database Migration Script

Migrates data from /tmp to persistent storage and adds required columns.
Run this ONCE before restarting the bot.
"""

import os
import sqlite3
import shutil
from datetime import datetime

OLD_DB = "/tmp/learning_trader.db"
NEW_DIR = os.path.expanduser("~/.polymarket")
NEW_DB = os.path.join(NEW_DIR, "learning_trader.db")


def migrate():
    print("=" * 60)
    print("DATABASE MIGRATION")
    print("=" * 60)

    # Create new directory
    os.makedirs(NEW_DIR, exist_ok=True)
    print(f"\n1. Created directory: {NEW_DIR}")

    # Check for existing data
    if os.path.exists(OLD_DB):
        print(f"\n2. Found old database at {OLD_DB}")

        # Get row counts
        old_conn = sqlite3.connect(OLD_DB)
        old_cursor = old_conn.cursor()
        old_cursor.execute("SELECT COUNT(*) FROM predictions")
        old_count = old_cursor.fetchone()[0]
        old_conn.close()

        print(f"   Contains {old_count} predictions")

        # Copy if has data
        if old_count > 0:
            if os.path.exists(NEW_DB):
                backup = NEW_DB + f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy(NEW_DB, backup)
                print(f"   Backed up existing DB to {backup}")

            shutil.copy(OLD_DB, NEW_DB)
            print(f"   Copied data to {NEW_DB}")
        else:
            print("   No data to migrate")
    else:
        print(f"\n2. No old database found at {OLD_DB}")

    # Ensure new database exists and has required schema
    print("\n3. Ensuring database schema...")
    conn = sqlite3.connect(NEW_DB)
    cursor = conn.cursor()

    # Add columns if they don't exist
    columns_to_add = [
        ("resolved_at", "TEXT"),
        ("pnl", "REAL"),
        ("token_id", "TEXT"),
        ("market_type", "TEXT")
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE predictions ADD COLUMN {col_name} {col_type}")
            print(f"   Added column: {col_name}")
        except sqlite3.OperationalError:
            print(f"   Column exists: {col_name}")

    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_token_id ON predictions(token_id)",
        "CREATE INDEX IF NOT EXISTS idx_market_type ON predictions(market_type)",
        "CREATE INDEX IF NOT EXISTS idx_position_open ON predictions(position_open)",
        "CREATE INDEX IF NOT EXISTS idx_trade_executed ON predictions(trade_executed)"
    ]

    for idx in indexes:
        cursor.execute(idx)

    conn.commit()
    print("   Indexes created")

    # Show current state
    cursor.execute('''
        SELECT COUNT(*),
               SUM(trade_executed),
               SUM(actual_outcome IS NOT NULL)
        FROM predictions
    ''')
    total, executed, with_outcome = cursor.fetchone()

    print(f"\n4. Database state:")
    print(f"   Total predictions: {total or 0}")
    print(f"   Trades executed: {executed or 0}")
    print(f"   With outcomes: {with_outcome or 0}")

    conn.close()

    print(f"\n5. Migration complete!")
    print(f"   New database location: {NEW_DB}")
    print(f"\n   Next step: Run outcome_sync.py to populate P&L data")


if __name__ == "__main__":
    migrate()
```

---

## Step 9: Create Verification Script

**Create new file:** `scripts/verify_bot_fixes.py`

```python
#!/usr/bin/env python3
"""
Verification script to confirm all fixes are working.
Run this after applying all fixes.
"""

import os
import sys
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.expanduser("~/.polymarket/learning_trader.db")


def check_database_location():
    """Check database is in persistent location."""
    print("\n1. DATABASE LOCATION")
    print("-" * 40)

    if os.path.exists(DB_PATH):
        print(f"   Location: {DB_PATH}")
        print(f"   Persistent: YES")
        size = os.path.getsize(DB_PATH)
        print(f"   Size: {size:,} bytes")
        return True
    else:
        print(f"   ERROR: Database not found at {DB_PATH}")
        print(f"   Run: python scripts/migrate_database.py")
        return False


def check_outcomes_recorded():
    """Check if outcomes are being recorded."""
    print("\n2. OUTCOME RECORDING")
    print("-" * 40)

    if not os.path.exists(DB_PATH):
        print("   Skipped (database not found)")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(trade_executed) as executed,
               SUM(actual_outcome IS NOT NULL) as with_outcome,
               SUM(pnl IS NOT NULL) as with_pnl
        FROM predictions
    ''')
    total, executed, with_outcome, with_pnl = cursor.fetchone()

    print(f"   Total predictions: {total or 0}")
    print(f"   Trades executed: {executed or 0}")
    print(f"   With outcomes: {with_outcome or 0}")
    print(f"   With P&L: {with_pnl or 0}")

    if executed and executed > 0:
        outcome_rate = (with_outcome or 0) / executed * 100
        print(f"   Outcome coverage: {outcome_rate:.1f}%")

        if outcome_rate < 50:
            print("   WARNING: Low outcome coverage - run outcome_sync")

    conn.close()
    return (with_outcome or 0) > 0


def check_edge_data():
    """Check edge data by market type."""
    print("\n3. EDGE DATA BY MARKET TYPE")
    print("-" * 40)

    if not os.path.exists(DB_PATH):
        print("   Skipped (database not found)")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT market_type,
               COUNT(*) as trades,
               SUM(CASE WHEN actual_outcome = 1 THEN 1 ELSE 0 END) as wins,
               AVG(pnl) as avg_pnl,
               SUM(pnl) as total_pnl
        FROM predictions
        WHERE trade_executed = 1
        AND actual_outcome IS NOT NULL
        GROUP BY market_type
    ''')

    results = cursor.fetchall()

    if not results:
        print("   No edge data available")
        print("   Run: python -m agents.polymarket.outcome_sync")
        conn.close()
        return False

    for market_type, trades, wins, avg_pnl, total_pnl in results:
        win_rate = wins / trades if trades else 0
        edge = "EDGE" if (avg_pnl or 0) > 0 else "NO EDGE"
        print(f"   {market_type or 'unknown'}: {trades} trades, "
              f"{win_rate:.1%} win rate, "
              f"${avg_pnl or 0:.2f} avg P&L, "
              f"${total_pnl or 0:.2f} total - {edge}")

    conn.close()
    return True


def check_env_variables():
    """Check required environment variables."""
    print("\n4. ENVIRONMENT VARIABLES")
    print("-" * 40)

    from dotenv import load_dotenv
    load_dotenv()

    required = [
        "POLYMARKET_PROXY_ADDRESS",
        "POLYMARKET_API_KEY",
        "POLYMARKET_API_SECRET"
    ]

    all_set = True
    for var in required:
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." if len(value) > 8 else value
            print(f"   {var}: {masked}")
        else:
            print(f"   {var}: NOT SET")
            all_set = False

    return all_set


def main():
    print("=" * 60)
    print("POLYMARKET BOT FIX VERIFICATION")
    print("=" * 60)

    results = {
        "database": check_database_location(),
        "outcomes": check_outcomes_recorded(),
        "edge_data": check_edge_data(),
        "env_vars": check_env_variables()
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_good = True
    for check, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"   {check}: {status}")
        if not passed:
            all_good = False

    if all_good:
        print("\n   All checks passed! Bot is ready.")
    else:
        print("\n   Some checks failed. Review above and fix issues.")

    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## Execution Order

Run these steps in order:

```bash
# 1. Create persistent storage directory
mkdir -p ~/.polymarket

# 2. Migrate existing database (if any)
cd /home/tony/Dev/agents
python scripts/migrate_database.py

# 3. Sync outcomes from Polymarket
python -m agents.polymarket.outcome_sync

# 4. Verify everything is working
python scripts/verify_bot_fixes.py

# 5. Restart the trading bot
python scripts/python/learning_autonomous_trader.py
```

---

## Files Changed Summary

| File | Change Type | Priority |
|------|-------------|----------|
| `agents/polymarket/outcome_sync.py` | NEW | Critical |
| `scripts/migrate_database.py` | NEW | Critical |
| `scripts/verify_bot_fixes.py` | NEW | High |
| `scripts/python/learning_autonomous_trader.py` | MODIFY | Critical |
| `agents/learning/trade_history.py` | MODIFY | High |
| `agents/polymarket/position_sync.py` | MODIFY | High |

---

## Expected Results After Fixes

1. **Database persists** across restarts
2. **Outcomes sync** from Polymarket REDEEM events
3. **Edge detection** uses real P&L data
4. **Bot trades crypto** (where you have edge)
5. **Bot reduces sports/esports** (where you're losing)
6. **Position tracking** uses token IDs (accurate)
7. **Bankroll** reflects actual balance
