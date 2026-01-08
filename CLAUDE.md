# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT!
GLOBAL CONSTRAINTS (always apply):

1. No narrative collapse
   - Do NOT compress uncertainty into a single explanation.
   - Enumerate multiple plausible hypotheses before evaluating any of them.

2. No unjustified causality
   - Do NOT use causal language (“because,” “drives,” “leads to”) unless you explicitly state:
     a) whether the relationship is causal or correlational
     b) at least one alternative explanation.

3. Conditional reasoning only
   - Do NOT recommend a single “best” strategy.
   - Frame guidance as conditional decision trees:
       IF condition A is true → action X
       IF condition B is true → action Y
       IF conditions cannot be determined → state “insufficient data”.

4. Explicit uncertainty is mandatory
   - For each major claim:
       - state what would falsify it
       - rate confidence (0–100%)
       - note whether required data is missing.

5. Bias awareness
   - Assume survivorship bias, selection effects, and hindsight bias are present.
   - For every observed pattern, explain how it could be an artifact of these biases.

6. Role constraint
   - Act as a skeptical peer reviewer, not a coach, consultant, or cheerleader.
   - Your default stance is to reject weak explanations.

OUTPUT STRUCTURE (unless explicitly overridden by the user):

A. Hypothesis enumeration (no evaluation)
B. Evidence required to discriminate between hypotheses
C. Conditional implications (no prescriptions)
D. Failure modes and misattribution risks
E. Confidence assessment & unknowns

## Project Overview

Polymarket Agents is a developer framework for building AI agents that autonomously trade on Polymarket prediction markets. The system integrates with the Polymarket API, uses RAG (Retrieval-Augmented Generation) for market analysis, and leverages LLMs for decision-making.

**Python Version**: 3.9

**Terms of Service**: US persons and persons from certain jurisdictions are prohibited from trading on Polymarket (see polymarket.com/tos).

## Development Setup

### Environment Setup
```bash
# Create and activate virtual environment
virtualenv --python=python3.9 .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate    # On Windows

# Install dependencies
pip install -r requirements.txt

# Set PYTHONPATH when running outside docker
export PYTHONPATH="."
```

### Required Environment Variables
Create a `.env` file with:
- `POLYGON_WALLET_PRIVATE_KEY`: Your Polygon wallet private key
- `OPENAI_API_KEY`: OpenAI API key for LLM operations
- `TAVILY_API_KEY`: (Optional) Tavily API for web search
- `NEWSAPI_API_KEY`: (Optional) NewsAPI for news retrieval

### Docker Setup
```bash
# Build Docker image
./scripts/bash/build-docker.sh

# Run development container
./scripts/bash/run-docker-dev.sh
```

## Common Commands

### CLI Commands
The primary interface is `scripts/python/cli.py` using Typer:

```bash
# Get markets from Polymarket
python scripts/python/cli.py get-all-markets --limit 10 --sort-by spread

# Get events from Polymarket
python scripts/python/cli.py get-all-events --limit 5 --sort-by number_of_markets

# Get relevant news articles
python scripts/python/cli.py get-relevant-news "election,politics"

# Create local RAG database for markets
python scripts/python/cli.py create-local-markets-rag ./local_db_markets

# Query local RAG database
python scripts/python/cli.py query-local-markets-rag ./local_db_markets "crypto markets"

# Ask superforecaster about a trade
python scripts/python/cli.py ask-superforecaster "2024 Election" "Will X win?" "yes"

# Ask LLM a question
python scripts/python/cli.py ask-llm "What are the best markets to trade?"

# Ask LLM with current market context
python scripts/python/cli.py ask-polymarket-llm "Which markets are trending?"

# Run autonomous trader (WARNING: Review TOS first)
python scripts/python/cli.py run-autonomous-trader
```

### Running the Autonomous Trader
```bash
# Execute trades autonomously (DISABLED by default in code)
python agents/application/trade.py
```

**Note**: Trade execution is commented out in `trade.py` line 60. You must uncomment and review TOS before enabling.

### Testing
```bash
# Run tests
python tests/test.py
```

### Code Quality
```bash
# Initialize pre-commit hooks (required for contributions)
pre-commit install

# Run black formatter manually
black agents/ scripts/ tests/
```

## Architecture Overview

### Core Components

**1. Polymarket Integration Layer** (`agents/polymarket/`)
- `polymarket.py`: Main Polymarket class that handles API authentication, market/event data retrieval, and trade execution via the CLOB (Central Limit Order Book). Manages Web3 interactions with Polygon network, USDC approvals, and order signing.
- `gamma.py`: GammaMarketClient interfaces with Gamma API to fetch and parse market and event metadata using Pydantic models.

**2. Data Connectors** (`agents/connectors/`)
- `chroma.py`: PolymarketRAG manages local vector databases using ChromaDB and OpenAI embeddings for semantic search over markets and events.
- `news.py`: News class integrates with NewsAPI to retrieve relevant articles based on market keywords.
- `search.py`: Web search integration (likely using Tavily).

**3. Application Layer** (`agents/application/`)
- `trade.py`: Trader class orchestrates the full autonomous trading pipeline:
  1. Clear local databases
  2. Fetch all tradeable events
  3. Filter events using RAG
  4. Map events to markets
  5. Filter markets
  6. Calculate best trade
  7. Execute (when enabled)

- `executor.py`: Executor class handles LLM interactions for:
  - Market analysis and forecasting
  - Token limit management (chunks large requests)
  - Superforecaster-style predictions
  - Polymarket-specific queries with market context

- `prompts.py`: Prompter class centralizes all prompt templates for different agent personas (trader, analyst, superforecaster).

- `creator.py`: Market creation functionality.

- `cron.py`: Scheduled job management.

**4. Utilities** (`agents/utils/`)
- `objects.py`: Pydantic data models for type-safe representations of trades, markets, events, rewards, tags, etc. These models handle API response parsing and validation.
- `utils.py`: Shared utility functions.

### Data Flow for Autonomous Trading

1. **Event Discovery**: `Polymarket.get_all_tradeable_events()` fetches events from Gamma API
2. **RAG Filtering**: `Executor.filter_events_with_rag()` uses vector similarity to find relevant events
3. **Market Mapping**: `Executor.map_filtered_events_to_markets()` converts events to tradeable markets
4. **Market Filtering**: `Executor.filter_markets()` applies trading criteria (spread, volume, etc.)
5. **Trade Calculation**: `Executor.source_best_trade()` determines optimal position and size
6. **Execution**: `Polymarket.execute_market_order()` submits order to CLOB (commented out by default)

### Key Technical Details

**Blockchain Integration**:
- Network: Polygon (chain_id: 137)
- Exchange addresses: CTF Exchange (0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e), Neg Risk Exchange (0xC5d563A36AE78145C45a50134d48A1215220f80a)
- Contracts: USDC (ERC20) and CTF (ERC1155) require approval before trading

**LLM Token Management**:
- Executor handles token limits for gpt-3.5-turbo-16k (15K) and gpt-4-1106-preview (95K)
- Automatically chunks large market/event datasets when exceeding limits
- Rough estimate: 4 characters ≈ 1 token

**RAG Implementation**:
- Uses OpenAI's text-embedding-3-small model
- ChromaDB for local vector storage
- Persists to `local_db_events/` and `local_db_markets/` directories

**Order Building**:
- Uses py-clob-client for CLOB API interactions
- py-order-utils for order construction and signing
- Supports market orders and limit orders via OrderBuilder

## API Clients and Dependencies

- **py-clob-client**: Polymarket CLOB client library
- **py-order-utils**: Order signing and construction utilities
- **LangChain**: Framework for LLM applications and RAG
- **ChromaDB**: Vector database for embeddings
- **Web3.py**: Ethereum/Polygon blockchain interactions
- **Pydantic**: Data validation and schema definitions
- **Typer**: CLI framework

## Important Notes

1. **Trade Execution Safety**: All actual trade execution is commented out by default. Review terms of service and test thoroughly before enabling.

2. **Local Database Cleanup**: The `Trader.pre_trade_logic()` deletes local RAG databases before each run to ensure fresh data.

3. **API Rate Limits**: Be mindful of rate limits for OpenAI, NewsAPI, and Polymarket APIs.

4. **Private Keys**: Never commit the `.env` file. The private key is used to sign orders and must be kept secure.

5. **Gas Fees**: All transactions on Polygon require MATIC for gas fees in addition to USDC for trading.

6. **Pre-commit Hooks**: Black formatter is enforced via pre-commit. Run `pre-commit install` before contributing.
