"""
CopyTrader Demo

This example demonstrates how to use the CopyTrader module.
It runs in "demo mode" with mocked execution for safe testing.
"""

import os
import time
from pathlib import Path
from agents.copytrader.config import CopyTraderConfig
from agents.copytrader.strategy import CopyTraderStrategy, SizingConfig
from agents.copytrader.ingest import create_ingestor
from agents.copytrader.tracking import PurchaseTracker
from agents.copytrader.health import run_health_check


def demo_mode():
    """Run copy trader in demo mode (no real execution)"""

    print("\n" + "=" * 70)
    print("COPYTRADER DEMO MODE")
    print("=" * 70)
    print("This demo shows the copy trading flow without real execution.")
    print("=" * 70 + "\n")

    # Configure from environment (or use defaults)
    config = CopyTraderConfig(
        allowed_traders={
            "0xd62531bc536bff72394fc5ef715525575787e809"  # Example trader
        },
        max_intent_size_usdc=100.0,
        max_intent_age_seconds=60,
    )

    sizing = SizingConfig(
        strategy="PERCENTAGE",
        base_size=10.0,  # Copy 10% of trader's orders
    )

    # Create tracking backend
    tracker = PurchaseTracker()

    print("✓ Configuration loaded:")
    print(f"  - Following {len(config.allowed_traders)} trader(s)")
    print(f"  - Max intent size: ${config.max_intent_size_usdc:.2f}")
    print(f"  - Sizing strategy: {sizing.strategy}")
    print(f"  - Copy size: {sizing.base_size}%\n")

    # Run health check (without Polymarket instance)
    print("Running health checks...")
    healthy = run_health_check(config, polymarket=None, tracker=tracker)

    if not healthy:
        print("\n⚠️  Some checks failed, but continuing in demo mode...\n")

    # Create ingestor (file mode)
    intent_file = Path("demo_intents.jsonl")
    print(f"📁 Watching for intents in: {intent_file}")
    print("   (TypeScript service would write to this file)\n")

    ingestor = create_ingestor(config, mode="file", filepath=intent_file)
    ingestor.start()

    # Create demo intent if file is empty
    if not intent_file.exists() or intent_file.stat().st_size == 0:
        print("📝 Creating demo intent...")
        from datetime import datetime
        import json

        demo_intent = {
            "intent_id": "demo-001",
            "timestamp": datetime.utcnow().isoformat(),
            "source_trader": "0xd62531bc536bff72394fc5ef715525575787e809",
            "market_id": "demo_market_001",
            "outcome": "YES",
            "side": "BUY",
            "size_usdc": 50.0,
            "metadata": {
                "trader_order_usd": 500.0,
                "best_ask": 0.65,
            },
        }

        with open(intent_file, "w") as f:
            f.write(json.dumps(demo_intent) + "\n")

        print(f"   Intent written to {intent_file}\n")

    # Process intents
    print("🔄 Processing intents (Ctrl+C to stop)...\n")

    try:
        check_count = 0
        while True:
            intent = ingestor.get_next_intent(timeout=1.0)

            if intent:
                print(f"\n📥 Intent received:")
                print(f"   ID: {intent.intent_id}")
                print(f"   Trader: {intent.source_trader[:16]}...")
                print(f"   Market: {intent.market_id}")
                print(f"   Side: {intent.side}")
                print(f"   Size: ${intent.size_usdc:.2f}")
                print(f"\n   ✓ Passed validation")
                print(f"   ℹ️  In production, this would execute via Polymarket")

                # Show stats
                stats = ingestor.get_stats()
                print(f"\n📊 Stats:")
                print(f"   Validated: {stats['validated_count']}")
                print(f"   Rejected: {stats['rejected_count']}")

            else:
                check_count += 1
                if check_count % 5 == 0:
                    print(f"⏳ Waiting for intents... ({check_count} checks)")

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Stopping...")
        ingestor.stop()
        print("✓ Demo complete\n")


if __name__ == "__main__":
    demo_mode()
