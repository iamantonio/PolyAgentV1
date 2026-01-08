# DECISIONS
**Role:** Decision registry. Captures *why* so compaction can't erase it.

## Decision Threshold (When to log)
Log a decision if it:
- survives more than one work session, OR
- touches safety/security/cost/data integrity, OR
- introduces a "magic number" you'll argue about later, OR
- rejects a tempting alternative you might re-propose later.

## Status vocabulary
- ACTIVE: in force
- SUPERSEDED: replaced by D-0XX
- EXPERIMENTAL: has kill criteria
- DEPRECATED: still present, should not be reused

## Format (copy/paste)
```
## D-XXX: <Short title>
**Date:** YYYY-MM-DD
**Status:** ACTIVE | SUPERSEDED | EXPERIMENTAL | DEPRECATED

**Context:**
- What problem forced this decision?
- What constraints mattered?

**Decision:**
- What we chose (specifics, parameters, thresholds)

**Rationale:**
- Why this is the best tradeoff right now

**Rejected Alternatives:**
- Alternative A (why rejected)
- Alternative B (why rejected)

**Implementation:**
- File(s):path and (optional) line references

**Revisit If / Kill Criteria:**
- Conditions that invalidate this decision
```

---

## D-001: Python 3.9 Requirement
**Date:** 2024-01-01 (project inception)
**Status:** ACTIVE

**Context:**
- Need stable Python version with modern type hints
- Compatibility with py-clob-client and LangChain ecosystem
- Balance between modern features and broad compatibility

**Decision:**
- Pin Python 3.9 as the required version

**Rationale:**
- 3.9 has pattern matching, improved type hints, and good library support
- Older than cutting-edge (3.11+) for better dependency compatibility
- Well-supported by virtualenv and common deployment targets

**Rejected Alternatives:**
- Python 3.11+: Too new, potential dependency conflicts
- Python 3.8: Missing some type hint improvements
- Python 3.7: End of life, security issues

**Implementation:**
- README.md: Line 50
- Dockerfile: Line 1
- .pre-commit-config.yaml: Line 6

**Revisit If / Kill Criteria:**
- Major dependency requires 3.10+
- Python 3.9 reaches end of life (Oct 2025)
- Performance benchmarks show significant gains in newer versions

---

## D-002: Trade Execution Disabled by Default
**Date:** 2024-01-01 (project inception)
**Status:** ACTIVE

**Context:**
- Trading involves real money and is irreversible
- Users in restricted jurisdictions must not accidentally trade
- Need clear explicit opt-in for production trading

**Decision:**
- Comment out the `execute_market_order()` call in `agents/application/trade.py:60`
- Require manual uncommenting + TOS review before trades execute
- Include warning comment referencing polymarket.com/tos

**Rationale:**
- Prevents accidental real-money trades during development/testing
- Forces users to consciously enable trading
- Legal safety: makes TOS review an explicit step
- Easy to enable for those who understand risks

**Rejected Alternatives:**
- Environment variable flag: Too easy to set without understanding
- Confirmation prompt: Could be automated/bypassed
- Separate "production mode": Adds complexity, users might run wrong mode
- Testnet/sandbox: Polymarket doesn't offer testnet for prediction markets

**Implementation:**
- agents/application/trade.py: Line 59-61

**Revisit If / Kill Criteria:**
- Polymarket offers a testnet/sandbox environment
- Regulatory landscape changes requiring different safety mechanism
- Community consensus on better safety pattern

---

## D-003: Ephemeral Local RAG Databases
**Date:** 2024-01-01 (project inception)
**Status:** ACTIVE

**Context:**
- Prediction markets change rapidly (odds, new markets, events close)
- Stale embeddings could lead to bad trading decisions
- Need to balance freshness vs. setup time

**Decision:**
- Delete local vector databases (`local_db_events/`, `local_db_markets/`) before each trading run
- Force re-fetch and re-embed market data every time

**Rationale:**
- Guarantees fresh data for trading decisions
- Simple implementation (no cache invalidation logic needed)
- Prediction markets are time-sensitive - stale data is dangerous
- ChromaDB rebuild is fast enough for typical use

**Rejected Alternatives:**
- Timestamp-based invalidation: Complex, error-prone, needs careful testing
- Incremental updates: Hard to detect what changed in markets
- Long-lived database: Risk of trading on outdated information
- No local RAG at all: Loses semantic search benefits

**Implementation:**
- agents/application/trade.py: Lines 17-25 (`clear_local_dbs()`)

**Revisit If / Kill Criteria:**
- Database rebuild becomes too slow (>30 seconds)
- Market data stabilizes (unlikely for prediction markets)
- Need for historical analysis across runs
- ChromaDB incremental update API becomes reliable

---

## D-004: LangChain + ChromaDB for RAG
**Date:** 2024-01-01 (project inception)
**Status:** ACTIVE

**Context:**
- Need semantic search over hundreds of markets/events
- Want easy integration with OpenAI embeddings
- Must work locally (no external vector DB service)

**Decision:**
- Use LangChain's RAG abstractions
- ChromaDB as the vector database backend
- OpenAI's text-embedding-3-small for embeddings

**Rationale:**
- LangChain provides high-level RAG patterns
- ChromaDB is lightweight, works locally, easy setup
- text-embedding-3-small is cost-effective and fast
- Good documentation and community support

**Rejected Alternatives:**
- Pinecone/Weaviate: Requires external service, added cost
- FAISS: More complex setup, less convenient API
- Larger embedding models (text-embedding-3-large): Higher cost, minimal benefit
- Local embedding models: Slower, quality concerns

**Implementation:**
- agents/connectors/chroma.py
- requirements.txt: Lines 18-19, 70-75

**Revisit If / Kill Criteria:**
- ChromaDB performance degrades with scale
- Need for multi-user/distributed vector DB
- OpenAI embedding costs become prohibitive
- Better local embedding models emerge

---

## D-005: Token Chunking Strategy
**Date:** 2024-01-01 (project inception, fixed in PR #23)
**Status:** ACTIVE

**Context:**
- LLMs have token limits (15k for gpt-3.5-turbo-16k, 95k for gpt-4)
- Polymarket can have hundreds of markets/events
- Need to handle large context without hitting limits

**Decision:**
- Estimate tokens using 4 chars = 1 token heuristic
- Automatically chunk market/event data when exceeding 80% of limit
- Process chunks sequentially, combine results
- Set model-specific limits in `Executor.__init__()`

**Rationale:**
- Simple estimation works well enough (rough but fast)
- 80% threshold leaves room for system/user messages
- Sequential processing is simpler than parallel+merge
- Model-specific handling allows upgrading to bigger models easily

**Rejected Alternatives:**
- Exact tokenization (tiktoken): Slower, overkill for estimation
- No chunking: Fails on large datasets
- Parallel chunk processing: Complex aggregation logic
- Filter aggressively upfront: Might miss important markets
- Always use largest model: Cost prohibitive

**Implementation:**
- agents/application/executor.py: Lines 32-35, 63-82, 84-115
- Fixed overflow issue in PR #23

**Revisit If / Kill Criteria:**
- Token limits increase dramatically (>200k)
- Chunking causes quality degradation in analysis
- Parallel processing becomes necessary for speed
- Better estimation methods available

---

## D-006: Typer for CLI Framework
**Date:** 2024-01-01 (project inception)
**Status:** ACTIVE

**Context:**
- Need user-friendly CLI for market queries, RAG operations, trading
- Want type hints and automatic help generation
- Must be easy to extend with new commands

**Decision:**
- Use Typer (from same author as FastAPI)
- Define commands as decorated functions
- Use type hints for automatic argument parsing

**Rationale:**
- Typer auto-generates help from docstrings and type hints
- Type safety reduces CLI argument bugs
- FastAPI-like DX is familiar and productive
- Less boilerplate than argparse or click

**Rejected Alternatives:**
- argparse: Too much boilerplate, no type hints
- click: Good but Typer is more modern/ergonomic
- Fire: Too magical, less explicit
- Custom parsing: Reinventing the wheel

**Implementation:**
- scripts/python/cli.py
- requirements.txt: Line 155

**Revisit If / Kill Criteria:**
- Need for interactive CLI (not just commands)
- Typer limitations with complex argument patterns
- Migration to web UI makes CLI secondary

---

## D-007: Black for Code Formatting
**Date:** 2024-01-01 (project inception)
**Status:** ACTIVE

**Context:**
- Need consistent code style across contributors
- Want to avoid style bikeshedding in PRs
- Pre-commit hooks required for contributions (per README)

**Decision:**
- Use Black (opinionated formatter, no config needed)
- Enforce via pre-commit hooks
- Python 3.9 language version

**Rationale:**
- Black is uncompromising - no style debates
- Community standard for Python formatting
- pre-commit integration is seamless
- Zero configuration needed

**Rejected Alternatives:**
- autopep8/yapf: More configurable but leads to debates
- Manual style guide: Not enforced, inconsistent
- Ruff: Good but Black is more established (could revisit)

**Implementation:**
- .pre-commit-config.yaml
- README.md: Line 176

**Revisit If / Kill Criteria:**
- Ruff formatter becomes stable and faster
- Need for more style customization
- Black development stalls
