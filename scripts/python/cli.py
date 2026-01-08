import typer
from devtools import pprint

from agents.polymarket.polymarket import Polymarket
from agents.connectors.chroma import PolymarketRAG
from agents.connectors.news import News
from agents.application.trade import Trader
from agents.application.executor import Executor
from agents.application.creator import Creator
from agents.copytrader.executor import CopyTrader
from agents.copytrader.risk_kernel import RiskKernel
from agents.copytrader.allowlist import AllowlistService
from agents.copytrader.position_tracker import PositionTracker
from agents.copytrader.alerts import AlertService, AlertConfig
from agents.copytrader.storage import CopyTraderDB
from decimal import Decimal
import os

app = typer.Typer()
polymarket = Polymarket()
newsapi_client = News()
polymarket_rag = PolymarketRAG()


@app.command()
def get_all_markets(limit: int = 5, sort_by: str = "spread") -> None:
    """
    Query Polymarket's markets
    """
    print(f"limit: int = {limit}, sort_by: str = {sort_by}")
    markets = polymarket.get_all_markets()
    markets = polymarket.filter_markets_for_trading(markets)
    if sort_by == "spread":
        markets = sorted(markets, key=lambda x: x.spread, reverse=True)
    markets = markets[:limit]
    pprint(markets)


@app.command()
def get_relevant_news(keywords: str) -> None:
    """
    Use NewsAPI to query the internet
    """
    articles = newsapi_client.get_articles_for_cli_keywords(keywords)
    pprint(articles)


@app.command()
def get_all_events(limit: int = 5, sort_by: str = "number_of_markets") -> None:
    """
    Query Polymarket's events
    """
    print(f"limit: int = {limit}, sort_by: str = {sort_by}")
    events = polymarket.get_all_events()
    events = polymarket.filter_events_for_trading(events)
    if sort_by == "number_of_markets":
        events = sorted(events, key=lambda x: len(x.markets), reverse=True)
    events = events[:limit]
    pprint(events)


@app.command()
def create_local_markets_rag(local_directory: str) -> None:
    """
    Create a local markets database for RAG
    """
    polymarket_rag.create_local_markets_rag(local_directory=local_directory)


@app.command()
def query_local_markets_rag(vector_db_directory: str, query: str) -> None:
    """
    RAG over a local database of Polymarket's events
    """
    response = polymarket_rag.query_local_markets_rag(
        local_directory=vector_db_directory, query=query
    )
    pprint(response)


@app.command()
def ask_superforecaster(event_title: str, market_question: str, outcome: str) -> None:
    """
    Ask a superforecaster about a trade
    """
    print(
        f"event: str = {event_title}, question: str = {market_question}, outcome (usually yes or no): str = {outcome}"
    )
    executor = Executor()
    response = executor.get_superforecast(
        event_title=event_title, market_question=market_question, outcome=outcome
    )
    print(f"Response:{response}")


@app.command()
def create_market() -> None:
    """
    Format a request to create a market on Polymarket
    """
    c = Creator()
    market_description = c.one_best_market()
    print(f"market_description: str = {market_description}")


@app.command()
def ask_llm(user_input: str) -> None:
    """
    Ask a question to the LLM and get a response.
    """
    executor = Executor()
    response = executor.get_llm_response(user_input)
    print(f"LLM Response: {response}")


@app.command()
def ask_polymarket_llm(user_input: str) -> None:
    """
    What types of markets do you want trade?
    """
    executor = Executor()
    response = executor.get_polymarket_llm(user_input=user_input)
    print(f"LLM + current markets&events response: {response}")


@app.command()
def run_autonomous_trader() -> None:
    """
    Let an autonomous system trade for you.
    """
    trader = Trader()
    trader.one_best_trade()


@app.command()
def run_copytrader(
    dry_run: bool = True,
    db_path: str = "./copytrader_v1.db",
    starting_capital: float = 1000.0,
) -> None:
    """
    Run CopyTrader bot (Phase 0 + Phase 1).

    Args:
        dry_run: If True, skip actual execution (default: True for safety)
        db_path: Path to SQLite database
        starting_capital: Starting capital in dollars (default: $1000)
    """
    print("=" * 60)
    print("CopyTrader v1 - Phase 0 + Phase 1")
    print("=" * 60)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE TRADING'}")
    print(f"Starting capital: ${starting_capital:.2f}")
    print(f"Database: {db_path}")
    print("=" * 60)

    # Initialize components
    print("\nInitializing components...")

    # Database
    db = CopyTraderDB(db_path)
    print("✓ Database initialized")

    # Risk kernel with v1 guardrails
    risk_kernel = RiskKernel(
        starting_capital=Decimal(str(starting_capital)),
        daily_stop_pct=Decimal("-5.0"),  # -5% daily stop
        hard_kill_pct=Decimal("-20.0"),  # -20% hard kill
        per_trade_cap_pct=Decimal("3.0"),  # 3% per trade cap
        max_positions=3,  # Max 3 positions
        anomalous_loss_pct=Decimal("-5.0"),  # >5% single trade loss = kill
    )
    print("✓ Risk kernel initialized")

    # Position tracker
    tracker = PositionTracker(db, Decimal(str(starting_capital)))
    print("✓ Position tracker initialized")

    # Allowlist service
    allowlist = AllowlistService()
    try:
        allowlist.refresh_politics_markets()
        print(f"✓ Allowlist initialized ({len(allowlist.get_allowlist())} markets)")
    except Exception as e:
        print(f"✗ Allowlist refresh failed: {e}")
        print("Bot will fail-closed (no trades allowed)")

    # Alert service
    alert_config = AlertConfig(
        enabled=True,
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )
    alerts = AlertService(alert_config)
    print("✓ Alert service initialized")

    # Polymarket client
    polymarket_client = Polymarket()
    print("✓ Polymarket client initialized")

    # CopyTrader executor
    copytrader = CopyTrader(
        polymarket=polymarket_client,
        risk_kernel=risk_kernel,
        allowlist=allowlist,
        tracker=tracker,
        alerts=alerts,
        dry_run=dry_run,
    )
    print("✓ CopyTrader executor initialized")

    # Get status
    print("\n" + "=" * 60)
    print("Bot Status:")
    print("=" * 60)
    status = copytrader.get_status()
    pprint(status)

    print("\n" + "=" * 60)
    print("CopyTrader initialized and ready.")
    print("=" * 60)
    print("\nNOTE: This command initializes the bot.")
    print("To process trade intents, you need to:")
    print("1. Implement intent ingestion (e.g., from external signal source)")
    print("2. Call copytrader.process_intent(intent) for each trade signal")
    print("\nSee docs/CopyTraderV1.md for full setup and usage.")


if __name__ == "__main__":
    app()
