# Win Rate Calculation Fix Applied

**Date**: January 9, 2026
**Status**: ✅ **FIXED** - Win rate now reflects profitability, not prediction accuracy
**Files Modified**: `agents/learning/trade_history.py`

---

## Summary

Fixed the win rate calculation to measure **profitability** instead of **prediction accuracy**.

**Before**:
- Win rate = `was_correct` (did outcome match prediction?)
- Result: 57.41% win rate (misleading)

**After**:
- Win rate = `profit_loss_usdc > 0` (did trade make money?)
- Result: 51.85% win rate (accurate)

---

## Changes Made

### 1. Updated `get_performance_summary()` method

**File**: `agents/learning/trade_history.py` (lines 393-434)

**Added SQL**:
```sql
SUM(CASE WHEN profit_loss_usdc > 0 THEN 1 ELSE 0 END) as profitable_trades
```

**Changed return value**:
```python
# BEFORE:
return {
    "win_rate": correct / resolved if resolved > 0 else None,
    ...
}

# AFTER:
return {
    "win_rate": profitable / resolved if resolved > 0 else None,
    "prediction_accuracy": correct / resolved if resolved > 0 else None,
    ...
}
```

**Impact**: Win rate now shows 51.85% instead of 57.41%

### 2. Updated `get_edge_by_market_type()` method

**File**: `agents/learning/trade_history.py` (lines 474-507)

**Added SQL**:
```sql
SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct_predictions,
SUM(CASE WHEN profit_loss_usdc > 0 THEN 1 ELSE 0 END) as profitable_trades
```

**Changed return value**:
```python
# BEFORE:
results[market_type] = {
    "win_rate": wins / total if total > 0 else 0,
    ...
}

# AFTER:
results[market_type] = {
    "win_rate": profitable / total if total > 0 else 0,
    "prediction_accuracy": correct / total if total > 0 else 0,
    ...
}
```

**Impact**: Win rate by market type now reflects profitability

---

## Verification Results

**Performance Summary** (54 resolved trades):
```
Win rate (P&L-based): 51.85% ✅
Prediction accuracy: 57.41%
Discrepancy: 5.56 percentage points
Total P&L: $4.18
```

**Edge by Market Type**:
```
Sports:
  - Win rate: 56.52% (P&L-based)
  - Prediction accuracy: 60.87%
  - Avg P&L/trade: $0.26
  - Has edge: YES ✅

Crypto:
  - Win rate: 25.00%
  - Prediction accuracy: 25.00%
  - Avg P&L/trade: -$0.98
  - Has edge: NO ❌

Other:
  - Win rate: 33.33%
  - Prediction accuracy: 33.33%
  - Avg P&L/trade: -$0.67
  - Has edge: NO ❌
```

---

## Key Insights

### 1. Sports Markets Show Edge
- **Win rate**: 56.52% (profitable majority)
- **Avg P&L**: +$0.26 per trade
- **Recommendation**: Continue focusing on sports markets

### 2. Crypto/Other Markets Losing Money
- **Crypto**: 25% win rate, -$0.98 avg P&L
- **Other**: 33.33% win rate, -$0.67 avg P&L
- **Recommendation**: Pause crypto/other until edge is found

### 3. Discrepancy Explained
- **5.56% of trades** were marked "correct" but lost money
- **Root cause**: High entry prices + fees exceeded profit
- **Example**: Bought YES at $0.99, outcome YES, but fees -$0.03 → net loss

---

## Benefits of Fix

1. **Accurate Performance Tracking**
   - Win rate reflects actual profitability
   - Can properly evaluate strategy effectiveness

2. **Better Decision Making**
   - Auto-scaling now based on P&L win rate, not prediction accuracy
   - Risk management uses correct metrics

3. **Separate Metrics**
   - `win_rate`: Profitability (investors care about this)
   - `prediction_accuracy`: Outcome matching (research metric)

4. **Improved Transparency**
   - Both metrics available for analysis
   - Can identify when "correct" predictions lose money

---

## Recommendations

### 1. Review Auto-Scaling Logic

**Current threshold** in `learning_autonomous_trader.py`:
```python
SCALING_WIN_RATE_THRESHOLD = 0.58  # 58% win rate
```

**Problem**: With corrected win rate at 51.85%, auto-scaling won't trigger

**Options**:
- **A**: Lower threshold to 52% (current performance level)
- **B**: Keep threshold at 58%, require improvement before scaling
- **C**: Use prediction_accuracy for confidence, win_rate for profitability

**Recommendation**: Option B - maintain high bar for scaling

### 2. Monitor Prediction Accuracy vs Win Rate Gap

**Healthy gap**: 0-2 percentage points
**Current gap**: 5.56 percentage points ⚠️

**If gap widens >10%**: Indicates systematic issue with:
- Entry price selection (buying too high)
- Fee structure (eating into profits)
- Exit timing (leaving money on table)

### 3. Fix Entry Price Logic

**Issue**: Bot buying at prices where even correct predictions lose money

**Investigation needed**:
1. Check slippage between decision and execution
2. Verify fee calculation is included in edge estimation
3. Review minimum edge threshold (should be > fees)

---

## Next Steps

1. ✅ **Fix applied and verified** - Win rate now uses P&L
2. ⏸️ **Wait for clean data** - Collect 2-4 hours with discriminating patch
3. 🔍 **Monitor gap** - Track prediction_accuracy vs win_rate divergence
4. 📊 **Run discrimination analysis** - After data collection complete
5. 🎯 **Phase 1 decision** - Based on H2a vs H2b vs H2c results

---

**Status**: Win rate calculation fix COMPLETE and verified working correctly.
