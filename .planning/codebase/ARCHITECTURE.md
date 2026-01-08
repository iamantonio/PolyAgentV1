# Architecture

**Analysis Date:** 2026-01-08

## Pattern Overview

**Overall:** Layered Hexagonal Architecture + Multi-Agent Trading System

**Key Characteristics:**
- Modular monolith with clear domain boundaries
- Multi-agent autonomous decision-making
- Pure functional risk logic (no I/O)
- Event-driven async I/O
- RAG-based market filtering
- Blockchain integration for trade execution

## Layers

**Entry Point Layer:**
- Purpose: User-facing interfaces
- Contains: CLI commands, web APIs, scheduled jobs
- Key files: `scripts/python/cli.py`, `dashboard_server.py`, `agents/application/trade.py`
- Depends on: Application layer orchestrators
- Used by: External users, cron jobs

**Application/Orchestration Layer:**
- Purpose: High-level business logic and workflow orchestration
- Contains: `agents/application/` - Trader, Executor, Prompts
- Key files:
  - `agents/application/trade.py` - Main trading pipeline orchestrator
  - `agents/application/executor.py` - LLM interactions, market analysis
  - `agents/application/prompts.py` - Prompt templates
- Depends on: Domain layer, Integration layer
- Used by: Entry points

**Domain Layer - Trading Logic:**
- Purpose: Core trading system with risk management
- Contains: `agents/copytrader/`, `agents/learning/`, `agents/reasoning/`, `agents/strategies/`
- Key modules:
  - `agents/copytrader/executor.py` - Main orchestrator: intent → validate → risk → execute → alert
  - `agents/copytrader/risk_kernel.py` - Pure deterministic risk approval (no I/O)
  - `agents/copytrader/position_tracker.py` - Position tracking, PnL
  - `agents/learning/integrated_learner.py` - ML-based edge detection
  - `agents/reasoning/multi_agent.py` - Multi-agent prediction validation
- Depends on: Data layer
- Used by: Application layer

**Integration Layer:**
- Purpose: External API communication
- Contains: `agents/polymarket/`, `agents/connectors/`
- Key modules:
  - `agents/polymarket/polymarket.py` - CLOB client, order execution
  - `agents/polymarket/gamma.py` - Gamma API for market metadata
  - `agents/connectors/chroma.py` - RAG vector search
  - `agents/connectors/news.py` - NewsAPI integration
  - `agents/connectors/lunarcrush.py` - Social sentiment
- Depends on: External APIs, Data layer
- Used by: Application layer, Domain layer

**Data Layer:**
- Purpose: Persistence and data models
- Contains: `agents/utils/`, `agents/copytrader/storage.py`
- Key modules:
  - `agents/utils/objects.py` - Pydantic models (Trade, Market, Event, etc.)
  - `agents/copytrader/storage.py` - SQLite persistence
  - ChromaDB vector storage
- Depends on: Nothing (pure data)
- Used by: All layers

## Data Flow

**Autonomous Trading Pipeline:**

1. **Event Discovery**: Trader.one_best_trade() → Polymarket.get_all_tradeable_events()
2. **RAG Filtering**: Executor.filter_events_with_rag() → ChromaDB semantic search
3. **Market Mapping**: Executor.map_filtered_events_to_markets() → GammaMarketClient
4. **Market Filtering**: Polymarket.filter_markets_for_trading() (spread, volume, etc.)
5. **Trade Decision**: Executor.source_best_trade() → LLM analysis
6. **Execution**: Polymarket.execute_market_order() → CLOB API (commented out)

**CopyTrader Execution Flow:**

1. **Intent Validation**: IntentValidator.validate() checks staleness, allowlist, limits
2. **Risk Approval**: RiskKernel.evaluate() (pure function, no I/O)
3. **Execution**: ExecutorAdapter.execute() (mock or live)
4. **Position Recording**: PositionTracker.record_trade() → SQLite
5. **Alert Notification**: AlertService.notify() → Discord webhook

**State Management:**
- SQLite: Persistent position tracking, trade history
- ChromaDB: Vector embeddings for RAG search
- In-memory: None (stateless request handling)

## Key Abstractions

**RiskKernel:**
- Purpose: Pure deterministic trade approval logic
- Location: `agents/copytrader/risk_kernel.py`
- Pattern: Pure function (no side effects, no I/O)
- Examples: Daily stop (-5%), hard kill (-20%), per-trade cap (3%)

**ExecutorAdapter:**
- Purpose: Strategy pattern for mock vs. live execution
- Location: `agents/copytrader/executor_adapter.py`
- Pattern: Adapter/Strategy
- Examples: MockExecutor, LiveExecutor

**TradeIntent:**
- Purpose: Validated trade request
- Location: `agents/copytrader/intent.py`
- Pattern: Pydantic model with validation
- Examples: IntentValidator checks staleness, allowlist, format

**PositionTracker:**
- Purpose: Track open positions and PnL
- Location: `agents/copytrader/position_tracker.py`
- Pattern: Repository pattern
- Examples: record_trade(), get_open_positions(), calculate_pnl()

**IntegratedLearningBot:**
- Purpose: ML-based edge detection and calibration
- Location: `agents/learning/integrated_learner.py`
- Pattern: Composition (combines multiple learners)
- Examples: EdgeDetection, FeatureLearner, IsotonicCalibrator

## Entry Points

**CLI Entry:**
- Location: `scripts/python/cli.py`
- Triggers: User runs `python scripts/python/cli.py <command>`
- Responsibilities: Command routing, argument parsing
- Commands: get-all-markets, run-autonomous-trader, ask-superforecaster, etc.

**Trading Entry:**
- Location: `agents/application/trade.py`
- Triggers: CLI command `run-autonomous-trader` or cron job
- Responsibilities: Execute full trading pipeline

**Dashboard Entry:**
- Location: `dashboard_server.py` (Flask), `scripts/python/server.py` (FastAPI)
- Triggers: HTTP requests to web API
- Responsibilities: Serve dashboard, expose trading metrics

## Error Handling

**Strategy:** Fail-loud with exceptions, retry with exponential backoff (incomplete)

**Patterns:**
- RiskKernel: Pure function returns approval/rejection (no exceptions)
- API calls: Bare except clauses (ANTI-PATTERN - needs fixing)
- Trade execution: Commented out (requires review)
- Validation: Pydantic models raise ValidationError

**Issues:**
- Bare `except:` clauses in `agents/application/trade.py` (swallow all errors)
- Infinite recursion risk in retry logic
- Missing error handling for API responses

## Cross-Cutting Concerns

**Logging:**
- Current: Print statements throughout codebase (25+ instances)
- Needed: Structured logging with Python logging module

**Validation:**
- Pydantic models at API boundaries
- IntentValidator for trade requests
- Schema validation in storage layer

**Authentication:**
- Polygon wallet signature for CLOB orders
- EIP-712 structured data signing
- No user authentication (single-user system)

---

*Architecture analysis: 2026-01-08*
*Update when major patterns change*
