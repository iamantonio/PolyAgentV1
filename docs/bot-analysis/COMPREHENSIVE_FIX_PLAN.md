# Polymarket Trading Bot - Comprehensive Fix Plan

**Generated:** 2026-01-12
**Goal:** Fix all data tracking issues so the bot makes decisions based on accurate P&L data

---

## Phase 1: Critical Infrastructure Fixes (Do First)

### 1.1 Move Database to Persistent Storage

**Current:** `/tmp/learning_trader.db` (wiped on restart)
**New:** `~/.polymarket/learning_trader.db` (persistent)

**Files to modify:**
- `scripts/python/learning_autonomous_trader.py:73`
- `agents/learning/trade_history.py:__init__`
- Any other files referencing `/tmp/*.db`

**Code change:**
```python
# Old
DB_PATH = "/tmp/learning_trader.db"

# New
import os
DB_DIR = os.path.expanduser("~/.polymarket")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "learning_trader.db")
```

---

### 1.2 Implement Outcome Resolution Pipeline

**New file:** `agents/polymarket/outcome_sync.py`

This is the most critical fix. The bot needs to:
1. Periodically check for resolved markets
2. Fetch REDEEM events from Polymarket Data API
3. Match trades to resolutions
4. Calculate actual P&L
5. Update database with outcomes
6. Trigger learning updates

**Implementation:**

```python
"""
Outcome Resolution Pipeline

Syncs resolved market outcomes from Polymarket to local database.
Uses REDEEM events from Data API to determine wins/losses.
"""

import sqlite3
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os

class OutcomeSync:
    """Syncs market resolution outcomes to local database."""

    DATA_API_BASE = "https://data-api.polymarket.com"

    def __init__(self, db_path: str, proxy_address: str):
        self.db_path = db_path
        self.proxy_address = proxy_address

    def get_redeem_events(self, since_hours: int = 168) -> List[Dict]:
        """
        Fetch REDEEM events (resolved markets) from Polymarket.

        REDEEM events indicate:
        - usdcSize > 0: WIN (received payout)
        - usdcSize = 0: LOSS (position worthless)
        """
        url = f"{self.DATA_API_BASE}/activity"
        params = {
            "user": self.proxy_address,
            "type": "REDEEM",
            "limit": 500
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            events = resp.json()

            # Filter to recent events
            cutoff = datetime.now() - timedelta(hours=since_hours)
            recent = []
            for e in events:
                ts = e.get("timestamp", "")
                if ts:
                    event_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if event_time.replace(tzinfo=None) > cutoff:
                        recent.append(e)

            return recent
        except Exception as e:
            print(f"Error fetching REDEEM events: {e}")
            return []

    def match_and_record_outcomes(self) -> Dict:
        """
        Match REDEEM events to trades and record outcomes.

        Returns stats about what was updated.
        """
        redeem_events = self.get_redeem_events()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get trades without recorded outcomes
        cursor.execute('''
            SELECT id, token_id, question, position_size, entry_price
            FROM predictions
            WHERE trade_executed = 1 AND actual_outcome IS NULL
        ''')
        pending_trades = cursor.fetchall()

        matched = 0
        wins = 0
        losses = 0

        for trade_id, token_id, question, size, entry_price in pending_trades:
            # Try to match by token_id first
            for event in redeem_events:
                event_token = event.get("assetId", "")

                if token_id and event_token == token_id:
                    usdc_size = float(event.get("usdcSize", 0))

                    # Determine outcome
                    if usdc_size > 0:
                        outcome = 1.0  # WIN
                        pnl = usdc_size - (size * entry_price)
                        wins += 1
                    else:
                        outcome = 0.0  # LOSS
                        pnl = -(size * entry_price)
                        losses += 1

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
                    break

        conn.commit()
        conn.close()

        return {
            "redeem_events": len(redeem_events),
            "pending_trades": len(pending_trades),
            "matched": matched,
            "wins": wins,
            "losses": losses,
            "synced_at": datetime.now().isoformat()
        }

    def backfill_historical(self) -> Dict:
        """
        Backfill P&L from all historical REDEEM events.

        Use this after moving to persistent storage to populate history.
        """
        # Get ALL REDEEM events (not just recent)
        url = f"{self.DATA_API_BASE}/activity"
        all_redeems = []

        params = {
            "user": self.proxy_address,
            "type": "REDEEM",
            "limit": 500
        }

        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            all_redeems = resp.json()
        except Exception as e:
            print(f"Error fetching historical REDEEM events: {e}")
            return {"error": str(e)}

        # Calculate totals by market type
        wins = sum(1 for r in all_redeems if float(r.get("usdcSize", 0)) > 0)
        losses = sum(1 for r in all_redeems if float(r.get("usdcSize", 0)) == 0)
        total_payout = sum(float(r.get("usdcSize", 0)) for r in all_redeems)

        return {
            "total_redeems": len(all_redeems),
            "wins": wins,
            "losses": losses,
            "total_payout": total_payout,
            "win_rate": wins / len(all_redeems) if all_redeems else 0
        }
```

---

### 1.3 Integrate Outcome Sync into Main Trading Loop

**File:** `scripts/python/learning_autonomous_trader.py`

Add to the main loop:
```python
from agents.polymarket.outcome_sync import OutcomeSync

# At startup
outcome_sync = OutcomeSync(DB_PATH, os.getenv("POLYMARKET_PROXY_ADDRESS"))

# In main loop, before checking edge
def sync_outcomes():
    result = outcome_sync.match_and_record_outcomes()
    if result["matched"] > 0:
        logger.info(f"Synced {result['matched']} outcomes: {result['wins']}W/{result['losses']}L")

# Call periodically (every 10 minutes or before edge checks)
sync_outcomes()
```

---

## Phase 2: Data Accuracy Fixes

### 2.1 Fix Bankroll Sync

**File:** `scripts/python/learning_autonomous_trader.py`

```python
# Replace hardcoded BANKROLL
# Old:
BANKROLL = 100.0

# New:
def get_actual_bankroll() -> float:
    """Get actual USDC balance from Polymarket."""
    try:
        balance = polymarket.get_usdc_balance()
        positions_value = position_sync.get_portfolio_value()
        return balance + positions_value
    except Exception as e:
        logger.error(f"Failed to get bankroll: {e}")
        return 100.0  # Fallback

BANKROLL = get_actual_bankroll()
```

---

### 2.2 Fix Position Matching

**File:** `agents/polymarket/position_sync.py:150-155`

```python
# Old (fragile string matching):
is_actual = any(
    q_prefix in title or title in q_prefix
    for title in actual_titles
)

# New (token_id matching):
def reconcile_positions(self, verbose: bool = True) -> Dict[str, Any]:
    # Get actual positions with token IDs
    actual_positions = self.get_actual_positions()
    actual_token_ids = {p.get("asset", "") for p in actual_positions}

    # Match by token_id instead of title
    cursor.execute('''
        SELECT id, token_id, question FROM predictions
        WHERE trade_executed = 1 AND position_open = 1
    ''')

    for pid, token_id, question in cursor.fetchall():
        if token_id and token_id not in actual_token_ids:
            # Position no longer exists on-chain
            cursor.execute(
                'UPDATE predictions SET position_open = 0 WHERE id = ?',
                (pid,)
            )
```

---

### 2.3 Fix Case-Sensitive Classification

**File:** `scripts/python/learning_autonomous_trader.py:699-745`

```python
def _classify_market_type(self, question: str) -> str:
    """Classify market by type using case-insensitive matching."""
    q_lower = question.lower()  # Normalize to lowercase

    crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol',
                       'xrp', 'ripple', 'dogecoin', 'doge', 'crypto', 'coin']

    for keyword in crypto_keywords:
        if keyword in q_lower:
            return 'crypto'

    # ... rest of classification
```

---

## Phase 3: Edge Detection Fix

### 3.1 Recalculate Edge After Outcome Sync

After fixing BUG-002 (outcomes never recorded), the edge detection will automatically start working correctly because it will have real data.

**File:** `agents/learning/trade_history.py`

```python
def get_market_edge(self, market_type: str) -> Dict:
    """
    Calculate edge for market type based on ACTUAL recorded outcomes.

    Returns:
        has_edge: bool - whether avg P&L > 0
        avg_pnl: float - average P&L per trade
        sample_size: int - number of resolved trades
        confidence: str - low/medium/high based on sample size
    """
    cursor = self.conn.cursor()
    cursor.execute('''
        SELECT pnl FROM predictions
        WHERE market_type = ?
        AND trade_executed = 1
        AND actual_outcome IS NOT NULL
        AND pnl IS NOT NULL
    ''', (market_type,))

    pnls = [row[0] for row in cursor.fetchall()]

    if len(pnls) < 5:
        return {
            "has_edge": True,  # Not enough data, default to trading
            "avg_pnl": 0,
            "sample_size": len(pnls),
            "confidence": "insufficient_data"
        }

    avg_pnl = sum(pnls) / len(pnls)

    return {
        "has_edge": avg_pnl > 0,
        "avg_pnl": avg_pnl,
        "sample_size": len(pnls),
        "confidence": "high" if len(pnls) > 50 else "medium" if len(pnls) > 20 else "low"
    }
```

---

## Phase 4: API Reliability

### 4.1 Add Timeouts to All API Calls

**File:** `agents/polymarket/polymarket.py`

```python
# Add timeout to all requests
DEFAULT_TIMEOUT = 30

resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
```

### 4.2 Add Retry Logic

```python
import time
from functools import wraps

def with_retry(max_retries=3, backoff_factor=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = backoff_factor ** attempt
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator

@with_retry(max_retries=3)
def get_positions(self):
    # ... existing code
```

---

## Phase 5: Database Schema Updates

### 5.1 Add Missing Columns

```sql
-- Add columns for better tracking
ALTER TABLE predictions ADD COLUMN resolved_at TEXT;
ALTER TABLE predictions ADD COLUMN pnl REAL;
ALTER TABLE predictions ADD COLUMN token_id TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_token_id ON predictions(token_id);
CREATE INDEX IF NOT EXISTS idx_market_type ON predictions(market_type);
CREATE INDEX IF NOT EXISTS idx_position_open ON predictions(position_open);
```

---

## Phase 6: Verification and Testing

### 6.1 Verification Script

Create `scripts/verify_fixes.py`:
```python
"""Verify all fixes are working correctly."""

import sqlite3
import os

DB_PATH = os.path.expanduser("~/.polymarket/learning_trader.db")

def verify():
    print("=" * 60)
    print("POLYMARKET BOT FIX VERIFICATION")
    print("=" * 60)

    # 1. Check database location
    print(f"\n1. Database location: {DB_PATH}")
    print(f"   Exists: {os.path.exists(DB_PATH)}")
    print(f"   Persistent: {'Yes' if not DB_PATH.startswith('/tmp') else 'NO - FIX NEEDED'}")

    if not os.path.exists(DB_PATH):
        print("   Database not found - run migration first")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 2. Check outcomes recorded
    cursor.execute('''
        SELECT COUNT(*), SUM(actual_outcome IS NOT NULL)
        FROM predictions WHERE trade_executed = 1
    ''')
    total, with_outcome = cursor.fetchone()
    print(f"\n2. Outcome recording:")
    print(f"   Total trades: {total}")
    print(f"   With outcomes: {with_outcome or 0}")
    print(f"   Status: {'OK' if with_outcome and with_outcome > 0 else 'BROKEN - outcomes not recorded'}")

    # 3. Check edge data
    cursor.execute('''
        SELECT market_type, COUNT(*), AVG(pnl)
        FROM predictions
        WHERE trade_executed = 1 AND pnl IS NOT NULL
        GROUP BY market_type
    ''')
    edges = cursor.fetchall()
    print(f"\n3. Edge data by market type:")
    if edges:
        for market_type, count, avg_pnl in edges:
            edge = "EDGE" if avg_pnl and avg_pnl > 0 else "NO EDGE"
            print(f"   {market_type}: {count} trades, avg P&L ${avg_pnl:.2f} - {edge}")
    else:
        print("   No edge data - outcomes not recorded yet")

    conn.close()

    print("\n" + "=" * 60)
    print("Verification complete")

if __name__ == "__main__":
    verify()
```

---

## Implementation Priority Order

1. **IMMEDIATE (Today):**
   - Phase 1.1: Move database to persistent storage
   - Phase 1.2: Create outcome_sync.py
   - Phase 1.3: Integrate into main loop

2. **HIGH (This Week):**
   - Phase 2.1: Fix bankroll sync
   - Phase 2.2: Fix position matching
   - Phase 5.1: Database schema updates

3. **MEDIUM (Next Week):**
   - Phase 2.3: Fix case-sensitive classification
   - Phase 3.1: Verify edge detection works
   - Phase 4.1-4.2: API reliability

4. **LOW (Ongoing):**
   - Phase 6: Verification and monitoring

---

## Expected Outcome After Fixes

| Metric | Before | After |
|--------|--------|-------|
| Outcomes recorded | 0 | All resolved trades |
| Edge data accuracy | 0% | 100% |
| Database persistence | No | Yes |
| Position sync accuracy | ~60% | 100% |
| Decision correctness | Inverted | Correct |

**After fixes, the bot will:**
1. Trade crypto markets (where you have +$113 edge)
2. Skip or reduce sports/esports (where you have -$164 loss)
3. Learn from actual outcomes, not stale data
4. Persist learning across restarts
