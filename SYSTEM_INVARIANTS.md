# SYSTEM INVARIANTS
**Role:** Single source of truth for non-negotiable rules. Files are law; chat is suggestion.

## Domain
- This project's purpose: AI agents for autonomous trading on Polymarket prediction markets using LLMs and RAG
- Primary user / stakeholder: Developers building trading agents, researchers, traders

## Non-Negotiables (Hard Rules)
- Safety > speed. Correctness > cleverness.
- If we can't explain it, we don't ship it.
- If we can't log it, it didn't happen.
- No changes to production-critical behavior without tests or explicit risk acceptance.
- **CRITICAL**: Trade execution is DISABLED by default. Must be explicitly enabled with full TOS understanding.
- **CRITICAL**: Private keys never committed. Only via `.env` which is gitignored.
- **CRITICAL**: US persons and restricted jurisdictions prohibited per Polymarket TOS.

## Data & Permission Boundaries
- Source-of-truth data systems:
  - Polymarket Gamma API (markets, events metadata)
  - Polymarket CLOB API (orderbooks, trade execution)
  - Polygon blockchain (on-chain state)

- READ/WRITE rules:
  - `Polymarket` class can READ: markets, events, orderbooks ; can WRITE: trades, approvals (blockchain)
  - `GammaMarketClient` can READ: markets, events ; can WRITE: nothing (read-only API client)
  - `Executor` can READ: market data, news, LLM responses ; can WRITE: predictions, analysis (no blockchain writes)
  - `PolymarketRAG` can READ: market data ; can WRITE: local vector databases only
  - `News` can READ: NewsAPI ; can WRITE: nothing (read-only)

- Secrets never committed. Secrets only via `.env` file:
  - `POLYGON_WALLET_PRIVATE_KEY`
  - `OPENAI_API_KEY`
  - `NEWSAPI_API_KEY`
  - `TAVILY_API_KEY`

## Operational Limits (Budgets)
- Timeouts: No explicit timeouts defined (relies on httpx defaults ~5s, blockchain confirmations variable)
- Rate limits / quotas:
  - OpenAI API: Depends on tier (monitor token usage)
  - NewsAPI: Free tier = 100 requests/day
  - Polymarket API: No official limit documented (be respectful)
- Cost ceiling per day/week: Not defined (user-managed via API keys)
- Latency target (if applicable): Sub-second for API calls, 3-10s for blockchain confirmations
- LLM token limits:
  - gpt-3.5-turbo-16k: 15,000 tokens
  - gpt-4-1106-preview: 95,000 tokens
  - Executor automatically chunks requests that exceed limits

## Release Safety
- Environments: DEV only (no staging/prod infrastructure defined)
- PROD changes require: (choose)
  - [ ] feature flag (not implemented)
  - [x] rollback plan (git revert)
  - [ ] monitoring/alerts (not implemented)
  - [ ] migration plan (manual - local DBs are ephemeral)

- **Trade execution safeguard**: Line 60 in `agents/application/trade.py` is commented out. Uncommenting requires:
  1. Full review of Polymarket TOS
  2. Verification of wallet funding (USDC + MATIC)
  3. Testing on small amounts first
  4. Understanding that trades are REAL and irreversible

## Explicit Anti-Goals (We refuse to optimize for)
- Bypassing jurisdiction restrictions or TOS compliance
- Trading without understanding (no "black box" execution without explanation)
- Optimizing for maximum profit at expense of risk management
- Hiding failures or losses (transparency required)
- Complex abstractions that obscure what trades are being made

## Known Failure Modes (List the top recurring ways this can break)
- **LLM token limit exceeded**: Executor chunks data but edge cases may still fail (see issue #23)
- **API rate limiting**: OpenAI, NewsAPI, or Polymarket APIs can throttle requests
- **Wallet insufficient funds**: Trades fail if USDC balance too low or no MATIC for gas
- **Stale market data**: Local RAG databases can become outdated if not refreshed
- **Private key exposure**: Accidental commit of `.env` file
- **Network issues**: Polygon RPC endpoint failures or connectivity problems
- **Order signing failures**: Web3 transaction errors if nonce issues or gas estimation problems
- **Prompt injection via market descriptions**: Malicious market text could manipulate LLM decisions

## Blockchain-Specific Invariants
- Network: Polygon mainnet (chain_id: 137)
- USDC address: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- CTF address: `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`
- Exchange address: `0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e`
- Neg Risk Exchange: `0xC5d563A36AE78145C45a50134d48A1215220f80a`
- Polygon RPC: `https://polygon-rpc.com` (consider backup RPCs for production)

## Data Integrity
- Local vector databases (`local_db_events/`, `local_db_markets/`) are CLEARED before each trading run
- This is intentional to prevent stale data, but means no historical RAG context is preserved
- Pydantic models enforce schema validation for all API responses
