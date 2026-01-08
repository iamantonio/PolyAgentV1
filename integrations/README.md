# Integrations Directory

## ⚠️ SECURITY WARNING

This directory contains **SANDBOXED** external services that are **UNTRUSTED**.

### Security Policy

**NO service in this directory may:**
- Access private keys
- Sign transactions
- Execute trades
- Modify wallet state

**Services in this directory may ONLY:**
- Read public APIs
- Emit signals/intents
- Process public data

## Current Integrations

### copytrader_ts/

**Purpose**: Monitor trader activity and emit TradeIntent messages

**Trust Level**: UNTRUSTED (sandboxed)

**Access**:
- ✅ Polymarket Data API (public)
- ✅ Orderbook data (public)
- ❌ Private keys (NEVER)
- ❌ Trade execution (NEVER)

**Data Flow**: TypeScript → JSON → Python Executor

See [`copytrader_ts/README.md`](copytrader_ts/README.md) for details.

## Adding New Integrations

When adding a new integration to this directory:

1. **Create isolated subdirectory**
   - Each integration gets its own folder
   - No shared dependencies across integrations

2. **Document security boundary**
   - Create README explaining what it CAN and CANNOT do
   - List all external APIs accessed
   - Document data flow

3. **Enforce sandboxing**
   - No access to parent directory's secrets
   - No execution of Python code from TypeScript
   - No shared credentials

4. **Audit dependencies**
   - Pin all versions in lockfile
   - Disable postinstall scripts (`--ignore-scripts`)
   - Run `npm audit` / `pip audit`

5. **Test isolation**
   - Service can be killed without affecting Python
   - Python continues safely if service crashes
   - No shared state beyond message passing

## Directory Structure

```
integrations/
├── README.md (this file)
└── copytrader_ts/          # TypeScript signal generator
    ├── README.md           # Security documentation
    ├── package.json        # Pinned dependencies
    ├── tsconfig.json       # TypeScript config
    ├── .env.example        # Public config only
    └── src/
        ├── index.ts        # Entry point
        ├── monitor.ts      # Trade monitoring
        └── output.ts       # Intent emission
```

## Verification

Before running any integration:

```bash
# Check for private keys (should find NONE)
grep -r "PRIVATE_KEY\|SECRET\|MNEMONIC" integrations/copytrader_ts/

# Check for signing operations (should find NONE)
grep -r "sign\|wallet\|eth_sendTransaction" integrations/copytrader_ts/src/

# Audit dependencies
cd integrations/copytrader_ts && npm audit
```

## Incident Response

If you suspect a sandboxed service is compromised:

1. **Kill the service immediately**
   ```bash
   killall -9 node  # Kill TypeScript service
   ```

2. **Python executor continues safely** (it validates everything)

3. **Check logs** for unusual intents or rejected validations

4. **Review firewall stats** to see if attack was blocked
   ```python
   firewall.get_stats()  # Check rejection count
   ```

5. **Rotate keys if needed** (Python-side only)

The firewall is designed to protect against compromised signal generators.
