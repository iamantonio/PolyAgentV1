# CopyTrader V1 — Phase 0 + Phase 1

**Status**: ✅ Validated – Execution Disabled
**Last Updated**: 2025-12-31
**Signed Off By**: Tony

---

## Overview

CopyTrader V1 is a Polymarket copy-trading bot with **hard risk controls** and **fail-closed architecture**.

### What V1 Does

- ✅ Validates trade intents against staleness threshold (<10s)
- ✅ Enforces politics-only market allowlist (dynamic from Polymarket)
- ✅ Enforces position limits (max 3 concurrent positions)
- ✅ Enforces per-trade capital cap (3% of capital)
- ✅ Enforces daily stop loss (-5%)
- ✅ Enforces hard kill switch (-20% total loss)
- ✅ Detects anomalous single-trade losses (>5% triggers kill)
- ✅ Records all intents, trades, and risk events to SQLite
- ✅ Sends Telegram alerts for critical events
- ✅ Calculates PnL (daily and total)
- ✅ Tracks open positions

### What V1 Does NOT Do

- ❌ **Live execution** (Phase 2 prerequisite)
- ❌ Multi-trader copying
- ❌ Custom market strategies
- ❌ LunarCrush integration
- ❌ Advanced position sizing
- ❌ Partial position closes
- ❌ Stop-loss per position
- ❌ Take-profit targets
- ❌ Market-making or limit orders

---

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────┐
│                  CopyTrader Executor                 │
│  (orchestrates: validation → risk → exec → alert)   │
└─────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐    ┌─────▼─────┐   ┌─────▼─────┐
   │ Intent  │    │   Risk    │   │ Position  │
   │Validator│    │  Kernel   │   │  Tracker  │
   └────┬────┘    └─────┬─────┘   └─────┬─────┘
        │                │                │
        └────────────────┼────────────────┘
                         │
                   ┌─────▼─────┐
                   │  Storage  │
                   │ (SQLite)  │
                   └───────────┘
```

### Intent Validation Pipeline

```
TradeIntent → Staleness Check → Allowlist Check → Position Limit → Risk Kernel → Execute
                     ↓                ↓                  ↓              ↓
                  REJECT          REJECT            REJECT         REJECT/APPROVE
```

### Risk Kernel Decision Tree

```
Is bot killed? ──YES──→ REJECT (killed)
     │
     NO
     ↓
Total PnL ≤ -20%? ──YES──→ REJECT (hard_kill) + KILL BOT
     │
     NO
     ↓
Daily PnL ≤ -5%? ──YES──→ REJECT (daily_stop)
     │
     NO
     ↓
Open positions ≥ 3? ──YES──→ REJECT (position_limit)
     │
     NO
     ↓
Trade size > 3% cap? ──YES──→ REJECT (per_trade_cap)
     │
     NO
     ↓
APPROVE ──→ Execute (dry-run or live)
```

---

## Guardrails (V1 Hard Limits)

| Limit | Value | Behavior |
|-------|-------|----------|
| Starting Capital | $1,000 | Fixed at initialization |
| Daily Stop Loss | -5% | Halts trading for remainder of day |
| Hard Kill | -20% total loss | Permanently disables bot |
| Per-Trade Cap | 3% of capital | Rejects oversized trades |
| Max Positions | 3 | Rejects new trades when at limit |
| Anomalous Loss | >5% on single trade | Triggers hard kill |
| Intent Staleness | >10 seconds | Rejects stale intents |
| Market Allowlist | Politics only | Rejects non-politics markets |

### Kill Conditions

The bot will **permanently stop trading** if:

1. **Hard Kill Triggered**: Total PnL ≤ -20%
2. **Anomalous Loss**: Single trade loses >5% of capital
3. **Manual Kill**: Operator calls `risk_kernel.kill()`

Once killed, the bot **cannot be restarted** without manual database reset.

---

## Fail-Closed Behavior

If any critical component fails, the bot **rejects all trades**:

- Empty allowlist → All intents rejected (`allowlist_empty`)
- Database unavailable → Raises exception, no trades
- Risk kernel returns non-approved → Trade rejected

**Philosophy**: No data = no trades. No ambiguity.

---

## Database Schema

**File**: `copytrader_v1.db` (SQLite)

### Tables

- `positions` — Open positions (market_id, side, size, entry_price, etc.)
- `trade_history` — Executed trades with execution status
- `intent_log` — All intents (accepted + rejected) with reasons
- `risk_events` — Daily stops, hard kills, anomalous losses
- `capital_state` — PnL snapshots
- `metadata` — Schema version tracking

### Schema Version

**Current**: v1
**Migration**: Not supported in V1 (breaking changes require new DB)

---

## Alerts

### Telegram Configuration

Set environment variables:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Alert Types

1. **Trade Executed** — Successful trade with price, size, market
2. **Trade Rejected** — Failed validation with reason
3. **Daily Stop** — -5% daily loss threshold hit
4. **Hard Kill** — -20% total loss OR >5% single trade loss

### Alert Failure Handling

Alert delivery failures are **logged but do not block operations**.

---

## Setup Instructions

### 1. Install Dependencies

```bash
# Create virtual environment
virtualenv --python=python3.9 .venv
source .venv/bin/activate

# Install CopyTrader test dependencies (minimal)
pip install -r requirements-copytrader-test.txt
```

### 2. Set Environment Variables

Create `.env` file:

```bash
# Required for live execution (Phase 2)
POLYGON_WALLET_PRIVATE_KEY=your_private_key
OPENAI_API_KEY=your_openai_key

# Optional: Telegram alerts
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Run Tests

```bash
# Verify all 21 tests pass
PYTHONPATH=. python -m pytest tests/test_copytrader.py -v
```

Expected output:
```
21 passed, 2 warnings in 0.42s
```

### 4. Run Dry-Run Validation

```bash
# Phase 1 validation script (uses mocked execution)
.venv/bin/python scripts/python/copytrader_dryrun.py
```

Expected behavior:
- ✓ Clean startup
- ✓ Allowlist refresh attempt (may fail if API unavailable)
- ✓ Fail-closed message if allowlist empty
- ✓ Intent rejection for correct reason
- ✓ No crashes

---

## Emergency Procedures

### 🚨 If Bot Loses >5% on Single Trade

**Automatic Response**: Bot triggers hard kill and stops all trading.

**Manual Steps**:
1. Check `risk_events` table for kill reason
2. Review `trade_history` for failed trade
3. Investigate execution logic (Phase 2 concern)
4. **Do NOT restart bot** until root cause identified

### 🚨 If Daily Stop Triggered (-5%)

**Automatic Response**: Bot rejects all new trades for remainder of day.

**Manual Steps**:
1. Check `capital_state` table for PnL breakdown
2. Review `intent_log` for rejection patterns
3. Monitor until daily reset (next UTC day)
4. Bot will auto-resume if total PnL > -20%

### 🚨 If Hard Kill Triggered (-20%)

**Automatic Response**: Bot permanently disabled.

**Manual Steps**:
1. Check `risk_events` table for kill event
2. Review full `trade_history` for loss breakdown
3. **Do NOT reset database** — preserve evidence
4. Conduct post-mortem before any restart

### 🚨 Manual Kill Switch

```python
from agents.copytrader.risk_kernel import RiskKernel
from agents.copytrader.storage import CopyTraderDB
from decimal import Decimal

db = CopyTraderDB("./copytrader_v1.db")
risk_kernel = RiskKernel(
    starting_capital=Decimal("1000.0"),
    daily_stop_pct=Decimal("-5.0"),
    hard_kill_pct=Decimal("-20.0"),
    per_trade_cap_pct=Decimal("3.0"),
    max_positions=3,
    anomalous_loss_pct=Decimal("-5.0"),
)
risk_kernel.kill()
print("Bot killed manually")
```

---

## Testing

### Test Coverage

**21/21 tests passing** across:

- **Intent Validation** (5 tests)
  - Stale intent rejection
  - Non-allowlist market rejection
  - Position limit enforcement
  - Valid intent acceptance
  - Empty allowlist fail-closed

- **Risk Kernel** (7 tests)
  - Daily stop at -5%
  - Hard kill at -20%
  - Per-trade cap at 3%
  - Position limit at 3
  - Anomalous loss detection (>5%)
  - Kill state persistence
  - Manual kill switch

- **Position Tracking** (4 tests)
  - Trade recording
  - Intent rejection logging
  - PnL calculation accuracy
  - Database corruption prevention

- **Execution Flow** (3 tests)
  - End-to-end success path
  - End-to-end rejection path
  - Execution failure handling

- **Alerts** (1 test)
  - All alert types delivery

- **Integration Guard** (1 test)
  - Real Polymarket client not imported

### Running Tests

```bash
# Full suite
PYTHONPATH=. python -m pytest tests/test_copytrader.py -v

# Specific test
PYTHONPATH=. python -m pytest tests/test_copytrader.py::test_daily_stop_at_minus_5pct -v
```

---

## Phase 2 Prerequisites

**Before enabling live execution**, the following MUST be resolved:

### 1. Web3 Dependency Issue

**Current blocker**: `cannot import name 'geth_poa_middleware' from 'web3.middleware'`

**Options**:
- Fix upstream `agents/polymarket/polymarket.py` web3 imports
- Pin compatible web3 version
- Abstract execution behind stable adapter interface

### 2. Execution Client Validation

**Required**:
- Single real execution with smallest possible size
- Verify no drift between mock and live behavior
- Confirm CLOB integration works end-to-end

### 3. Intent Ingestion Source

**Required**:
- Define how intents are received (API, websocket, polling, etc.)
- Implement ingestion layer
- Add intent source validation

**NOT required in Phase 2**:
- Multi-trader logic
- Strategy changes
- Additional risk controls

---

## Known Limitations

### Phase 1 Constraints

- **Execution**: Mocked only (no live trading)
- **Intent Source**: Manual injection only
- **Markets**: Politics-only (hardcoded filter)
- **Trader**: Single trader ID (no multi-copy)
- **Position Sizing**: Fixed dollar amount (no dynamic sizing)

### Expected Warnings

```
PydanticDeprecatedSince20: `@validator` is deprecated, use `@field_validator`
```

**Impact**: None (cosmetic deprecation warning)
**Fix**: Deferred to post-Phase 2 cleanup

---

## Files Reference

### Core Modules (agents/copytrader/)

- `executor.py` — Main orchestrator (330 lines)
- `risk_kernel.py` — Risk limits enforcement (311 lines)
- `intent.py` — Intent schema and validation (157 lines)
- `position_tracker.py` — PnL tracking (230 lines)
- `storage.py` — SQLite persistence (263 lines)
- `allowlist.py` — Politics market filtering (126 lines)
- `alerts.py` — Telegram notifications (130 lines)

### Tests

- `tests/test_copytrader.py` — 21-test suite (539 lines)
- `tests/mocks/mock_polymarket_client.py` — Mock executor (83 lines)

### Scripts

- `scripts/python/copytrader_dryrun.py` — Standalone validation script
- `scripts/python/cli.py` — Main CLI (includes `run-copytrader` command)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2025-12-31 | Phase 0 + Phase 1 complete, signed off by Tony |

---

## Design Philosophy

> "We are not trying to be clever today. We are trying to be correct."
> — Tony

### Principles

1. **Fail-closed** — No data = no trades
2. **Deterministic** — Same inputs → same outputs
3. **Observable** — Explain every decision
4. **Contained** — External failures don't cascade
5. **Boring** — Prefer simplicity over cleverness

### Why This Matters

Most trading bots fail because:

- Hidden state
- Undefined failure modes
- Scope creep during development
- "Smart" logic that's actually fragile

V1 survives because it's **boringly correct**.

---

## Support

**Questions?** Review this document first.
**Bugs?** Check if it's a Phase 2 integration issue.
**Improvements?** Phase 1 is frozen. Propose for Phase 2+.

---

**Phase 1 Status**: ✅ Complete — Validated — Execution Disabled
**Next Phase**: Phase 2 (Live Execution Enablement) — Not started
