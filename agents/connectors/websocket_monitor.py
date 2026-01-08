"""
Polymarket WebSocket Price Monitor

Real-time price monitoring using Polymarket's WebSocket API.
Enables sub-second arbitrage detection and opportunity alerts.

Based on Polymarket CLOB WebSocket and RTDS documentation.
"""

import asyncio
import json
from typing import Callable, Dict, List, Optional, Set
from datetime import datetime
import websocket


class PolymarketWebSocketMonitor:
    """
    Real-time price monitoring via Polymarket WebSocket.

    Subscribes to market updates and triggers callbacks when prices change.
    Essential for competitive arbitrage bot performance.
    """

    def __init__(
        self,
        on_price_update: Optional[Callable] = None,
        ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market",
    ):
        """
        Initialize WebSocket monitor.

        Args:
            on_price_update: Callback function(market_id, prices) called on updates
            ws_url: WebSocket endpoint URL
        """
        self.ws_url = ws_url
        self.on_price_update = on_price_update
        self.subscribed_markets: Set[str] = set()
        self.ws = None
        self.running = False

    def subscribe_market(self, market_id: str):
        """
        Subscribe to price updates for a specific market.

        Args:
            market_id: Polymarket market ID to monitor
        """
        self.subscribed_markets.add(market_id)

        if self.ws and self.ws.sock and self.ws.sock.connected:
            # Send subscription message
            subscribe_msg = {
                "type": "subscribe",
                "market": market_id,
                "assets_ids": []  # Subscribe to all assets in market
            }
            self.ws.send(json.dumps(subscribe_msg))
            print(f"  📡 Subscribed to market {market_id}")

    def unsubscribe_market(self, market_id: str):
        """Unsubscribe from market updates."""
        if market_id in self.subscribed_markets:
            self.subscribed_markets.remove(market_id)

            if self.ws and self.ws.sock and self.ws.sock.connected:
                unsubscribe_msg = {
                    "type": "unsubscribe",
                    "market": market_id
                }
                self.ws.send(json.dumps(unsubscribe_msg))
                print(f"  📡 Unsubscribed from market {market_id}")

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "price_change":
                # Price update message
                market_id = data.get("market")
                price_changes = data.get("price_changes", [])

                # Extract prices for each outcome
                prices = {}
                for change in price_changes:
                    asset_id = change.get("asset_id")
                    best_bid = float(change.get("best_bid", 0))
                    best_ask = float(change.get("best_ask", 0))
                    mid_price = (best_bid + best_ask) / 2

                    prices[asset_id] = {
                        "bid": best_bid,
                        "ask": best_ask,
                        "mid": mid_price
                    }

                # Trigger callback
                if self.on_price_update and market_id in self.subscribed_markets:
                    self.on_price_update(market_id, prices)

            elif msg_type == "last_trade_price":
                # Last trade update
                market_id = data.get("market")
                asset_id = data.get("asset_id")
                price = float(data.get("price", 0))

                if self.on_price_update and market_id in self.subscribed_markets:
                    self.on_price_update(market_id, {asset_id: {"last": price}})

        except Exception as e:
            print(f"  ⚠️ WebSocket message error: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        print(f"  ❌ WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        print(f"  🔌 WebSocket closed: {close_msg}")
        self.running = False

    def _on_open(self, ws):
        """Handle WebSocket connection open."""
        print(f"  ✅ WebSocket connected to {self.ws_url}")

        # Subscribe to all markets
        for market_id in self.subscribed_markets:
            subscribe_msg = {
                "type": "subscribe",
                "market": market_id,
                "assets_ids": []
            }
            ws.send(json.dumps(subscribe_msg))
            print(f"  📡 Subscribed to market {market_id}")

    def start(self):
        """
        Start WebSocket connection and monitoring.

        Runs in blocking mode - use asyncio or threading for background operation.
        """
        self.running = True

        # Create WebSocket connection
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

        # Run forever (blocking)
        print(f"  🚀 Starting WebSocket monitor...")
        self.ws.run_forever()

    def stop(self):
        """Stop WebSocket monitoring."""
        self.running = False
        if self.ws:
            self.ws.close()
        print(f"  ⏹️ WebSocket monitor stopped")


class ArbitrageScanner:
    """
    Continuous arbitrage scanner using WebSocket price feed.

    Monitors multiple markets simultaneously for arbitrage opportunities.
    """

    def __init__(self, arbitrage_detector, on_opportunity_found: Optional[Callable] = None):
        """
        Initialize arbitrage scanner.

        Args:
            arbitrage_detector: ArbitrageDetector instance
            on_opportunity_found: Callback(opportunity) when arbitrage found
        """
        self.detector = arbitrage_detector
        self.on_opportunity_found = on_opportunity_found
        self.market_prices: Dict[str, Dict] = {}  # Cache of latest prices
        self.monitor = PolymarketWebSocketMonitor(on_price_update=self._handle_price_update)

    def _handle_price_update(self, market_id: str, prices: Dict):
        """Handle price update from WebSocket."""
        # Update price cache
        self.market_prices[market_id] = prices

        # TODO: Get market metadata (question, outcome names)
        # For now, placeholder
        question = f"Market {market_id}"

        # Extract mid prices for arbitrage check
        outcome_prices = {}
        for asset_id, price_data in prices.items():
            mid_price = price_data.get("mid", price_data.get("last", 0))
            outcome_prices[asset_id] = mid_price

        # Scan for arbitrage
        opportunities = self.detector.scan_market(market_id, question, outcome_prices)

        # Alert on opportunities
        for opp in opportunities:
            if self.on_opportunity_found:
                self.on_opportunity_found(opp)

    def add_market(self, market_id: str):
        """Add market to monitoring."""
        self.monitor.subscribe_market(market_id)

    def remove_market(self, market_id: str):
        """Remove market from monitoring."""
        self.monitor.unsubscribe_market(market_id)

    def start(self):
        """Start continuous scanning."""
        self.monitor.start()

    def stop(self):
        """Stop scanning."""
        self.monitor.stop()
