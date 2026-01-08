# Phase 2 — Falsification Conditions

**Date**: 2025-12-31
**Purpose**: Explicit stop conditions for Phase 2
**Status**: ✅ DEFINED

---

## What This Document Is

**Falsifiers** are conditions that, if observed, immediately terminate Phase 2.

These are NOT warnings. These are NOT concerns to investigate.

**If any falsifier occurs → Phase 2 STOPS immediately.**

---

## Falsifier Categories

### Category A: Parity Breaks (CRITICAL)

**Any of these → Phase 2 terminates, do NOT proceed to live trading**

| # | Falsifier | Detection | Response |
|---|-----------|-----------|----------|
| **A1** | Success/Failure Divergence | Same intent: Mock succeeds, Live fails (or vice versa) | STOP Phase 2 |
| **A2** | Error Semantic Divergence | Same error type produces different responses | STOP Phase 2 |
| **A3** | Accounting Divergence | Same trade produces different PnL calculations | STOP Phase 2 |
| **A4** | Non-Determinism | Same inputs produce different outputs across runs | STOP Phase 2 |
| **A5** | Interface Violation | Executor doesn't implement adapter contract correctly | STOP Phase 2 |

### Category B: Kill Criteria (from Phase 2 Charter)

**These were defined in Phase 2 Charter and remain active**

| # | Falsifier | Detection | Response |
|---|-----------|-----------|----------|
| **B1** | Parity Break (general) | Live execution deviates from mock beyond tolerance | STOP, revert to Phase 1 |
| **B2** | Risk Violation | Any guardrail breach (even at minimal size) | STOP, revert to Phase 1 |
| **B3** | Import Leakage | Real client imported outside adapter boundary | STOP, revert to Phase 1 |
| **B4** | Dependency Sprawl | Requires global downgrades/pins to proceed | STOP, revert to Phase 1 |
| **B5** | Non-Determinism | Same inputs produce different outcomes | STOP, revert to Phase 1 |
| **B6** | Operational Fragility | Flaky runs or intermittent failures | STOP, revert to Phase 1 |

### Category C: Tolerance Violations

**These indicate parity exists but is outside acceptable bounds**

| # | Falsifier | Threshold | Response |
|---|-----------|-----------|----------|
| **C1** | Price Tolerance Exceeded | Price differs by >10% AND >$0.05 | STOP Phase 2, reassess tolerance |
| **C2** | Size Tolerance Exceeded | Size differs by >$0.01 | STOP Phase 2, investigate |
| **C3** | Timestamp Tolerance Exceeded | Timestamp differs by >1 second | STOP Phase 2, investigate |

---

## Falsifier Details

### A1: Success/Failure Divergence

**Definition**: Same trade intent produces different success/failure outcomes through Mock vs Live executors.

**Example**:
```python
intent = TradeIntent(market_id="test", side="buy", size=Decimal("10"))

mock_result = mock_executor.execute_market_order(...)
# → success=True

live_result = live_executor.execute_market_order(...)
# → success=False

# FALSIFIER TRIGGERED
```

**Why critical**: Risk kernel would make different decisions depending on which executor is active. This breaks core invariant.

**Action**: STOP Phase 2 immediately, do NOT proceed to live trading.

---

### A2: Error Semantic Divergence

**Definition**: Same error condition produces semantically different error responses.

**Example**:
```python
# Trigger same error in both executors
mock_result = mock_executor.execute_market_order(market_id="invalid", ...)
# → error="market_not_found"

live_result = live_executor.execute_market_order(market_id="invalid", ...)
# → error="insufficient_balance"

# FALSIFIER TRIGGERED
```

**Why critical**: Alert system would send wrong notifications. Error handling logic diverges.

**Action**: STOP Phase 2 immediately.

---

### A3: Accounting Divergence

**Definition**: Same trade produces different position sizes or PnL calculations.

**Example**:
```python
intent = TradeIntent(market_id="test", side="buy", size=Decimal("100"))

# Process through Mock
tracker_mock.record_trade(trade_from_mock)
position_mock = tracker_mock.get_current_positions()[0]
# → size = $100

# Process through Live
tracker_live.record_trade(trade_from_live)
position_live = tracker_live.get_current_positions()[0]
# → size = $150

# FALSIFIER TRIGGERED
```

**Why critical**: Risk kernel limits would be calculated incorrectly. PnL tracking would be wrong.

**Action**: STOP Phase 2 immediately.

---

### A4: Non-Determinism

**Definition**: Running same executor with same inputs produces different outputs.

**Example**:
```python
intent = TradeIntent(market_id="test", side="buy", size=Decimal("10"))

# Run 1
result1 = executor.execute_market_order(...)
# → success=True

# Run 2 (same intent, same executor, same conditions)
result2 = executor.execute_market_order(...)
# → success=False

# FALSIFIER TRIGGERED
```

**Why critical**: Flaky behavior makes system unreliable. Cannot predict outcomes.

**Action**: STOP Phase 2 immediately.

---

### A5: Interface Violation

**Definition**: Executor doesn't implement ExecutorAdapter contract correctly.

**Example**:
```python
result = executor.execute_market_order(...)

# Missing required field
assert hasattr(result, "success")  # FAILS

# Wrong type
assert isinstance(result, ExecutionResult)  # FAILS

# Unexpected exception
result = executor.execute_market_order(...)  # Raises TypeError

# FALSIFIER TRIGGERED
```

**Why critical**: Substitutability broken. Core logic can't rely on adapter contract.

**Action**: STOP Phase 2 immediately.

---

### B3: Import Leakage (Already Verified ✅)

**Definition**: Real Polymarket client imported outside adapter boundary.

**Status**: ✅ VERIFIED SAFE by guard test

**Test**: `test_live_executor_not_loaded_without_feature_flag` PASSING

**Current state**: No leakage detected. Lazy import working correctly.

---

### C1: Price Tolerance Exceeded

**Definition**: Price difference between Mock and Live exceeds acceptable tolerance.

**Threshold**: Price differs by >10% AND >$0.05

**Example**:
```python
mock_result.price = Decimal("0.50")
live_result.price = Decimal("0.75")

diff = abs(0.75 - 0.50) = 0.25
diff_pct = (0.25 / 0.50) * 100 = 50%

# Exceeds tolerance (>10% AND >$0.05)
# FALSIFIER TRIGGERED
```

**Why concerning**: Large price differences suggest mock doesn't represent reality. Risk kernel uses price for some calculations.

**Action**: STOP Phase 2, reassess whether tolerance should be adjusted OR mock is fundamentally wrong.

---

## Test-to-Falsifier Mapping

**Each parity test maps to a falsifier:**

| Test | Falsifier | Status |
|------|-----------|--------|
| `test_mock_executor_interface_compliance` | A5 (Interface Violation) | ✅ PASSED |
| `test_live_executor_interface_compliance` | A5 (Interface Violation) | ⏸️ SKIPPED |
| `test_mock_executor_determinism` | A4 (Non-Determinism) | ✅ PASSED |
| `test_live_executor_determinism` | A4 (Non-Determinism) | ⏸️ SKIPPED |
| `test_mock_executor_error_semantics` | A2 (Error Divergence) | ✅ PASSED |
| `test_live_executor_error_semantics` | A2 (Error Divergence) | ⏸️ SKIPPED |
| `test_parity_price_tolerance` | C1 (Price Tolerance) | ⏸️ SKIPPED |
| `test_parity_size_accuracy` | C2 (Size Tolerance) | ⏸️ SKIPPED |
| `test_parity_invariant_success_failure_equivalence` | A1 (Success/Failure Divergence) | ⏸️ SKIPPED |
| `test_parity_invariant_risk_kernel_independence` | A3 (Accounting Divergence) | ✅ PASSED |

**Current state**: All MockExecutor tests passing, LiveExecutor tests skipped (web3 blocker).

---

## Decision Tree

```
Parity Test Run
    ├─ Category A Falsifier Detected
    │   └─ STOP Phase 2 immediately
    │       └─ Do NOT proceed to live trading
    │           └─ Revert to Phase 1
    │               └─ Reassess execution strategy
    │
    ├─ Category B Falsifier Detected
    │   └─ STOP Phase 2 immediately
    │       └─ Revert to Phase 1
    │           └─ Document failure mode
    │
    ├─ Category C Falsifier Detected
    │   └─ STOP Phase 2
    │       └─ Investigate tolerance
    │           └─ Option A: Adjust tolerance (justify)
    │           └─ Option B: Accept as unfixable, stop Phase 2
    │
    └─ No Falsifiers Detected
        └─ Phase 2 can continue (with approval)
            └─ Proceed to next decision point
```

---

## Falsifier Confidence

**How confident are we these are the right falsifiers?**

### High Confidence (Will definitely stop Phase 2)

- A1: Success/Failure Divergence ✓
- A3: Accounting Divergence ✓
- A4: Non-Determinism ✓
- A5: Interface Violation ✓
- B2: Risk Violation ✓

### Medium Confidence (Probably should stop Phase 2)

- A2: Error Semantic Divergence (some errors might be tolerable)
- C1: Price Tolerance (threshold might need adjustment)
- C2: Size Tolerance (threshold might need adjustment)

### Unknown (Need real data)

- C3: Timestamp Tolerance (might not matter for bot operation)
- B4: Dependency Sprawl (subjective judgment)

---

## What Happens When Falsifier Triggers

### Immediate Actions

1. **STOP all Phase 2 work**
2. **Log the falsifier** (which one, what data triggered it)
3. **Preserve state** (don't delete evidence)
4. **Document in post-mortem**

### Analysis

1. **Root cause**: Why did falsifier trigger?
2. **False positive?**: Is falsifier definition wrong?
3. **Fixable?**: Can we address root cause without scope creep?

### Decision

1. **Fix and retry**: If fixable within Phase 2 scope
2. **Adjust falsifier**: If definition was too strict (requires justification)
3. **Terminate Phase 2**: If fundamental incompatibility detected

---

## Current Falsifier Status

| Category | Count | Triggered | Status |
|----------|-------|-----------|--------|
| **Category A** | 5 | 0 | 🟢 SAFE |
| **Category B** | 6 | 0 | 🟢 SAFE |
| **Category C** | 3 | 0 | 🟢 SAFE |

**No falsifiers triggered as of 2025-12-31.**

**MockExecutor**: All tests passing ✓
**LiveExecutor**: Not yet tested (web3 blocker)

---

## Next Steps (After LiveExecutor Implemented)

When LiveExecutor is implemented and tests un-skipped:

1. Run all parity tests
2. Check for falsifier triggers
3. If any Category A or B → STOP immediately
4. If any Category C → Investigate, then decide
5. If none → Document results, proceed to decision point

**Do NOT proceed to Step 4 (live trade) unless all parity tests pass.**

---

**Falsifiers**: ✅ DEFINED
**Test Mapping**: ✅ COMPLETE
**Decision Tree**: ✅ DOCUMENTED
**Status**: 🟢 No falsifiers triggered (MockExecutor tests passing)
