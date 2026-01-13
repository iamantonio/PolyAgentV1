# Polymarket Trading Bot - Comprehensive Bug Report

**Generated:** 2026-01-12
**Status:** Complete Analysis
**Severity:** CRITICAL - Bot is making decisions based on incorrect/missing data

---

## Executive Summary

The trading bot has been **doing the opposite of what it should**:
- **Skipping crypto markets** (which were actually +$113.29 PROFIT)
- **Trading sports/esports** (which were actually -$164.35 LOSS combined)

Root cause: The bot's database stores ZERO resolved outcomes, so edge detection uses stale/empty data.

---

## Actual Performance (From User's Polymarket Portfolio)

| Market Type | Win Rate | Actual P&L | Bot's Decision |
|-------------|----------|------------|----------------|
| Crypto | 48.6% (52W/55L) | **+$113.29** | SKIP (wrong!) |
| Sports | 50.0% (18W/18L) | **-$69.83** | TRADE (wrong!) |
| Other | 53.8% (7W/6L) | **-$94.52** | TRADE (wrong!) |

**Total:** $183.18 deposited → $116.80 remaining = **-$66.38 loss**

---

## CRITICAL BUGS (Priority 1 - Fix Immediately)

### BUG-001: Database in Ephemeral Storage
**File:** `scripts/python/learning_autonomous_trader.py:73`
```python
DB_PATH = "/tmp/learning_trader.db"  # CRITICAL: Data lost on restart!
```
**Impact:** All historical data, P&L records, and learning wiped on every system restart.
**Fix:** Move to persistent storage like `~/.polymarket/trader.db` or project directory.

---

### BUG-002: Outcomes Never Recorded
**File:** `scripts/python/learning_autonomous_trader.py`
**Evidence:** Database has 1,049 predictions, 14 trades, but **0 outcomes recorded**
```sql
SELECT COUNT(*), SUM(trade_executed), SUM(actual_outcome IS NOT NULL) FROM predictions;
-- Result: 1049 | 14 | 0
```
**Root Cause:** The `record_outcome()` function exists in `trade_history.py:242` but is **never called** from the main trading script.
**Impact:** Edge detection uses empty data, making random or inverted decisions.
**Fix:** Implement outcome resolution by syncing REDEEM events from Polymarket Data API.

---

### BUG-003: Edge Detection Uses Empty Data
**File:** `agents/learning/trade_history.py:474-507`
```python
def get_market_edge(self, market_type: str):
    # Returns has_edge = avg_pnl_per_trade > 0
    # But avg_pnl_per_trade is calculated from... 0 recorded outcomes
```
**Impact:** Edge calculation returns incorrect values based on stale/missing data.
**Fix:** First fix BUG-002, then edge detection will work correctly.

---

### BUG-004: Stale Log Statistics
**File:** `logs/live_trading.log`
The log shows outdated statistics from a previous session:
```
crypto: 25.0% win rate, $-0.98 avg P&L (4 trades)
```
But actual crypto performance was 48.6% win rate with +$113.29 profit.
**Root Cause:** Stats calculated from empty/reset database due to BUG-001.

---

## HIGH PRIORITY BUGS (Priority 2)

### BUG-005: Bankroll Not Synced with Actual Balance
**File:** `scripts/python/learning_autonomous_trader.py:74`
```python
BANKROLL = 100.0  # Hardcoded, never updated!
```
**Impact:** Position sizing based on wrong capital amount.
**Fix:** Sync with actual USDC balance from Polymarket API on startup.

---

### BUG-006: Position Count Mismatch
**Evidence from logs:**
```
Position mismatch: DB says 4 open, API says 11 actual
```
**Root Cause:** String-based matching in `position_sync.py:150-155` is fragile:
```python
is_actual = any(
    q_prefix in title or title in q_prefix
    for title in actual_titles
)
```
**Fix:** Use token_id matching instead of title substring matching.

---

### BUG-007: USDC Balance Calculation Confusing
**File:** `agents/polymarket/polymarket.py`
```python
balance_res / 10e5  # This equals 10^6 but is confusing
```
**Note:** This actually works (10e5 = 1,000,000) but should be `10**6` for clarity.

---

## MEDIUM PRIORITY BUGS (Priority 3)

### BUG-008: No HTTP Timeouts
**File:** `agents/polymarket/polymarket.py`
API calls have no timeout set, could hang indefinitely.
**Fix:** Add `timeout=30` to all `requests.get()` calls.

---

### BUG-009: No Rate Limiting
**Impact:** Could get rate-limited by Polymarket API during heavy usage.
**Fix:** Add exponential backoff and rate limiting.

---

### BUG-010: Case-Sensitive Market Classification
**File:** `scripts/python/learning_autonomous_trader.py:699-745`
```python
crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', ...]
# But market titles might be "Bitcoin" or "BITCOIN"
```
**Fix:** Normalize to lowercase before matching.

---

### BUG-011: P&L Formula Inconsistency
**File:** `agents/learning/trade_history.py`
- Resolution P&L: `position_size * (outcome - entry_price)`
- Manual close P&L: `exit_price - entry_price`

These should be consistent.

---

### BUG-012: MagicLink Proxy Address
**User Note:** Uses Google login via MagicLink, creating a proxy wallet.
**Current:** `POLYMARKET_PROXY_ADDRESS` env variable exists in `position_sync.py`
**Verify:** Ensure this is correctly set and used consistently across all API calls.

---

## DESIGN ISSUES (Priority 4)

### DESIGN-001: No Outcome Resolution Pipeline
The bot places trades but has no mechanism to:
1. Detect when markets resolve
2. Fetch resolution outcomes
3. Calculate actual P&L
4. Update learning models

**Solution:** Implement REDEEM event sync from Polymarket Data API:
```python
# Polymarket Data API has this data:
GET /activity?user={proxy_address}&type=REDEEM
# Returns: usdcSize > 0 = WIN, usdcSize = 0 = LOSS
```

---

### DESIGN-002: Learning Loop Broken
1. Bot makes prediction → recorded
2. Trade executed → recorded
3. Market resolves → **NOT RECORDED**
4. Edge detection → uses empty data
5. Future decisions → based on nothing

---

### DESIGN-003: No Backfill Capability
When database resets (BUG-001), there's no way to:
- Import historical trades from Polymarket
- Reconstruct P&L history
- Restore learning state

---

## Data Flow Diagram (Current - Broken)

```
Polymarket API → Market Discovery → Prediction → Trade Execution
                                                        ↓
                                              [Database: /tmp/...]
                                                        ↓
                                              [Outcomes: NEVER RECORDED]
                                                        ↓
                                              Edge Detection → [Empty Data]
                                                        ↓
                                              Skip/Trade Decision → [WRONG]
```

## Data Flow Diagram (Fixed)

```
Polymarket API → Market Discovery → Prediction → Trade Execution
       ↓                                                ↓
[REDEEM Events] ← Market Resolution ←─────────────────┘
       ↓
[Outcome Sync Pipeline]
       ↓
[Database: ~/.polymarket/trader.db] (persistent!)
       ↓
Edge Detection → [Accurate P&L Data]
       ↓
Skip/Trade Decision → [CORRECT]
```

---

## Verification Commands

```bash
# Check current database state
sqlite3 /tmp/learning_trader.db "SELECT COUNT(*), SUM(trade_executed), SUM(actual_outcome IS NOT NULL) FROM predictions;"

# Check Polymarket positions via API
curl "https://data-api.polymarket.com/positions?user=${POLYMARKET_PROXY_ADDRESS}&limit=50"

# Check REDEEM events (resolved markets)
curl "https://data-api.polymarket.com/activity?user=${POLYMARKET_PROXY_ADDRESS}&type=REDEEM&limit=100"
```

---

## Summary Table

| Bug ID | Severity | Component | Status |
|--------|----------|-----------|--------|
| BUG-001 | CRITICAL | Database Path | Open |
| BUG-002 | CRITICAL | Outcome Recording | Open |
| BUG-003 | CRITICAL | Edge Detection | Open |
| BUG-004 | HIGH | Log Stats | Open |
| BUG-005 | HIGH | Bankroll Sync | Open |
| BUG-006 | HIGH | Position Matching | Open |
| BUG-007 | LOW | USDC Calc | Open |
| BUG-008 | MEDIUM | HTTP Timeouts | Open |
| BUG-009 | MEDIUM | Rate Limiting | Open |
| BUG-010 | MEDIUM | Case Sensitivity | Open |
| BUG-011 | MEDIUM | P&L Formula | Open |
| BUG-012 | MEDIUM | Proxy Address | Verify |
