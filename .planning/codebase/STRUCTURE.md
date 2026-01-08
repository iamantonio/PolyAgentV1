# Codebase Structure

**Analysis Date:** 2026-01-08

## Directory Layout

```
agents/
├── agents/                      # Main application code
│   ├── application/            # Orchestration layer
│   ├── polymarket/             # Polymarket API integration
│   ├── connectors/             # External data sources
│   ├── copytrader/             # Production trading system (v2)
│   ├── copytrader_legacy/      # Legacy trading system (v1)
│   ├── learning/               # ML learning system
│   ├── reasoning/              # Multi-agent reasoning
│   ├── strategies/             # Trading strategies
│   └── utils/                  # Shared utilities
├── scripts/                     # Executable scripts
│   ├── python/                 # Python scripts (CLI, servers)
│   ├── bash/                   # Shell scripts (deployment)
│   └── systemd/                # Systemd service files
├── tests/                       # Test suite
├── docs/                        # Documentation
├── integrations/                # External integrations (TypeScript)
│   └── copytrader_ts/          # CopyTrader TypeScript port
├── .github/workflows/           # CI/CD pipelines
├── dashboard.html               # Web UI
├── dashboard_server.py          # Flask dashboard API
├── dashboard_api.py             # Dashboard business logic
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Docker container
└── .env.example                 # Environment template
```

## Directory Purposes

**agents/application/**
- Purpose: High-level orchestration and business logic
- Contains: Trading pipeline, LLM executor, prompt templates
- Key files:
  - `trade.py` - Main Trader class, pipeline orchestrator
  - `executor.py` - LLM interactions, market analysis, RAG filtering
  - `prompts.py` - Prompt templates for different personas
  - `creator.py` - Market creation functionality
  - `cron.py` - Scheduled job management
- Subdirectories: None

**agents/polymarket/**
- Purpose: Polymarket API integration and blockchain interaction
- Contains: CLOB client, Gamma API wrapper, order signing
- Key files:
  - `polymarket.py` - Core Polymarket class (500 lines): API auth, order execution, Web3
  - `gamma.py` - GammaMarketClient for market/event metadata
- Subdirectories: None

**agents/connectors/**
- Purpose: External data source connectors
- Contains: RAG, news, search, social sentiment
- Key files:
  - `chroma.py` - PolymarketRAG for vector search
  - `news.py` - NewsAPI integration
  - `search.py` - Web search (Tavily)
  - `lunarcrush.py` - Social sentiment tracking
  - `websocket_monitor.py` - Real-time market monitoring
- Subdirectories: None

**agents/copytrader/**
- Purpose: Production copy trading system (v2)
- Contains: Intent validation, risk kernel, position tracking, execution
- Key files:
  - `executor.py` - Main orchestrator
  - `risk_kernel.py` - Pure risk logic (no I/O)
  - `position_tracker.py` - Position tracking and PnL
  - `storage.py` - SQLite persistence
  - `intent.py` - Trade intent validation
  - `allowlist.py` - Market whitelist service
  - `executor_adapter.py` - Mock/live execution adapter
  - `alerts.py` - Discord/Slack notifications
  - `config.py` - Configuration models
  - `risk.py` - Risk management utilities
- Subdirectories: None

**agents/copytrader_legacy/**
- Purpose: Legacy copy trading system (v1)
- Contains: Original implementation (deprecated)
- Key files: Similar structure to copytrader/
- Subdirectories: None

**agents/learning/**
- Purpose: Machine learning and calibration system
- Contains: Edge detection, feature learning, calibration
- Key files:
  - `integrated_learner.py` - Unified learning system
  - `feature_learning.py` - Feature extraction and pattern recognition
  - `calibration.py` - Confidence calibration tracking
  - `isotonic_calibration.py` - Isotonic regression
  - `trade_history.py` - Trade history database
- Subdirectories: None

**agents/reasoning/**
- Purpose: Multi-agent reasoning system
- Contains: Predictor-Critic-Synthesizer pattern
- Key files:
  - `multi_agent.py` - Multi-agent prediction validation
- Subdirectories: None

**agents/strategies/**
- Purpose: Trading strategies
- Contains: Arbitrage, pattern-based strategies
- Key files:
  - `arbitrage.py` - Arbitrage strategy implementation
- Subdirectories: None

**agents/utils/**
- Purpose: Shared utilities and data models
- Contains: Pydantic models, helper functions, alerts
- Key files:
  - `objects.py` - Pydantic models (Trade, Market, Event, etc.)
  - `utils.py` - Helper functions
  - `discord_alerts.py` - Discord notification service
- Subdirectories: None

**scripts/python/**
- Purpose: Python executable scripts
- Contains: CLI, servers, trading scripts
- Key files:
  - `cli.py` - Primary CLI (Typer framework)
  - `server.py` - FastAPI server
  - `continuous_trader.py` - 24/7 trading loop
  - `hybrid_autonomous_trader.py` - Hybrid strategy
  - `copytrader_dryrun.py` - Dry-run mode
- Subdirectories: None

**scripts/bash/**
- Purpose: Shell scripts for deployment and management
- Contains: Docker scripts, bot management
- Key files:
  - `build-docker.sh` - Build Docker image
  - `run-docker-dev.sh` - Run dev container
  - `run-24-7.sh` - Start 24/7 trading
  - `bot-status.sh` - Check bot status
  - `stop-bot.sh` - Stop trading bot
- Subdirectories: None

**tests/**
- Purpose: Test suite
- Contains: Unit and integration tests
- Key files:
  - `test_copytrader.py` - 20-test core suite
  - `test_copytrader_integration.py` - Integration tests
  - `test_parity.py` - Executor equivalence tests
  - `test.py` - Placeholder tests
- Subdirectories:
  - `mocks/` - Mock objects

**integrations/copytrader_ts/**
- Purpose: TypeScript port of CopyTrader
- Contains: TypeScript signal generator
- Key files:
  - `package.json` - Dependencies
  - `tsconfig.json` - TypeScript config (ES2020, strict mode)
- Subdirectories: Not analyzed

## Key File Locations

**Entry Points:**
- `scripts/python/cli.py` - Primary CLI interface
- `agents/application/trade.py` - Trading pipeline entry
- `dashboard_server.py` - Web dashboard (Flask)
- `scripts/python/server.py` - API server (FastAPI)

**Configuration:**
- `.env` - Environment variables (gitignored)
- `.env.example` - Environment template
- `.pre-commit-config.yaml` - Black formatter hook
- `Dockerfile` - Container configuration
- `requirements.txt` - Python dependencies
- `integrations/copytrader_ts/tsconfig.json` - TypeScript config

**Core Logic:**
- `agents/application/executor.py` - LLM orchestration, market analysis
- `agents/copytrader/executor.py` - Trade execution orchestrator
- `agents/copytrader/risk_kernel.py` - Risk approval logic
- `agents/polymarket/polymarket.py` - Blockchain integration
- `agents/learning/integrated_learner.py` - ML learning system

**Testing:**
- `tests/test_copytrader.py` - Core unit tests
- `tests/test_parity.py` - Interface compliance tests
- `.github/workflows/python-app.yml` - CI test pipeline

**Documentation:**
- `README.md` - Project overview
- `CLAUDE.md` - AI assistant instructions
- `docs/` - Project documentation
- Multiple *.md files in root (RUN_LOCAL.md, DECISIONS.md, etc.)

## Naming Conventions

**Files:**
- Snake case: `risk_kernel.py`, `position_tracker.py`, `polymarket.py`
- Module names: Descriptive, lowercase with underscores

**Directories:**
- Snake case: `copytrader/`, `copytrader_legacy/`, `learning/`
- Domain-specific: Organized by feature/concern

**Special Patterns:**
- `test_*.py` - Test files
- `*_legacy` - Deprecated/old implementations
- `*.example` - Template files

## Where to Add New Code

**New Trading Strategy:**
- Primary code: `agents/strategies/{strategy_name}.py`
- Tests: `tests/test_{strategy_name}.py`
- Integration: Import in `agents/application/trade.py`

**New Data Connector:**
- Implementation: `agents/connectors/{connector_name}.py`
- Integration: Import in `agents/application/executor.py`
- Config: Add API key to `.env.example`

**New Learning Component:**
- Implementation: `agents/learning/{component_name}.py`
- Integration: Compose in `agents/learning/integrated_learner.py`
- Tests: `tests/test_learning.py`

**New CLI Command:**
- Implementation: Add function to `scripts/python/cli.py` with `@app.command()` decorator
- Usage: `python scripts/python/cli.py {command-name}`

**Utilities:**
- Shared helpers: `agents/utils/utils.py`
- Data models: `agents/utils/objects.py` (Pydantic models)
- Alerts: `agents/utils/discord_alerts.py`

## Special Directories

**local_db_events/, local_db_markets/**
- Purpose: ChromaDB vector storage (RAG)
- Source: Generated by `agents/connectors/chroma.py`
- Committed: No (local artifacts)

**copytrader_dryrun.db**
- Purpose: SQLite database for dry-run testing
- Source: Generated by `agents/copytrader/storage.py`
- Committed: No (local artifacts)

**.agent/, .claude/, .windsurf/**
- Purpose: AI assistant working directories
- Source: Generated by AI tools
- Committed: No (tool artifacts)

**.github/workflows/**
- Purpose: CI/CD pipeline definitions
- Source: Version controlled
- Committed: Yes

---

*Structure analysis: 2026-01-08*
*Update when directory structure changes*
