# CopyTrader TypeScript Signal Generator

## ⚠️ SECURITY NOTICE

**This service is SANDBOXED and UNTRUSTED.**

- **NEVER** provide this service with private keys
- **NEVER** allow this service to sign transactions
- **NEVER** execute binaries from this directory
- **ONLY** reads public data from Polymarket APIs
- **ONLY** outputs TradeIntent JSON messages

## Purpose

This service monitors trader activity on Polymarket and emits TradeIntent messages
when new trades are detected. The Python executor validates and executes these intents.

## Architecture

```
TypeScript Service (THIS)          Python Executor (agents/)
──────────────────────              ───────────────────────
- Read public APIs                  - Hold private keys
- Detect trader activity            - Validate intents
- Emit TradeIntent JSON     ───>    - Execute orders
- NO private keys                   - Track positions
- NO trade execution
```

## What This Service Does

1. Polls Polymarket Data API for trader activity
2. Detects new trades by comparing positions over time
3. Fetches orderbook data for price context
4. Outputs TradeIntent JSON (to file or HTTP)

## What This Service CANNOT Do

- Cannot access private keys (they are in Python service only)
- Cannot sign transactions
- Cannot execute trades
- Cannot modify existing positions
- Cannot access wallet beyond public address

## Installation

```bash
npm install --ignore-scripts  # Disable postinstall hooks for security
```

## Configuration

Create `.env` file (only PUBLIC data):

```env
# Traders to monitor (comma-separated public addresses)
MONITORED_TRADERS=0xabc...,0xdef...

# Output mode: file or http
OUTPUT_MODE=file
OUTPUT_FILE=../intents.jsonl

# OR for HTTP mode:
# OUTPUT_MODE=http
# PYTHON_ENDPOINT=http://127.0.0.1:8765/intent

# Polling interval (seconds)
POLL_INTERVAL=1
```

## Running

```bash
npm run build
npm start
```

## Threat Model

### Assumptions

1. This code runs in an environment with no access to private keys
2. Python executor validates ALL intents before execution
3. Firewall prevents oversized/stale/duplicate intents

### Attack Scenarios

| Attack | Mitigation |
|--------|-----------|
| Compromise TS service | Can only emit intents; Python firewall validates all |
| Inject malicious intent | Python allowlists prevent unauthorized traders/markets |
| Replay attack | Python deduplicates by intent_id |
| Stale price manipulation | Python checks intent age and orderbook |
| Large order attack | Python enforces max_intent_size |

### Defense in Depth

1. **Separation**: No keys in TypeScript environment
2. **Validation**: Python firewall validates everything
3. **Allowlists**: Only whitelisted traders/markets
4. **Deduplication**: Prevents double-execution
5. **Staleness**: Rejects old intents
6. **Size caps**: Prevents oversized orders

## Auditing

Before running this service:

1. Review all dependencies in package.json
2. Check package-lock.json is pinned (no floating versions)
3. Verify no postinstall scripts in dependencies
4. Review source code for any key/signing operations (should be NONE)

## Dependencies

Minimal dependencies only:
- `cross-fetch`: HTTP requests
- `dotenv`: Environment variables
- TypeScript tooling (dev dependencies)

NO dependencies that:
- Sign transactions
- Handle private keys
- Execute shell commands
- Download additional code at runtime
