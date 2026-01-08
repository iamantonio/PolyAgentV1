# Phase 2 Charter — Execution Isolation & Falsification

**Authorized By**: Tony
**Date**: 2025-12-31
**Status**: 🟡 IN PROGRESS
**Capital Status**: 🔴 NOT DEPLOYED

---

## What Phase 2 IS

- Proving real Polymarket execution can be isolated behind a stable adapter
- Demonstrating mock ↔ live parity
- Executing **one** smallest-possible real trade under strict supervision
- Measuring latency, slippage, and failure behavior

## What Phase 2 IS NOT

- ❌ Strategy changes
- ❌ LunarCrush integration
- ❌ Multi-trader expansion
- ❌ Optimization
- ❌ Scaling
- ❌ Going live
- ❌ Automated trading

**If work drifts beyond scope → HARD STOP**

---

## Hypotheses (Falsifiable)

| ID | Hypothesis | Status | Falsification Criteria |
|----|------------|--------|------------------------|
| **H1** | Real execution can be isolated without contaminating core logic | 🟡 Testing | Import leakage, side effects |
| **H2** | Live execution behavior matches mock assumptions within tolerance | 🟡 Testing | Parity break, semantic divergence |
| **H3** | Latency/slippage do not violate risk kernel guarantees at minimal size | 🟡 Testing | Risk violation, timing issues |
| **H4** | Upstream dependencies can be stabilized without repo-wide pins | 🟡 Testing | Dependency sprawl, global downgrades |

---

## Kill Criteria (Non-Negotiable)

**IMMEDIATE HARD STOP** if any occur:

| # | Criterion | Detection | Response |
|---|-----------|-----------|----------|
| 1 | **Parity break** | Live execution deviates from mock behavior beyond tolerance | Stop, revert to Phase 1, reassess |
| 2 | **Risk violation** | Any guardrail breach (even at minimal size) | Stop, revert to Phase 1, reassess |
| 3 | **Import leakage** | Real client imported outside adapter boundary | Stop, revert to Phase 1, reassess |
| 4 | **Dependency sprawl** | Requires global downgrades/pins to proceed | Stop, revert to Phase 1, reassess |
| 5 | **Non-determinism** | Same inputs produce different outcomes | Stop, revert to Phase 1, reassess |
| 6 | **Operational fragility** | Flaky runs or intermittent failures | Stop, revert to Phase 1, reassess |

**No retries by default. Revert and reassess.**

---

## Acceptance Criteria (Must ALL Pass)

### 1. Adapter Isolation ✅

- [ ] Real client only loads behind feature flag
- [ ] No side-effect imports at module load
- [ ] Guard test confirms isolation

### 2. Mock ↔ Live Parity ✅

- [ ] Same intent → same decision path → same accounting semantics
- [ ] Differences documented and justified
- [ ] Parity tests pass

### 3. Minimal Live Trade ✅

- [ ] One trade only
- [ ] Smallest allowable size
- [ ] Full telemetry captured

### 4. Post-Trade Audit ✅

- [ ] Every step explained: intent → validation → execution → fill → PnL
- [ ] No unexplained deltas
- [ ] Written post-mortem produced

---

## Work Plan (Ordered)

### Step 1 — Execution Adapter (ONLY)

**Goal**: Create single adapter interface with two implementations

**Deliverables**:
- `ExecutorAdapter` abstract interface
- `MockExecutor` implementation (wraps existing mock)
- `LiveExecutor` implementation (wraps Polymarket client)
- Feature flag: `USE_REAL_EXECUTOR=false` (default)

**Acceptance**:
- CopyTrader uses adapter, not direct client
- Adapter switch via flag only
- No breaking changes to Phase 1 code

### Step 2 — Import Hygiene

**Goal**: Lazy-load live client inside adapter only

**Deliverables**:
- Live client loaded only when `USE_REAL_EXECUTOR=true`
- Guard test: real client NOT imported by default
- TYPE_CHECKING pattern for imports

**Acceptance**:
- All Phase 1 tests still pass
- Integration guard test passes
- No module-level side effects

### Step 3 — Parity Tests

**Goal**: Assert mock and live (dry-run) equivalence

**Deliverables**:
- Parity test suite comparing mock vs live
- Tolerance definitions for acceptable differences
- Documentation of semantic equivalence

**Acceptance**:
- Same intent produces same validation decisions
- Same risk kernel behavior
- Differences <= tolerance or justified

### Step 4 — One Live Trade

**Goal**: Execute single minimal trade, capture telemetry

**Deliverables**:
- Pre-flight checklist (balances, allowlist, limits)
- Single trade execution (smallest size)
- Full execution log (timestamps, prices, fills)

**Acceptance**:
- Trade executes without crash
- Guardrails enforced correctly
- Telemetry complete

**FREEZE IMMEDIATELY AFTER**

### Step 5 — Audit & Decision

**Goal**: Produce written post-mortem and decide

**Deliverables**:
- Post-mortem document analyzing execution
- Comparison: expected vs actual behavior
- Decision: proceed / pause / stop

**Acceptance**:
- Every step explained
- No unexplained deltas
- Clear go/no-go decision

---

## Capital Policy (Unchanged)

- **Capital deployed**: Minimal, one-time only
- **Trade size**: Smallest allowable on Polymarket
- **Automation**: Disabled except for single supervised execution
- **Scaling**: Explicitly disallowed in Phase 2

---

## Confidence Estimate

**Probability Phase 2 completes cleanly**: ~50%

**Biggest Unknowns**:
1. web3 dependency behavior in production
2. Latency under real network conditions
3. Subtle fill semantics differences between mock and CLOB
4. Order rejection reasons not covered by mock

---

## Team Assignments

| Role | Responsibility |
|------|----------------|
| **Barry (Dev)** | Implement execution adapter and guards |
| **Murat (Test Architect)** | Define parity assertions and stop conditions |
| **Bob (Scrum Master)** | Phase 2 micro-sprint management |
| **Paige (Tech Writer)** | Update docs with Phase 2 scope and kill criteria |
| **BMad Master** | Enforce scope, no exceptions |

---

## Progress Tracking

| Step | Status | Started | Completed |
|------|--------|---------|-----------|
| 1. Execution Adapter | 🟡 In Progress | 2025-12-31 | — |
| 2. Import Hygiene | 🔴 Not Started | — | — |
| 3. Parity Tests | 🔴 Not Started | — | — |
| 4. One Live Trade | 🔴 Not Started | — | — |
| 5. Audit & Decision | 🔴 Not Started | — | — |

---

## Scope Enforcement

**Any work beyond the 5 steps MUST be explicitly authorized.**

**Examples of BLOCKED work** (non-exhaustive):
- Refactoring Phase 1 code
- Adding new risk controls
- Optimizing execution logic
- Adding multi-trader support
- Integrating LunarCrush
- Building dashboards
- Creating monitoring tools
- Improving position sizing
- Adding stop-loss per position

**If in doubt → STOP and ask.**

---

## Decision Points

### After Step 1
- ✅ Continue if adapter isolation clean
- 🔴 Stop if import leakage or contamination

### After Step 2
- ✅ Continue if guard tests pass
- 🔴 Stop if imports leak to main codebase

### After Step 3
- ✅ Continue if parity holds within tolerance
- 🔴 Stop if semantic divergence detected

### After Step 4
- ✅ Continue to audit if trade executes cleanly
- 🔴 Stop immediately if any kill criterion triggered

### After Step 5
- ✅ Proceed to limited automation (if approved)
- ⏸️ Pause for further analysis
- 🔴 Stop and revert to Phase 1

---

## Why Proceeding

**Because**:
- Phase 1 proved correctness
- Risk is tightly bounded
- We have explicit falsifiers
- Kill criteria are clear
- Work plan is narrow

**Not because**:
- ~~We're confident it will work~~
- ~~We need to ship~~
- ~~Pressure to go live~~

---

**Phase 2 Status**: 🟡 IN PROGRESS
**Current Step**: 1 of 5
**Capital**: 🔴 NOT DEPLOYED
**Automation**: 🔴 DISABLED
