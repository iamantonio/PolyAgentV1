# Technology Stack

**Analysis Date:** 2026-01-08

## Languages

**Primary:**
- Python 3.9+ - All application code (`requirements.txt`, `.github/workflows/python-app.yml`)

**Secondary:**
- TypeScript 5.3 - `integrations/copytrader_ts/` (ES2020 target, Node >=18.0.0)
- JavaScript - Build scripts, configuration files

## Runtime

**Environment:**
- Python 3.9+ (specified in Docker, GitHub Actions)
- Node.js 18.0.0+ (for TypeScript modules)

**Package Manager:**
- pip - Python packages
- Lockfile: `requirements.txt` (173 dependencies)
- npm - TypeScript integration (`integrations/copytrader_ts/package.json`)

## Frameworks

**Core:**
- FastAPI 0.111.0 - `scripts/python/server.py` (web API server)
- Flask 3.0.0 - `dashboard_api.py`, `dashboard_server.py` (dashboard API)
- Flask-CORS 4.0.0 - CORS support
- Typer 0.12.3 - `scripts/python/cli.py` (CLI framework)

**Testing:**
- pytest 8.3.2 - Unit tests
- unittest - Standard library (minimal use)

**Build/Dev:**
- Black 24.4.2 - Code formatter (pre-commit hook)
- pre-commit 3.8.0 - Git hooks manager
- Docker - Python 3.9 base image

## Key Dependencies

**Critical:**
- LangChain 0.2.11 - `agents/application/executor.py`, `agents/connectors/chroma.py` (LLM orchestration, RAG)
  - langchain-openai 0.1.19
  - langchain-community 0.2.10
  - langchain-core 0.2.26
  - langchain-chroma 0.1.2
  - langgraph 0.1.17 (multi-agent coordination)
- Web3.py 6.11.0 - `agents/polymarket/polymarket.py` (Polygon blockchain interaction)
- py-clob-client 0.17.5 - Polymarket CLOB API client
- py-order-utils 0.3.2 - Order signing and construction
- ChromaDB 0.5.5 - `agents/connectors/chroma.py` (vector database for RAG)
- Pydantic 2.8.2 - `agents/utils/objects.py` (data validation)
- SQLAlchemy 2.0.31 - `agents/copytrader/storage.py` (ORM for SQLite)

**Infrastructure:**
- httpx 0.27.0 - Async HTTP client
- aiohttp 3.10.0 - Async HTTP operations
- requests 2.32.3 - Synchronous HTTP
- uvicorn 0.30.3 - ASGI server
- openai 1.35.12 - OpenAI API client
- newsapi-python 0.2.7 - NewsAPI integration
- tavily-python 0.5.0 - Web search

## Configuration

**Environment:**
- .env files - Environment variables
- .env.example - Template with required vars
- Key configs: `POLYGON_WALLET_PRIVATE_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`, `NEWSAPI_API_KEY`

**Build:**
- `.pre-commit-config.yaml` - Black formatter hook (Python 3.9)
- `tsconfig.json` - TypeScript compilation (`integrations/copytrader_ts/`)
- `Dockerfile` - Python 3.9 container

## Platform Requirements

**Development:**
- Any platform with Python 3.9+
- Docker for containerized development
- Node.js 18+ for TypeScript modules

**Production:**
- Docker container deployment
- Polygon (chain_id: 137) blockchain access
- External API access: OpenAI, Polymarket, NewsAPI, Tavily

---

*Stack analysis: 2026-01-08*
*Update after major dependency changes*
