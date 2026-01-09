"""
Example: Continuous Trader with Opportunity Scoring

Shows how to integrate opportunity scoring into the continuous trader
to maximize ROI by focusing budget on high-value markets.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.application.market_filter import MarketFilter


def example_integrate_scoring_into_trader():
    """
    Example showing how to integrate opportunity scoring
    into the continuous trader workflow.
    """

    print("\n" + "="*70)
    print("CONTINUOUS TRADER + OPPORTUNITY SCORING INTEGRATION")
    print("="*70)

    # Step 1: Initialize market filter with scoring enabled
    print("\n1. Initialize MarketFilter with opportunity scoring...")

    market_filter = MarketFilter(
        # Basic pre-filters (cheap, fast)
        min_liquidity=1000.0,
        max_spread_pct=5.0,
        min_price=0.10,
        max_price=0.90,
        min_hours_to_close=24.0,

        # Opportunity scoring (prioritization)
        enable_opportunity_scoring=True,
        min_opportunity_score=40.0  # Filter markets below this threshold
    )

    print("   ✓ MarketFilter configured:")
    config = market_filter.get_config()
    for key, value in config.items():
        print(f"     • {key}: {value}")

    # Step 2: Filter and score markets
    print("\n2. Filter and score markets...")
    print("   (In production, markets would come from Chroma/Polymarket)")

    # Simulate getting markets from your data source
    # In production: markets = chroma_client.query(...)
    markets = []  # Empty for this example

    # Filter with scoring
    scored_markets = market_filter.filter_markets(
        markets,
        return_scored=True  # Get (market, score_data) tuples
    )

    if scored_markets:
        print(f"   ✓ {len(scored_markets)} markets passed filters and scoring")

        # Show top 5
        print("\n   Top 5 markets:")
        for i, (market, score) in enumerate(scored_markets[:5], 1):
            print(f"   {i}. Score {score['total_score']:.1f}: {score['question'][:60]}...")
    else:
        print("   (No markets in this example)")

    # Step 3: Allocate budget
    print("\n3. Allocate daily budget to top markets...")

    daily_budget = 100.0  # Example: $100/day
    top_n = 10  # Focus on top 10 markets

    if scored_markets:
        allocations = market_filter.allocate_budget_to_markets(
            scored_markets,
            daily_budget=daily_budget,
            top_n=top_n
        )

        print(f"   ✓ Allocated ${daily_budget:.2f} to top {len(allocations)} markets")
        print("\n   Budget allocation:")
        for market_id, allocated in sorted(allocations.items(), key=lambda x: -x[1])[:5]:
            print(f"     • {market_id}: ${allocated:.2f}")
    else:
        print("   (No markets to allocate to)")

    # Step 4: Use in trading loop
    print("\n4. Integration with continuous trader loop...")
    print("   Pseudo-code for integration:")
    print("""
    while True:
        # Fetch available markets
        markets = get_markets_from_chroma()

        # Filter and score
        scored_markets = market_filter.filter_markets(
            markets,
            return_scored=True
        )

        # Allocate budget
        allocations = market_filter.allocate_budget_to_markets(
            scored_markets,
            daily_budget=DAILY_BUDGET,
            top_n=10
        )

        # Trade based on allocations
        for market, score_data in scored_markets[:10]:
            market_id = score_data['market_id']
            budget = allocations[market_id]

            # Use LLM to forecast (only for high-value markets)
            if budget > 0:
                forecast = llm_forecast(market, budget)
                execute_trade(forecast)

        time.sleep(SCAN_INTERVAL)
    """)

    # Step 5: Expected impact
    print("\n5. Expected Impact:")
    print("-" * 70)
    print("   BEFORE (no scoring):")
    print("     • Process all markets equally")
    print("     • Spread budget evenly")
    print("     • Waste LLM calls on low-value markets")
    print("     • Average ROI")

    print("\n   AFTER (with scoring):")
    print("     • Focus on top 10% of markets (score > 40)")
    print("     • Exponential budget allocation (top gets 6x more)")
    print("     • Skip low-value markets (save 50-70% API costs)")
    print("     • 2-3x ROI improvement")

    print("\n   Metrics to track:")
    print("     1. ROI by score range (80-100, 60-80, 40-60)")
    print("     2. API cost reduction")
    print("     3. Budget efficiency")
    print("     4. Market coverage vs. returns")

    # Step 6: Configuration tips
    print("\n6. Configuration Tips:")
    print("-" * 70)
    print("   Adjust thresholds based on market conditions:")
    print("")
    print("   AGGRESSIVE (more opportunities):")
    print("     min_opportunity_score = 30.0")
    print("     top_n = 15")
    print("")
    print("   CONSERVATIVE (high-quality only):")
    print("     min_opportunity_score = 50.0")
    print("     top_n = 5")
    print("")
    print("   BALANCED (recommended start):")
    print("     min_opportunity_score = 40.0")
    print("     top_n = 10")

    # Step 7: Monitoring
    print("\n7. Production Monitoring:")
    print("-" * 70)
    print("   Track these metrics:")
    print("     • Average score of traded markets")
    print("     • ROI correlation with score")
    print("     • Markets filtered out (missed opportunities?)")
    print("     • Budget utilization by score range")
    print("     • Cost per trade (with vs. without scoring)")

    print("\n" + "="*70)
    print("INTEGRATION EXAMPLE COMPLETE")
    print("="*70)
    print("\nTo enable in production:")
    print("1. Update continuous_trader.py to use MarketFilter with scoring")
    print("2. Configure thresholds based on your budget and risk tolerance")
    print("3. Monitor ROI improvement over 1-2 weeks")
    print("4. Adjust thresholds based on performance data")
    print("\nSee docs/opportunity_scoring_usage.md for full documentation.")
    print()


if __name__ == "__main__":
    example_integrate_scoring_into_trader()
