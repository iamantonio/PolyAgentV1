"""
Integration tests for CopyTrader.

Tests the full flow using recorded intent replay to ensure deterministic behavior.
"""

import json
import tempfile
from pathlib import Path
from datetime import datetime
from agents.copytrader.schema import TradeIntent
from agents.copytrader.config import CopyTraderConfig
from agents.copytrader.ingest import FileIngestor
from agents.copytrader.firewall import ValidationError
import time


class TestIntentReplay:
    """Test intent replay with recorded scenarios"""

    def create_intent_file(self, intents: list[dict], filepath: Path) -> None:
        """Write intents to a JSON lines file"""
        with open(filepath, "w") as f:
            for intent in intents:
                f.write(json.dumps(intent) + "\n")

    def test_replay_valid_intents(self):
        """Test replaying valid recorded intents"""
        # Create sample intents
        intents = [
            {
                "intent_id": "intent-001",
                "timestamp": datetime.utcnow().isoformat(),
                "source_trader": "0x" + "a" * 40,
                "market_id": "market_001",
                "outcome": "YES",
                "side": "BUY",
                "size_usdc": 50.0,
                "metadata": {
                    "trader_order_usd": 500.0,
                    "best_ask": 0.65,
                },
            },
            {
                "intent_id": "intent-002",
                "timestamp": datetime.utcnow().isoformat(),
                "source_trader": "0x" + "a" * 40,
                "market_id": "market_002",
                "outcome": "NO",
                "side": "BUY",
                "size_usdc": 25.0,
                "metadata": {
                    "trader_order_usd": 250.0,
                    "best_ask": 0.45,
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            intent_file = Path(tmpdir) / "intents.jsonl"
            self.create_intent_file(intents, intent_file)

            # Configure ingestor
            config = CopyTraderConfig(
                allowed_traders={"0x" + "a" * 40},
                max_intent_size_usdc=100.0,
            )

            ingestor = FileIngestor(config, intent_file)
            ingestor.start()

            # Wait for ingestion
            time.sleep(0.5)

            # Should receive both intents
            intent1 = ingestor.get_next_intent(timeout=1.0)
            intent2 = ingestor.get_next_intent(timeout=1.0)
            intent3 = ingestor.get_next_intent(timeout=0.1)  # Should be None

            assert intent1 is not None
            assert intent1.intent_id == "intent-001"
            assert intent1.size_usdc == 50.0

            assert intent2 is not None
            assert intent2.intent_id == "intent-002"
            assert intent2.size_usdc == 25.0

            assert intent3 is None  # No more intents

            # Check stats
            stats = ingestor.get_stats()
            assert stats["validated_count"] == 2
            assert stats["rejected_count"] == 0

            ingestor.stop()

    def test_replay_with_rejections(self):
        """Test replay with some intents that should be rejected"""
        intents = [
            # Valid intent
            {
                "intent_id": "intent-valid",
                "timestamp": datetime.utcnow().isoformat(),
                "source_trader": "0x" + "a" * 40,
                "market_id": "market_001",
                "outcome": "YES",
                "side": "BUY",
                "size_usdc": 50.0,
                "metadata": {},
            },
            # Oversized intent (should be rejected)
            {
                "intent_id": "intent-oversized",
                "timestamp": datetime.utcnow().isoformat(),
                "source_trader": "0x" + "a" * 40,
                "market_id": "market_002",
                "outcome": "YES",
                "side": "BUY",
                "size_usdc": 500.0,  # Over limit
                "metadata": {},
            },
            # Unauthorized trader (should be rejected)
            {
                "intent_id": "intent-unauthorized",
                "timestamp": datetime.utcnow().isoformat(),
                "source_trader": "0x" + "b" * 40,  # Not in allowlist
                "market_id": "market_003",
                "outcome": "YES",
                "side": "BUY",
                "size_usdc": 30.0,
                "metadata": {},
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            intent_file = Path(tmpdir) / "intents.jsonl"
            self.create_intent_file(intents, intent_file)

            # Configure with strict limits
            config = CopyTraderConfig(
                allowed_traders={"0x" + "a" * 40},
                max_intent_size_usdc=100.0,
            )

            ingestor = FileIngestor(config, intent_file)
            ingestor.start()

            # Wait for ingestion
            time.sleep(0.5)

            # Should only receive the valid intent
            intent1 = ingestor.get_next_intent(timeout=1.0)
            intent2 = ingestor.get_next_intent(timeout=0.1)

            assert intent1 is not None
            assert intent1.intent_id == "intent-valid"
            assert intent2 is None

            # Check stats: 1 valid, 2 rejected
            stats = ingestor.get_stats()
            assert stats["validated_count"] == 1
            assert stats["rejected_count"] == 2

            ingestor.stop()

    def test_deterministic_replay(self):
        """Test that replaying the same intents produces identical results"""
        intents = [
            {
                "intent_id": "intent-001",
                "timestamp": "2024-01-01T12:00:00",
                "source_trader": "0x" + "a" * 40,
                "market_id": "market_001",
                "outcome": "YES",
                "side": "BUY",
                "size_usdc": 50.0,
                "metadata": {},
            },
        ]

        config = CopyTraderConfig(allowed_traders={"0x" + "a" * 40})

        results = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmpdir:
                intent_file = Path(tmpdir) / "intents.jsonl"
                self.create_intent_file(intents, intent_file)

                ingestor = FileIngestor(config, intent_file)
                ingestor.start()
                time.sleep(0.5)

                intent = ingestor.get_next_intent(timeout=1.0)
                assert intent is not None
                results.append(intent.to_dict())

                ingestor.stop()

        # Both replays should produce identical results
        assert results[0] == results[1]

    def test_deduplication_across_replays(self):
        """Test that duplicate intent IDs are rejected"""
        intents = [
            {
                "intent_id": "duplicate-id",
                "timestamp": datetime.utcnow().isoformat(),
                "source_trader": "0x" + "a" * 40,
                "market_id": "market_001",
                "outcome": "YES",
                "side": "BUY",
                "size_usdc": 50.0,
                "metadata": {},
            },
            # Same intent_id (should be rejected)
            {
                "intent_id": "duplicate-id",
                "timestamp": datetime.utcnow().isoformat(),
                "source_trader": "0x" + "a" * 40,
                "market_id": "market_002",
                "outcome": "YES",
                "side": "BUY",
                "size_usdc": 30.0,
                "metadata": {},
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            intent_file = Path(tmpdir) / "intents.jsonl"
            self.create_intent_file(intents, intent_file)

            config = CopyTraderConfig(allowed_traders={"0x" + "a" * 40})

            ingestor = FileIngestor(config, intent_file)
            ingestor.start()
            time.sleep(0.5)

            # Should only get first intent
            intent1 = ingestor.get_next_intent(timeout=1.0)
            intent2 = ingestor.get_next_intent(timeout=0.1)

            assert intent1 is not None
            assert intent2 is None

            # Stats: 1 valid, 1 rejected (duplicate)
            stats = ingestor.get_stats()
            assert stats["validated_count"] == 1
            assert stats["rejected_count"] == 1

            ingestor.stop()
