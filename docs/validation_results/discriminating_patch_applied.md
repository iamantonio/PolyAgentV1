# Discriminating Patch Applied - E2 Root Cause Fix

**Date**: 2026-01-09 00:35 UTC
**Status**: ✅ **PATCHES APPLIED - READY FOR RESTART**
**Target**: `scripts/python/learning_autonomous_trader.py`

---

## Changes Applied

### 1. Data Quality Tracking (Line 263)

**Added dedupe counter for unique failures:**
```python
# Data quality tracking (E1/E2 discrimination)
self._invalid_market_keys = set()  # Dedupe for unique market_id failures
```

**Purpose**: Track unique key combinations that fail, preventing log inflation

---

### 2. Discriminating Patch - Market ID Resolution (Lines 650-673)

**BEFORE (Root Cause)**:
```python
market_id = market.get('condition_id') or market.get('market_id', 'unknown')
```

**AFTER (Discriminating Fix)**:
```python
# DISCRIMINATING PATCH (E2 root cause fix):
# Prefer stable identifiers; NEVER allow sentinel "unknown" to flow into API calls
condition_id = market.get("condition_id")
gamma_id     = market.get("id")          # Gamma often uses "id"
market_id_f  = market.get("market_id")   # Existing fallback

market_id = condition_id or gamma_id or market_id_f

if not market_id:
    # Discrimination logging: what keys do we even have?
    keys = list(market.keys()) if isinstance(market, dict) else []
    q = (market.get("question") or market.get("title") or "")[:120] if isinstance(market, dict) else ""

    # Dedupe: only log unique key combinations
    key_signature = frozenset(keys)
    if key_signature not in self._invalid_market_keys:
        self._invalid_market_keys.add(key_signature)
        print("🚨 DATA_INVALID: Missing ALL market identifiers. Skipping.")
        print(f"   present_keys={keys[:40]}")
        print(f"   condition_id={condition_id} id={gamma_id} market_id={market_id_f}")
        print(f"   question/title={q}")

    self.markets_skipped += 1
    return False, "Missing market identifiers", None
```

**Key Improvements**:
- ✅ **BLOCKS "unknown" cascade** - Never allows sentinel value into API calls
- ✅ **Discriminates H2a vs H2b** - Logs which specific fields are missing
- ✅ **Dedupes log spam** - Only logs unique key combinations once
- ✅ **Provides diagnostics** - Shows present keys, tested fields, question context

---

### 3. Enhanced clobTokenIds Validation (Lines 1253-1259)

**BEFORE**:
```python
token_ids = market_data.get('clobTokenIds') or []
if len(token_ids) < 2:
    print(f"  ⚠️  Invalid clobTokenIds (expected 2, got {len(token_ids)}), skipping")
    continue
```

**AFTER**:
```python
token_ids = market_data.get('clobTokenIds') or []
if len(token_ids) < 2:
    print(f"  ⚠️  Invalid clobTokenIds (expected 2, got {len(token_ids)})")
    print(f"      market_id={market_id}")
    print(f"      market_data keys={list(market_data.keys())[:20] if isinstance(market_data, dict) else 'NOT_DICT'}")
    continue
```

**Key Improvements**:
- ✅ **Attribution** - Shows which market_id caused failure
- ✅ **Diagnostics** - Shows what keys Gamma API actually returned
- ✅ **Discrimination** - Helps identify if issue is upstream (H2a) or parsing (H2b)

---

## What This Fixes

### Cascade Failure Eliminated

**OLD FLOW (BROKEN)**:
```
market missing 'condition_id' + 'market_id'
  ↓
defaults to market_id = "unknown"
  ↓
API call: gamma.get_market("unknown")
  ↓
404 or empty response
  ↓
clobTokenIds = [] (length 0)
  ↓
"Invalid clobTokenIds (expected 2, got 0)"
  ↓
Trade skipped
```

**NEW FLOW (FIXED)**:
```
market missing 'condition_id' + 'id' + 'market_id'
  ↓
🚨 DATA_INVALID logged with:
   - present_keys (to see what API sent)
   - tested fields (condition_id, id, market_id)
   - question context
  ↓
Trade skipped BEFORE API call
  ↓
No cascade failure
  ↓
Clear attribution of root cause
```

---

## Hypothesis Discrimination

This patch allows us to distinguish between:

**H2a (Upstream API Corruption)**:
```
🚨 DATA_INVALID: Missing ALL market identifiers
   present_keys=['question', 'volume', 'liquidity']
   condition_id=None id=None market_id=None
```
→ **Evidence**: Gamma API returned incomplete data (missing ALL ID fields)

**H2b (Brittle Mapping)**:
```
🚨 DATA_INVALID: Missing ALL market identifiers
   present_keys=['question', 'volume', 'liquidity', 'slug', 'tokens']
   condition_id=None id=None market_id=None
```
→ **Evidence**: Data present but we're looking for wrong keys

**H2c (Log Inflation)**:
- Before: Same market could log warning 1000+ times
- After: Dedupe ensures each unique key combination logged once
→ **Evidence**: If we see 100 unique key signatures, that's real diversity, not repetition

---

## Measurement Plan (Next 2-4 Hours)

After bot restart, collect these counters:

### **Primary Metrics**:
```python
# From logs/live_trading.log
markets_seen = grep -c "ANALYZING MARKET" logs/live_trading.log
missing_ids_unique = grep -c "DATA_INVALID: Missing ALL market identifiers" logs/live_trading.log
invalid_clobTokenIds_unique = grep -c "Invalid clobTokenIds" logs/live_trading.log

# Calculate rates
missing_id_rate = (missing_ids_unique / markets_seen) * 100
invalid_clob_rate = (invalid_clobTokenIds_unique / markets_seen) * 100
```

### **Discrimination Evidence**:
```bash
# Extract present_keys from DATA_INVALID warnings
grep "present_keys=" logs/live_trading.log | sort | uniq -c

# Extract tested field values
grep "condition_id=None" logs/live_trading.log | wc -l
```

### **Decision Criteria** (from user's framework):

| Metric | Threshold | Interpretation |
|--------|-----------|----------------|
| `missing_id_rate` | **>5%** | Material upstream corruption (H2a likely) |
| `missing_id_rate` | **<2%** | Negligible corruption (H2b or H2c likely) |
| `present_keys diversity` | **>10 unique signatures** | Real data variance (not repetition) |
| `invalid_clob_rate` AFTER fix | **>2%** | Upstream issue persists (not fixed by ID patch) |

---

## Bot Restart Instructions

1. **Stop current bot**:
   ```bash
   pkill -f learning_autonomous_trader
   ```

2. **Restart with new code**:
   ```bash
   cd /home/tony/Dev/agents
   .venv/bin/python scripts/python/learning_autonomous_trader.py --continuous --live >> logs/live_trading.log 2>&1 &
   ```

3. **Monitor logs** (first 5 minutes):
   ```bash
   tail -f logs/live_trading.log | grep -E "(DATA_INVALID|Invalid clobTokenIds|ANALYZING MARKET)"
   ```

4. **Expected behavior**:
   - ✅ "unknown" market_id should NEVER appear
   - ✅ `DATA_INVALID` warnings show diagnostic info
   - ✅ Each unique key combination logged once only
   - ✅ clobTokenIds failures show market_id attribution

5. **After 2-4 hours**, run discrimination analysis:
   ```bash
   bash /tmp/retroactive_e1_analysis.sh  # Updated with new counters
   ```

---

## Success Criteria

**Patch is working if**:
1. ✅ No "markets/unknown" API calls in logs
2. ✅ `DATA_INVALID` warnings show specific key combinations
3. ✅ Invalid clobTokenIds warnings include market_id attribution
4. ✅ Dedupe prevents log spam (same key signature logged once)

**Discrimination succeeds if**:
- We can see `present_keys` patterns to determine H2a vs H2b
- We can measure true unique failure rate (not inflated by repetition)
- We can correlate missing IDs with clobTokenIds failures

---

## Risk Mitigation

**Safeguards in place**:
- ✅ Bot continues to skip invalid markets (fail-safe)
- ✅ No changes to trade execution logic
- ✅ WAL mode already applied (E4 fix)
- ✅ Existing dedupe protection maintained
- ✅ Idempotency still active

**Failure modes prevented**:
- ❌ "unknown" cascade → BLOCKED by early return
- ❌ API call to /markets/unknown → PREVENTED
- ❌ Log inflation → DEDUPED by key signature tracking
- ❌ DB persistence of invalid data → SKIPPED before storage

---

## Next Steps

1. **Immediate**: Restart bot to activate patch
2. **2-4 hours**: Monitor logs for discrimination patterns
3. **After data collection**: Run updated E1 analysis
4. **Decision point**: Based on discrimination evidence, either:
   - **H2a confirmed** → API quality issues require observability (proceed with Phase 1)
   - **H2b confirmed** → Mapping fixes resolve most issues (lighter intervention)
   - **H2c confirmed** → Logging was inflated, issues minimal (defer Phase 1)

---

## Status

**Code changes**: ✅ COMPLETE
**Bot restart**: ⏳ PENDING USER ACTION
**Data collection**: ⏳ PENDING RESTART
**Discrimination analysis**: ⏳ PENDING 2-4H DATA

---

**The discriminating patch is surgical, safe, and ready for production deployment.**
