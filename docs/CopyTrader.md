# CopyTrader Integration

## Overview

The CopyTrader module enables Polymarket Agents to follow and copy trades from successful traders. The architecture follows a strict security boundary:

- **TypeScript Signal Generator** (`integrations/copytrader_ts/`): Sandboxed service that monitors trader activity and emits TradeIntent messages (NO private keys)
- **Python Executor** (`agents/copytrader/`): Validates and executes intents using existing Polymarket order execution (holds private keys)

## Architecture: Bridge + Intent Pattern

```
┌─────────────────────────────────┐
│ TypeScript Signal Generator     │
│ (integrations/copytrader_ts/)   │
│                                 │
│ - Monitor trader activity       │
│ - Fetch public data only        │
│ - Emit TradeIntent JSON         │
│ - NO private keys               │
│ - NO trade execution            │
└──────────┬──────────────────────┘
           │ TradeIntent
           │ (JSON/HTTP)
           ▼
┌─────────────────────────────────┐
│ Validation Firewall             │
│ (agents/copytrader/firewall.py) │
│                                 │
│ ✓ Trader allowlist              │
│ ✓ Market allowlist              │
│ ✓ Size limits                   │
│ ✓ Staleness check               │
│ ✓ Deduplication                 │
└──────────┬──────────────────────┘
           │ Validated Intent
           ▼
┌─────────────────────────────────┐
│ Python Executor                 │
│ (agents/copytrader/strategy.py) │
│                                 │
│ - Position sizing               │
│ - Orderbook validation          │
│ - Execute via Polymarket        │
│ - Track purchases               │
│ - HOLDS private keys            │
└─────────────────────────────────┘
```

## Quick Start

### 1. Configure Python Executor

Set environment variables:

```bash
# Traders to follow (comma-separated Ethereum addresses)
export FOLLOW_TRADERS="0xabc123...,0xdef456..."

# Optional: Market allowlist (empty = all markets allowed)
export MARKET_ALLOWLIST="market_id_1,market_id_2"

# Safety limits
export MAX_INTENT_SIZE_USDC=100.0  # Maximum order size per intent
export MAX_INTENT_AGE_SECONDS=60   # Reject intents older than this

# Position sizing strategy
export COPY_SIZING_STRATEGY=PERCENTAGE  # FIXED, PERCENTAGE, or TIERED
export COPY_SIZE=10.0  # Meaning depends on strategy

# Optional: Tiered multipliers (for TIERED strategy)
# Format: "min-max:mult,min-max:mult,min+:mult"
# export TIERED_MULTIPLIERS="1-100:2.0,100-1000:0.5,1000+:0.1"

# Slippage protection
export MAX_SLIPPAGE_PERCENT=5.0
```

### 2. Set Up TypeScript Signal Generator

```bash
cd integrations/copytrader_ts

# Install dependencies (disable postinstall for security)
npm install --ignore-scripts

# Configure
cp .env.example .env
# Edit .env to set MONITORED_TRADERS

# Build
npm run build
```

### 3. Run Health Check

```bash
python scripts/python/cli.py copytrader-health-check
```

### 4. Start Services

**Terminal 1: Python Executor (holds keys)**
```bash
python scripts/python/cli.py run-copy-trader
```

**Terminal 2: TypeScript Signal Generator (no keys)**
```bash
cd integrations/copytrader_ts
npm start
```

## Position Sizing Strategies

### FIXED Strategy

Copy a fixed dollar amount per trade, regardless of trader's order size.

```bash
export COPY_SIZING_STRATEGY=FIXED
export COPY_SIZE=50.0  # Always trade $50
```

**Use case**: Predictable spending, budget control

### PERCENTAGE Strategy

Copy a percentage of the trader's order size.

```bash
export COPY_SIZING_STRATEGY=PERCENTAGE
export COPY_SIZE=10.0  # Copy 10% of trader's order
```

**Use case**: Proportional exposure, scales with trader confidence

### TIERED Strategy

Apply different multipliers based on trade size (handles traders with varying position sizes).

```bash
export COPY_SIZING_STRATEGY=TIERED
export TIERED_MULTIPLIERS="1-100:2.0,100-500:1.0,500-1000:0.5,1000+:0.1"
```

Example with $2k account following $500k trader:
- Trader's $5 order → 2.0x = $10 copy
- Trader's $250 order → 1.0x = $250 copy
- Trader's $750 order → 0.5x = $375 copy
- Trader's $5000 order → 0.1x = $500 copy

**Use case**: Following traders with different capital bases

## Threat Model

### Security Assumptions

1. **TypeScript service is untrusted**: It runs in an environment with NO access to private keys
2. **Python executor validates everything**: All intents pass through validation firewall
3. **Allowlists are enforced**: Only whitelisted traders/markets can trigger trades
4. **Position limits protect capital**: Max intent size prevents oversized orders

### Attack Scenarios & Mitigations

| Attack Vector | Description | Mitigation |
|--------------|-------------|------------|
| **Compromised TS Service** | Attacker controls signal generator | Firewall validates all intents; no keys in TS environment |
| **Malicious Intents** | Attacker injects fake trade intents | Trader allowlist prevents unauthorized traders |
| **Replay Attack** | Re-execute old intents multiple times | Deduplication by intent_id prevents double-execution |
| **Stale Price Manipulation** | Execute intent with outdated prices | Staleness check + orderbook validation reject old intents |
| **Large Order Attack** | Force execution of oversized order | Max intent size cap enforced by firewall |
| **Market Manipulation** | Target illiquid or manipulated markets | Market allowlist (optional) restricts tradeable markets |
| **Position Drift** | Sell wrong amount due to balance changes | Purchase tracking with myBoughtSize maintains accuracy |

### Defense in Depth

1. **Separation of Concerns**
   - Signal generation = TypeScript (no keys)
   - Trade execution = Python (holds keys)
   - Clear boundary prevents key exposure

2. **Validation Firewall**
   - Trader allowlist (FOLLOW_TRADERS)
   - Market allowlist (MARKET_ALLOWLIST, optional)
   - Size limits (MAX_INTENT_SIZE_USDC)
   - Staleness check (MAX_INTENT_AGE_SECONDS)
   - Deduplication (intent_id tracking)

3. **Execution Guards**
   - Orderbook validation before execution
   - Slippage protection (MAX_SLIPPAGE_PERCENT)
   - Retry limits prevent runaway execution

4. **Position Tracking**
   - SQLite backend tracks exact purchases
   - Proportional sells based on tracked buys
   - Prevents position drift from balance changes

## Configuration Reference

### Python Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FOLLOW_TRADERS` | Yes | - | Comma-separated trader addresses to copy |
| `MARKET_ALLOWLIST` | No | all markets | Comma-separated market IDs (empty = all) |
| `MAX_INTENT_SIZE_USDC` | No | 100.0 | Maximum order size per intent (USDC) |
| `MAX_INTENT_AGE_SECONDS` | No | 60 | Maximum intent age before rejection |
| `MAX_SLIPPAGE_PERCENT` | No | 5.0 | Maximum allowed slippage (%) |
| `COPY_SIZING_STRATEGY` | No | PERCENTAGE | Position sizing: FIXED, PERCENTAGE, TIERED |
| `COPY_SIZE` | No | 10.0 | Base size (meaning depends on strategy) |
| `TIERED_MULTIPLIERS` | No | - | Tiered multipliers (for TIERED strategy) |

### TypeScript Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MONITORED_TRADERS` | Yes | - | Comma-separated trader addresses to monitor |
| `OUTPUT_MODE` | No | file | Output mode: file or http |
| `OUTPUT_FILE` | No | ../../intents.jsonl | File path for intent output |
| `PYTHON_ENDPOINT` | No | http://127.0.0.1:8765/intent | HTTP endpoint for Python executor |
| `POLL_INTERVAL` | No | 1 | Polling interval (seconds) |

## Advanced Usage

### Custom Storage Backend

Replace SQLite with custom backend:

```python
from agents.copytrader.tracking import TrackingBackend, PurchaseTracker

class MongoTrackingBackend(TrackingBackend):
    # Implement abstract methods
    pass

tracker = PurchaseTracker(backend=MongoTrackingBackend())
```

### Multiple Strategies

Run multiple copy strategies with different configs:

```python
from agents.copytrader.strategy import CopyTraderStrategy

# Conservative strategy
conservative_config = CopyTraderConfig(
    allowed_traders={...},
    max_intent_size_usdc=50.0,
)
conservative_strategy = CopyTraderStrategy(polymarket, conservative_config, ...)

# Aggressive strategy
aggressive_config = CopyTraderConfig(
    allowed_traders={...},
    max_intent_size_usdc=200.0,
)
aggressive_strategy = CopyTraderStrategy(polymarket, aggressive_config, ...)
```

### Intent Logging for Audit

Log all intents for compliance:

```python
class AuditIngestor(IntentIngestor):
    def _process_intent_dict(self, data: dict) -> None:
        # Log to audit trail
        audit_logger.info(f"Intent received: {data}")

        # Continue normal processing
        super()._process_intent_dict(data)
```

## Testing

### Run Unit Tests

```bash
# Test schema validation and firewall
pytest tests/test_copytrader.py -v
```

### Run Integration Tests

```bash
# Test intent replay (deterministic)
pytest tests/test_copytrader_integration.py -v
```

### Manual Testing with Mock Intents

Create test intent file:

```bash
cat > test_intents.jsonl << EOF
{"intent_id":"test-001","timestamp":"$(date -u +%Y-%m-%dT%H:%M:%S)","source_trader":"0xabc...","market_id":"test_market","outcome":"YES","side":"BUY","size_usdc":10.0,"metadata":{}}
EOF
```

Configure Python to read file:

```python
from agents.copytrader.config import CopyTraderConfig
from agents.copytrader.ingest import FileIngestor

config = CopyTraderConfig(allowed_traders={"0xabc..."})
ingestor = FileIngestor(config, "test_intents.jsonl")
ingestor.start()

intent = ingestor.get_next_intent(timeout=2.0)
print(f"Received: {intent}")
```

## Monitoring & Observability

### Health Check

```bash
python scripts/python/cli.py copytrader-health-check
```

Validates:
- Trader allowlist configured
- Size limits sensible
- Storage backend working
- Polymarket API connectivity
- Wallet balance sufficient

### Runtime Statistics

```python
# Firewall stats
stats = firewall.get_stats()
print(f"Validated: {stats['validated_count']}, Rejected: {stats['rejected_count']}")

# Strategy stats
stats = strategy.get_stats()
print(f"Executions: {stats['executions']}, Rejections: {stats['rejections']}")

# Tracking stats
stats = tracker.backend.get_stats()
print(f"Purchases: {stats['total_purchases']}, Markets: {stats['unique_markets']}")
```

## Troubleshooting

### "Trader not in allowlist"

**Cause**: Trader address not in FOLLOW_TRADERS

**Fix**: Add trader to allowlist:
```bash
export FOLLOW_TRADERS="0xabc...,0xnewtrader..."
```

### "Intent is stale"

**Cause**: Intent too old (>MAX_INTENT_AGE_SECONDS)

**Fix**: Increase staleness tolerance or reduce polling interval:
```bash
export MAX_INTENT_AGE_SECONDS=120  # Allow older intents
```

### "Slippage too high"

**Cause**: Price moved between observation and execution

**Fix**: Increase slippage tolerance or reduce latency:
```bash
export MAX_SLIPPAGE_PERCENT=10.0
```

### "No tracked purchases found"

**Cause**: Trying to sell but no purchase tracking exists

**Fix**: This is expected if position was opened before tracking started. Manual position close required.

## Security Checklist

Before deploying to production:

- [ ] TypeScript service has NO access to private keys
- [ ] FOLLOW_TRADERS allowlist is configured
- [ ] MAX_INTENT_SIZE_USDC is reasonable for your capital
- [ ] MAX_SLIPPAGE_PERCENT protects against bad fills
- [ ] Health check passes
- [ ] Tests pass (`pytest tests/test_copytrader*.py`)
- [ ] TypeScript dependencies audited (`npm audit`)
- [ ] No postinstall scripts in package.json
- [ ] Monitoring/logging configured
- [ ] Backup wallet has limited funds

## License & Disclaimer

This software is for educational purposes only. Trading involves risk of loss. The developers are not responsible for any financial losses incurred while using this module.

**US persons and persons from certain jurisdictions are prohibited from trading on Polymarket.** See https://polymarket.com/tos.
