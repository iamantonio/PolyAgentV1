# Phase 2 — Mock ↔ Live Parity Criteria

**Date**: 2025-12-31
**Purpose**: Define semantic equivalence between MockExecutor and LiveExecutor
**Status**: 🟡 Criteria Defined, Tests Scaffolded

---

## What "Parity" Means

**Parity** = Same trade intent produces same *semantic outcome* through both executors, within defined tolerances.

### Core Principle

**The risk kernel, position tracker, and alert system must make identical decisions regardless of which executor is used.**

If they don't, we have a **parity break** → Phase 2 terminates.

---

## Parity Categories

### Category 1: MUST Match (Zero Tolerance)

These must be **identical** between Mock and Live executors:

| Property | Requirement | Rationale |
|----------|-------------|-----------|
| **Success/Failure Decision** | Same intent → same success boolean | Risk kernel depends on this |
| **Error Semantics** | Same error type → same error handling | Alert system depends on this |
| **Accounting Semantics** | Same size → same capital impact | Position tracker depends on this |
| **Determinism** | Same inputs → same outputs (every time) | No flaky behavior allowed |
| **Interface Contract** | Both implement ExecutorAdapter correctly | Substitutability requirement |

**Falsifiers**:
- Mock succeeds, Live fails (or vice versa) for same intent
- Different error types for same failure mode
- Different PnL calculation for same fill
- Non-deterministic behavior (flakiness)
- Interface violation

### Category 2: SHOULD Match (With Tolerance)

These should be similar, but exact equality not required:

| Property | Tolerance | Rationale |
|----------|-----------|-----------|
| **Price** | ±0.05 or ±10% (whichever is larger) | Market volatility is real |
| **Size** | Exact match expected, but rounding to 2 decimals acceptable | USDC has 6 decimals, we use dollars |
| **Timestamp Precision** | ±1 second | Network latency varies |

**Falsifiers**:
- Price differs by >10% AND >$0.05
- Size differs by >$0.01
- Timestamp differs by >1 second (if both provided)

### Category 3: MAY Differ (Documented)

These are expected to differ and do NOT indicate parity break:

| Property | Mock Behavior | Live Behavior | Rationale |
|----------|---------------|---------------|-----------|
| **Execution ID** | Sequential mock ID | Transaction hash | Implementation detail |
| **Timestamp** | `None` | Unix timestamp | Mock doesn't track time |
| **Price** | Fixed `0.50` | Real CLOB price | Mock uses placeholder |
| **Network Metadata** | Not present | Gas, block number, etc. | Live execution only |

**NOT falsifiers** - these differences are expected and acceptable.

---

## Parity Invariants

**These properties MUST hold for both executors:**

### Invariant 1: Risk Kernel Independence

```
∀ intent, ∀ executor ∈ {Mock, Live}:
  risk_kernel.approve_trade(intent) → same decision
```

**What this means**: Risk kernel decisions must NOT depend on executor implementation details.

**Test**: Run same intent through both executors, verify risk kernel makes same decision.

### Invariant 2: Position Tracking Independence

```
∀ trade, ∀ executor ∈ {Mock, Live}:
  tracker.record_trade(trade) → same position state
```

**What this means**: Position tracker must calculate same PnL regardless of executor.

**Test**: Record trades from both executors, verify position state matches.

### Invariant 3: Error Handling Equivalence

```
∀ failure_mode, ∀ executor ∈ {Mock, Live}:
  executor.execute_market_order(...) → semantically equivalent error
```

**What this means**: Same failure modes must produce same error responses.

**Test**: Trigger same failures in both executors, verify error semantics match.

### Invariant 4: Interface Contract Compliance

```
∀ executor ∈ {Mock, Live}:
  executor implements ExecutorAdapter correctly
```

**What this means**: Both executors must honor the adapter contract.

**Test**: Verify both implement all required methods with correct signatures.

---

## Acceptable Differences (Explicit)

### Price Differences

**Why acceptable**:
- Mock uses fixed price (`0.50`)
- Live uses real CLOB price (market-determined)

**Tolerance**: ±0.05 or ±10%

**Why this tolerance**:
- Polymarket spreads typically <10%
- Market volatility can shift price quickly
- Risk kernel uses size, not price, for limits

**Falsifier**: Price differs by >10% AND >$0.05

### Timestamp Differences

**Why acceptable**:
- Mock doesn't track execution time
- Live records blockchain timestamp

**Tolerance**: ±1 second (if both provided)

**Why this tolerance**:
- Network latency is sub-second
- Block time is ~2 seconds
- 1 second is generous buffer

**Falsifier**: Timestamp differs by >1 second

### Execution ID Format

**Why acceptable**:
- Mock uses sequential IDs (`mock_1`, `mock_2`, ...)
- Live uses transaction hashes (`0x...`)

**No tolerance needed**: These are opaque identifiers

**Falsifier**: None (format difference expected)

---

## Disqualifying Differences (Falsifiers)

**Any of these → immediate Phase 2 termination:**

### 1. Success/Failure Divergence

```
MockExecutor.execute_market_order(...) → success=True
LiveExecutor.execute_market_order(...) → success=False

OR vice versa
```

**This means**: Same intent produces different outcomes.

**Impact**: Risk kernel would make different decisions.

**Action**: STOP Phase 2, do not proceed to live trading.

### 2. Error Semantic Divergence

```
MockExecutor → ExecutionResult(error="insufficient_balance")
LiveExecutor → ExecutionResult(error="invalid_market")

For same failure condition
```

**This means**: Error handling logic diverges.

**Impact**: Alert system would send different notifications.

**Action**: STOP Phase 2, do not proceed to live trading.

### 3. Accounting Semantic Divergence

```
Same trade intent through both executors →
  MockExecutor: position size = $100
  LiveExecutor: position size = $150
```

**This means**: Position tracking produces different PnL.

**Impact**: Risk kernel limits would be miscalculated.

**Action**: STOP Phase 2, do not proceed to live trading.

### 4. Non-Determinism

```
Same intent, same executor, different runs →
  Run 1: success=True
  Run 2: success=False
```

**This means**: Flaky behavior exists.

**Impact**: Unreliable execution, unpredictable outcomes.

**Action**: STOP Phase 2, do not proceed to live trading.

### 5. Interface Violation

```
LiveExecutor.execute_market_order(...)
  → Returns wrong type
  → Missing required fields
  → Raises unexpected exception
```

**This means**: Adapter contract not honored.

**Impact**: Substitutability broken, core logic fails.

**Action**: STOP Phase 2, do not proceed to live trading.

---

## Test Strategy

### Phase 2 Step 3 Tests (THIS STEP)

**Goal**: Verify parity criteria are testable and MockExecutor passes.

**Approach**:
1. Define parity test structure
2. Test MockExecutor against criteria
3. Document what LiveExecutor must do to pass
4. Do NOT implement LiveExecutor execution (web3 blocker)

**Tests to create**:
- `test_mock_executor_interface_compliance`
- `test_mock_executor_determinism`
- `test_mock_executor_error_semantics`
- `test_parity_price_tolerance` (structure only)
- `test_parity_success_failure` (structure only)
- `test_parity_accounting` (structure only)

**Tests marked SKIP** if LiveExecutor not implemented.

### Future Tests (Phase 2.x or Phase 3)

**When LiveExecutor is implemented**:
- Un-skip parity tests
- Run same intent through both executors
- Assert invariants hold
- Measure tolerances

---

## Confidence Levels

### High Confidence (>80%)

- MockExecutor meets all criteria ✓
- Adapter interface is sound ✓
- Test structure is correct ✓

### Medium Confidence (50-80%)

- LiveExecutor WILL meet criteria (unknown until implemented)
- Tolerance thresholds are appropriate (need real data)
- No hidden semantic divergences (can't prove negative)

### Low Confidence (<50%)

- Real CLOB behavior matches assumptions (haven't tested)
- Price volatility stays within tolerance (market-dependent)
- No exotic failure modes missed (unknown unknowns)

---

## Decision Tree

```
Parity Tests Run
    ├─ ALL PASS
    │   ├─ Within tolerance → Phase 2 can continue
    │   └─ Edge of tolerance → Reassess tolerance, then decide
    │
    └─ ANY FAIL
        ├─ Category 1 (MUST match) → STOP Phase 2
        ├─ Category 2 (SHOULD match) → Investigate, may stop
        └─ Category 3 (MAY differ) → Not a failure
```

---

## Acceptance Criteria for Step 3

**Step 3 is complete when**:

1. ✅ This document exists and is approved
2. ✅ Parity test scaffolding created
3. ✅ MockExecutor passes all applicable tests
4. ✅ Falsifiers are explicitly documented
5. ✅ LiveExecutor requirements are documented

**Step 3 does NOT require**:
- ❌ LiveExecutor implementation
- ❌ web3 dependency fix
- ❌ Real execution tests
- ❌ Live trade execution

---

## Falsification Conditions (Summary)

**Phase 2 STOPS if ANY occur**:

1. Success/failure divergence for same intent
2. Error semantic divergence for same failure
3. Accounting semantic divergence for same trade
4. Non-deterministic behavior (flakiness)
5. Interface contract violation
6. Price tolerance exceeded (>10% AND >$0.05)
7. Timestamp tolerance exceeded (>1 second)

**Phase 2 continues if**:
- All Category 1 criteria match exactly
- All Category 2 criteria within tolerance
- All Category 3 differences documented and expected

---

**Parity Criteria**: ✅ DEFINED
**Next**: Implement test scaffolding
**Awaiting**: Test results before Phase 2 reassessment
