"""
CopyTrader module for Polymarket Agents.

This module enables following trader addresses by consuming TradeIntent messages
from an external signal generator. The signal generator is sandboxed and never
holds private keys - it only reads public data and emits trade intents.

Security model:
- External service (TypeScript) generates trade intents (public data only)
- Python service validates and executes intents (holds keys, signs orders)
- Strict validation firewall prevents unauthorized trades
"""

from agents.copytrader.schema import TradeIntent, TradeIntentMetadata
from agents.copytrader.ingest import IntentIngestor

__all__ = ["TradeIntent", "TradeIntentMetadata", "IntentIngestor"]
