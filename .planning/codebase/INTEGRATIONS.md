# External Integrations

**Analysis Date:** 2026-01-08

## APIs & External Services

**LLM APIs:**
- OpenAI - LLM API (gpt-3.5-turbo-16k, gpt-4-1106-preview) - `agents/application/executor.py`
  - SDK/Client: openai 1.35.12, langchain-openai 0.1.19
  - Auth: API key in `OPENAI_API_KEY` env var
  - Usage: Market analysis, forecasting, RAG-based filtering
- Grok (xAI) - Alternative LLM (grok-4-1-fast-reasoning/non-reasoning) - `agents/application/executor.py`
  - Integration method: Custom LangChain wrapper
  - Auth: API key from environment
  - Usage: Alternative to OpenAI for decision-making

**Prediction Markets:**
- Polymarket Gamma API - Market and event metadata - `agents/polymarket/gamma.py`
  - Integration method: REST API via httpx
  - Endpoints: gamma-api.polymarket.com/markets, /events
  - Auth: None (public API)
  - Usage: Fetch tradeable markets and events
- Polymarket CLOB API - Central Limit Order Book trading - `agents/polymarket/polymarket.py`
  - Integration method: py-clob-client 0.17.5
  - Endpoints: clob.polymarket.com
  - Auth: Wallet signature (POLYGON_WALLET_PRIVATE_KEY)
  - Usage: Order execution, trade history

**Data & News APIs:**
- NewsAPI - News retrieval for market context - `agents/connectors/news.py`
  - SDK/Client: newsapi-python 0.2.7
  - Auth: API key in `NEWSAPI_API_KEY` env var
  - Endpoints: newsapi.org/v2/top-headlines, /everything
  - Usage: Contextual news for market analysis
- Tavily - Web search integration - `agents/connectors/search.py`
  - SDK/Client: tavily-python 0.5.0
  - Auth: API key in `TAVILY_API_KEY` env var
  - Usage: General web search for market research
- LunarCrush - Social sentiment data - `agents/connectors/lunarcrush.py`
  - Integration method: REST API via httpx
  - Auth: API key in `LUNARCRUSH_API_KEY` env var
  - Usage: Social media sentiment tracking

## Data Storage

**Databases:**
- SQLite - Local persistence - `agents/copytrader/storage.py`
  - Connection: File-based (copytrader.db, copytrader_dryrun.db)
  - Client: SQLAlchemy 2.0.31
  - Usage: Position tracking, trade history, intent logs
- ChromaDB - Vector database - `agents/connectors/chroma.py`
  - Connection: Local file-based (local_db_events/, local_db_markets/)
  - Client: chromadb 0.5.5
  - Embeddings: OpenAI text-embedding-3-small
  - Usage: RAG semantic search over markets and events

**File Storage:**
- Local filesystem - JSON persistence
  - Locations: `local_db_events/`, `local_db_markets/`
  - Format: JSON files with market/event data
  - Usage: RAG data caching, local development

## Authentication & Identity

**Blockchain Authentication:**
- Polygon Wallet - Ethereum-compatible wallet - `agents/polymarket/polymarket.py`
  - Implementation: web3.py 6.11.0, eth-account 0.13.1
  - Key storage: POLYGON_WALLET_PRIVATE_KEY env var
  - Usage: Order signing, transaction submission
- EIP-712 Signing - Structured data signing - `agents/polymarket/polymarket.py`
  - Libraries: poly_eip712_structs 0.0.1, eip712-structs 1.1.0
  - Usage: Polymarket order authentication

## Monitoring & Observability

**Error Tracking:**
- Not detected - No Sentry or similar error tracking

**Analytics:**
- PostHog 3.5.0 - Product analytics (installed but minimal usage detected)
- LangSmith 0.1.94 - LLM monitoring via LangChain

**Logs:**
- Standard output - Print statements throughout codebase
- Discord Webhooks - `agents/utils/discord_alerts.py` (alert notifications)

**Tracing:**
- OpenTelemetry - Distributed tracing stack
  - opentelemetry-api 1.26.0
  - opentelemetry-instrumentation-fastapi 0.47b0
  - opentelemetry-sdk 1.26.0
  - opentelemetry-exporter-otlp-proto-grpc 1.26.0

## CI/CD & Deployment

**Hosting:**
- Docker - Containerized deployment
  - Image: Python 3.9 base
  - Build: `scripts/bash/build-docker.sh`
  - Run: `scripts/bash/run-docker-dev.sh`

**CI Pipeline:**
- GitHub Actions - `.github/workflows/`
  - `python-app.yml` - Test + lint on push/PR to main
  - `docker-image.yml` - Docker build validation
  - `dependency-review.yml` - Dependency scanning
  - Secrets: None detected in workflows (uses environment)

## Environment Configuration

**Development:**
- Required env vars: POLYGON_WALLET_PRIVATE_KEY, OPENAI_API_KEY, TAVILY_API_KEY, NEWSAPI_API_KEY
- Optional env vars: LUNARCRUSH_API_KEY, Grok API keys
- Secrets location: .env.local (gitignored), .env.example template
- Mock services: None detected (uses live APIs)

**Production:**
- Same env vars as development
- Blockchain: Polygon mainnet (chain_id: 137)
- RPC: polygon-rpc.com (public endpoint)

## Webhooks & Callbacks

**Incoming:**
- Not detected - No webhook endpoints

**Outgoing:**
- Discord Webhooks - `agents/utils/discord_alerts.py`
  - Endpoint: Discord webhook URL
  - Events: Trade alerts, system notifications
  - Retry logic: Not detected

## Blockchain Integration

**Network:**
- Polygon (chain_id: 137) - `agents/polymarket/polymarket.py:45`
- RPC: polygon-rpc.com (public)

**Contracts:**
- CTF Exchange: 0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e - `agents/polymarket/polymarket.py:50`
- Neg Risk Exchange: 0xC5d563A36AE78145C45a50134d48A1215220f80a - `agents/polymarket/polymarket.py:51`
- USDC: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174 - `agents/polymarket/polymarket.py:56`
- CTF Token: 0x4D97DCd97eC945f40cF65F87097ACe5EA0476045 - `agents/polymarket/polymarket.py:57`

---

*Integration audit: 2026-01-08*
*Update when adding/removing external services*
