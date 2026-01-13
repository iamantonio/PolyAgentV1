"""
Crypto Edge Detector

Combines multiple signals to identify tradeable edge in crypto markets:
1. Funding Rate - Contrarian signal from perpetual futures
2. Order Book Imbalance - Buy/sell pressure from Binance
3. Social Sentiment - LunarCrush data
4. Regime Detection - Skip unfavorable market conditions
5. Price Edge - Only trade mispriced markets

Research shows 55-62% accuracy is achievable with multi-signal ensemble.
"""

import os
import time
import asyncio
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
from decimal import Decimal
import httpx
from dotenv import load_dotenv

# Import existing connectors
try:
    from agents.connectors.lunarcrush import LunarCrush
except ImportError:
    LunarCrush = None


class CryptoEdgeDetector:
    """
    Multi-signal crypto edge detection system.

    Combines:
    - Funding rates (contrarian)
    - Order book imbalance (momentum)
    - Social sentiment (LunarCrush)
    - Regime filtering

    Target: 55-62% accuracy on 1-hour crypto markets
    """

    # Supported tokens for edge detection
    SUPPORTED_TOKENS = {
        'bitcoin': {'symbol': 'BTC', 'binance': 'BTCUSDT'},
        'ethereum': {'symbol': 'ETH', 'binance': 'ETHUSDT'},
        'solana': {'symbol': 'SOL', 'binance': 'SOLUSDT'},
        'ripple': {'symbol': 'XRP', 'binance': 'XRPUSDT'},
        'dogecoin': {'symbol': 'DOGE', 'binance': 'DOGEUSDT'},
        'cardano': {'symbol': 'ADA', 'binance': 'ADAUSDT'},
        'avalanche': {'symbol': 'AVAX', 'binance': 'AVAXUSDT'},
        'polygon': {'symbol': 'MATIC', 'binance': 'MATICUSDT'},
        'chainlink': {'symbol': 'LINK', 'binance': 'LINKUSDT'},
        'litecoin': {'symbol': 'LTC', 'binance': 'LTCUSDT'},
    }

    def __init__(self):
        load_dotenv()

        # Initialize LunarCrush if available
        self.lunarcrush = None
        if LunarCrush:
            try:
                self.lunarcrush = LunarCrush()
                print("  ✅ LunarCrush connector initialized")
            except Exception as e:
                print(f"  ⚠️ LunarCrush initialization failed: {e}")

        # Cache for API responses
        self._cache = {}
        self._cache_ttl = timedelta(minutes=2)  # Short TTL for real-time data

        # Rate limiting
        self._last_binance_request = 0
        self._binance_rate_limit = 0.1  # 10 requests/second max

    # =========================================================================
    # SIGNAL 1: Funding Rate (Contrarian)
    # =========================================================================

    def get_funding_rate(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get perpetual futures funding rate from Binance.

        Funding rate is paid between longs and shorts every 8 hours.
        - Positive funding = longs pay shorts = market is long-heavy = BEARISH signal
        - Negative funding = shorts pay longs = market is short-heavy = BULLISH signal

        Args:
            token: Token name (e.g., "bitcoin", "ethereum")

        Returns:
            Dict with funding_rate, signal, and confidence
        """
        token_info = self.SUPPORTED_TOKENS.get(token.lower())
        if not token_info:
            return None

        symbol = token_info['binance']
        cache_key = f"funding_{symbol}"

        # Check cache
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if datetime.now() - entry['timestamp'] < self._cache_ttl:
                return entry['data']

        try:
            # Binance Futures API - no auth needed for public data
            url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1"

            self._wait_for_binance_rate_limit()
            response = httpx.get(url, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                if data:
                    funding_rate = float(data[0]['fundingRate'])

                    # Interpret the signal
                    signal = None
                    confidence = 0.5

                    # Extreme funding rates are contrarian signals
                    if funding_rate > 0.0005:  # 0.05% - moderately long-heavy
                        signal = "DOWN"
                        confidence = 0.55
                    elif funding_rate > 0.001:  # 0.1% - very long-heavy
                        signal = "DOWN"
                        confidence = 0.60
                    elif funding_rate > 0.002:  # 0.2% - extremely long-heavy
                        signal = "DOWN"
                        confidence = 0.65
                    elif funding_rate < -0.0005:  # -0.05% - moderately short-heavy
                        signal = "UP"
                        confidence = 0.55
                    elif funding_rate < -0.001:  # -0.1% - very short-heavy
                        signal = "UP"
                        confidence = 0.60
                    elif funding_rate < -0.002:  # -0.2% - extremely short-heavy
                        signal = "UP"
                        confidence = 0.65

                    result = {
                        'funding_rate': funding_rate,
                        'funding_rate_pct': funding_rate * 100,
                        'signal': signal,
                        'confidence': confidence,
                        'interpretation': self._interpret_funding(funding_rate),
                        'timestamp': datetime.now().isoformat()
                    }

                    # Cache result
                    self._cache[cache_key] = {
                        'data': result,
                        'timestamp': datetime.now()
                    }

                    return result

        except Exception as e:
            print(f"  ⚠️ Funding rate fetch failed for {token}: {e}")

        return None

    def _interpret_funding(self, rate: float) -> str:
        """Human-readable interpretation of funding rate."""
        if rate > 0.002:
            return "Extremely long-heavy (strong bearish contrarian signal)"
        elif rate > 0.001:
            return "Very long-heavy (bearish contrarian signal)"
        elif rate > 0.0005:
            return "Moderately long-heavy (mild bearish signal)"
        elif rate < -0.002:
            return "Extremely short-heavy (strong bullish contrarian signal)"
        elif rate < -0.001:
            return "Very short-heavy (bullish contrarian signal)"
        elif rate < -0.0005:
            return "Moderately short-heavy (mild bullish signal)"
        else:
            return "Neutral (no clear signal)"

    # =========================================================================
    # SIGNAL 2: Order Book Imbalance (Momentum)
    # =========================================================================

    def get_order_book_imbalance(self, token: str, depth: int = 20) -> Optional[Dict[str, Any]]:
        """
        Get order book imbalance from Binance spot market.

        Order Book Imbalance (OBI) measures buy vs sell pressure:
        - OBI > 0.55 = more buying pressure = BULLISH
        - OBI < 0.45 = more selling pressure = BEARISH

        Args:
            token: Token name (e.g., "bitcoin")
            depth: Number of order book levels to analyze (default: 20)

        Returns:
            Dict with obi, signal, and confidence
        """
        token_info = self.SUPPORTED_TOKENS.get(token.lower())
        if not token_info:
            return None

        symbol = token_info['binance']
        cache_key = f"orderbook_{symbol}"

        # Check cache (very short TTL for order book)
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if datetime.now() - entry['timestamp'] < timedelta(seconds=30):
                return entry['data']

        try:
            url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={depth}"

            self._wait_for_binance_rate_limit()
            response = httpx.get(url, timeout=10.0)

            if response.status_code == 200:
                data = response.json()

                # Calculate bid and ask volumes
                bid_volume = sum(float(bid[1]) for bid in data['bids'][:depth])
                ask_volume = sum(float(ask[1]) for ask in data['asks'][:depth])

                total_volume = bid_volume + ask_volume
                if total_volume == 0:
                    return None

                obi = bid_volume / total_volume

                # Interpret the signal
                signal = None
                confidence = 0.5

                if obi > 0.65:  # Strong buying pressure
                    signal = "UP"
                    confidence = 0.60
                elif obi > 0.55:  # Moderate buying pressure
                    signal = "UP"
                    confidence = 0.55
                elif obi < 0.35:  # Strong selling pressure
                    signal = "DOWN"
                    confidence = 0.60
                elif obi < 0.45:  # Moderate selling pressure
                    signal = "DOWN"
                    confidence = 0.55

                result = {
                    'obi': obi,
                    'bid_volume': bid_volume,
                    'ask_volume': ask_volume,
                    'signal': signal,
                    'confidence': confidence,
                    'interpretation': self._interpret_obi(obi),
                    'timestamp': datetime.now().isoformat()
                }

                # Cache result
                self._cache[cache_key] = {
                    'data': result,
                    'timestamp': datetime.now()
                }

                return result

        except Exception as e:
            print(f"  ⚠️ Order book fetch failed for {token}: {e}")

        return None

    def _interpret_obi(self, obi: float) -> str:
        """Human-readable interpretation of order book imbalance."""
        if obi > 0.65:
            return "Strong buying pressure (bullish momentum)"
        elif obi > 0.55:
            return "Moderate buying pressure (mild bullish)"
        elif obi < 0.35:
            return "Strong selling pressure (bearish momentum)"
        elif obi < 0.45:
            return "Moderate selling pressure (mild bearish)"
        else:
            return "Balanced order book (no clear signal)"

    # =========================================================================
    # SIGNAL 3: Social Sentiment (LunarCrush)
    # =========================================================================

    def get_sentiment_signal(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get social sentiment signal from LunarCrush.

        Args:
            token: Token name (e.g., "bitcoin")

        Returns:
            Dict with sentiment score, signal, and confidence
        """
        if not self.lunarcrush:
            return None

        try:
            data = self.lunarcrush.get_topic_data(token)
            if not data:
                return None

            sentiment = data.get('sentiment')
            trend = data.get('trend', '').lower()
            interactions = data.get('interactions') or 0

            # Interpret the signal
            signal = None
            confidence = 0.5

            # Sentiment-based signal
            if sentiment is not None:
                if sentiment >= 70:
                    signal = "UP"
                    confidence = 0.58
                elif sentiment >= 60:
                    signal = "UP"
                    confidence = 0.55
                elif sentiment <= 30:
                    signal = "DOWN"
                    confidence = 0.58
                elif sentiment <= 40:
                    signal = "DOWN"
                    confidence = 0.55

            # Boost confidence if trend aligns
            if trend == 'up' and signal == "UP":
                confidence = min(0.65, confidence + 0.05)
            elif trend == 'down' and signal == "DOWN":
                confidence = min(0.65, confidence + 0.05)

            # Boost confidence if high engagement
            if interactions > 100000:
                confidence = min(0.65, confidence + 0.03)

            return {
                'sentiment': sentiment,
                'trend': trend,
                'interactions': interactions,
                'social_volume': data.get('social_mentions_24h'),
                'signal': signal,
                'confidence': confidence,
                'interpretation': self._interpret_sentiment(sentiment, trend),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"  ⚠️ Sentiment fetch failed for {token}: {e}")

        return None

    def _interpret_sentiment(self, sentiment: Optional[float], trend: str) -> str:
        """Human-readable interpretation of sentiment."""
        if sentiment is None:
            return "No sentiment data available"
        if sentiment >= 70:
            return f"Very bullish sentiment ({sentiment:.0f}%), trend: {trend}"
        elif sentiment >= 60:
            return f"Bullish sentiment ({sentiment:.0f}%), trend: {trend}"
        elif sentiment <= 30:
            return f"Very bearish sentiment ({sentiment:.0f}%), trend: {trend}"
        elif sentiment <= 40:
            return f"Bearish sentiment ({sentiment:.0f}%), trend: {trend}"
        else:
            return f"Neutral sentiment ({sentiment:.0f}%), trend: {trend}"

    # =========================================================================
    # SIGNAL 4: Regime Detection
    # =========================================================================

    def detect_regime(self, token: str) -> Dict[str, Any]:
        """
        Detect current market regime to filter unfavorable conditions.

        Unfavorable regimes (should skip trading):
        - Weekend low liquidity
        - Very low volatility (flat market)
        - Post-major-move chop

        Args:
            token: Token name

        Returns:
            Dict with regime info and tradeable flag
        """
        now = datetime.utcnow()
        hour = now.hour
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        regime = {
            'hour_utc': hour,
            'weekday': weekday,
            'is_weekend': weekday >= 5,
            'is_asia_session': 0 <= hour < 8,
            'is_europe_session': 8 <= hour < 16,
            'is_us_session': 16 <= hour < 24,
            'tradeable': True,
            'confidence_modifier': 1.0,
            'skip_reason': None
        }

        # Weekend penalty
        if regime['is_weekend']:
            regime['confidence_modifier'] *= 0.8
            regime['skip_reason'] = "Weekend - lower liquidity"

        # Asia session - slightly lower confidence for Western traders
        if regime['is_asia_session']:
            regime['confidence_modifier'] *= 0.9

        # Get recent price action to detect choppy conditions
        try:
            token_info = self.SUPPORTED_TOKENS.get(token.lower())
            if token_info:
                symbol = token_info['binance']
                url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=24"

                self._wait_for_binance_rate_limit()
                response = httpx.get(url, timeout=10.0)

                if response.status_code == 200:
                    klines = response.json()

                    # Calculate recent volatility
                    closes = [float(k[4]) for k in klines]
                    if len(closes) >= 2:
                        returns = [(closes[i] - closes[i-1]) / closes[i-1]
                                   for i in range(1, len(closes))]

                        import statistics
                        volatility = statistics.stdev(returns) if len(returns) > 1 else 0

                        regime['volatility_24h'] = volatility

                        # Very low volatility = flat market = hard to predict
                        if volatility < 0.005:  # <0.5% hourly volatility
                            regime['confidence_modifier'] *= 0.7
                            regime['skip_reason'] = "Very low volatility - flat market"

                        # High volatility = trending = easier to predict
                        elif volatility > 0.02:  # >2% hourly volatility
                            regime['confidence_modifier'] *= 1.1

        except Exception as e:
            print(f"  ⚠️ Regime detection error: {e}")

        # Set tradeable flag based on confidence modifier
        if regime['confidence_modifier'] < 0.7:
            regime['tradeable'] = False

        return regime

    # =========================================================================
    # COMBINED EDGE DETECTION
    # =========================================================================

    def get_combined_edge(
        self,
        token: str,
        market_price: float = 0.50,
        min_confidence: float = 0.55
    ) -> Dict[str, Any]:
        """
        Get combined edge signal from all sources.

        Requires 2+ agreeing signals for a trade recommendation.

        Args:
            token: Token name (e.g., "bitcoin")
            market_price: Current Polymarket price (default: 0.50)
            min_confidence: Minimum confidence to recommend trade

        Returns:
            Dict with combined signal, confidence, and reasoning
        """
        print(f"\n  📊 Analyzing edge for {token.upper()}...")

        result = {
            'token': token,
            'market_price': market_price,
            'signals': {},
            'combined_signal': None,
            'combined_confidence': 0.5,
            'should_trade': False,
            'skip_reason': None,
            'reasoning': []
        }

        # Collect all signals
        signals_up = []
        signals_down = []

        # 1. Funding rate signal
        funding = self.get_funding_rate(token)
        if funding:
            result['signals']['funding'] = funding
            if funding['signal'] == "UP":
                signals_up.append(('funding', funding['confidence']))
                result['reasoning'].append(f"Funding: {funding['interpretation']}")
            elif funding['signal'] == "DOWN":
                signals_down.append(('funding', funding['confidence']))
                result['reasoning'].append(f"Funding: {funding['interpretation']}")

        # 2. Order book imbalance signal
        obi = self.get_order_book_imbalance(token)
        if obi:
            result['signals']['order_book'] = obi
            if obi['signal'] == "UP":
                signals_up.append(('order_book', obi['confidence']))
                result['reasoning'].append(f"Order Book: {obi['interpretation']}")
            elif obi['signal'] == "DOWN":
                signals_down.append(('order_book', obi['confidence']))
                result['reasoning'].append(f"Order Book: {obi['interpretation']}")

        # 3. Sentiment signal
        sentiment = self.get_sentiment_signal(token)
        if sentiment:
            result['signals']['sentiment'] = sentiment
            if sentiment['signal'] == "UP":
                signals_up.append(('sentiment', sentiment['confidence']))
                result['reasoning'].append(f"Sentiment: {sentiment['interpretation']}")
            elif sentiment['signal'] == "DOWN":
                signals_down.append(('sentiment', sentiment['confidence']))
                result['reasoning'].append(f"Sentiment: {sentiment['interpretation']}")

        # 4. Regime detection
        regime = self.detect_regime(token)
        result['signals']['regime'] = regime

        if not regime['tradeable']:
            result['skip_reason'] = regime['skip_reason']
            result['reasoning'].append(f"Regime: {regime['skip_reason']}")
            return result

        # 5. Price edge check
        if 0.45 <= market_price <= 0.55:
            result['skip_reason'] = "No price edge - market at ~50%"
            result['reasoning'].append("Price: No edge at $0.50 (need mispriced market)")
            # Don't return yet - still provide signal info

        # Combine signals - need 2+ agreeing
        if len(signals_up) >= 2:
            # Average confidence of agreeing signals
            avg_confidence = sum(c for _, c in signals_up) / len(signals_up)
            # Apply regime modifier
            final_confidence = avg_confidence * regime['confidence_modifier']

            result['combined_signal'] = "UP"
            result['combined_confidence'] = final_confidence

            if final_confidence >= min_confidence and result['skip_reason'] is None:
                result['should_trade'] = True

        elif len(signals_down) >= 2:
            avg_confidence = sum(c for _, c in signals_down) / len(signals_down)
            final_confidence = avg_confidence * regime['confidence_modifier']

            result['combined_signal'] = "DOWN"
            result['combined_confidence'] = final_confidence

            if final_confidence >= min_confidence and result['skip_reason'] is None:
                result['should_trade'] = True
        else:
            result['skip_reason'] = "Insufficient signal agreement (need 2+)"
            result['reasoning'].append("Signals: Not enough agreement to trade")

        # Log summary
        print(f"    UP signals: {len(signals_up)}, DOWN signals: {len(signals_down)}")
        print(f"    Combined: {result['combined_signal']} @ {result['combined_confidence']:.1%}")
        print(f"    Trade: {'✅ YES' if result['should_trade'] else '❌ NO'}")
        if result['skip_reason']:
            print(f"    Skip reason: {result['skip_reason']}")

        return result

    def _wait_for_binance_rate_limit(self):
        """Enforce rate limit for Binance API."""
        elapsed = time.time() - self._last_binance_request
        if elapsed < self._binance_rate_limit:
            time.sleep(self._binance_rate_limit - elapsed)
        self._last_binance_request = time.time()

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def detect_token_from_question(self, question: str) -> Optional[str]:
        """
        Detect which crypto token a market question is about.

        Args:
            question: Market question text

        Returns:
            Token name or None
        """
        question_lower = question.lower()

        # Direct token mentions
        for token, info in self.SUPPORTED_TOKENS.items():
            if token in question_lower:
                return token
            if info['symbol'].lower() in question_lower:
                return token

        return None

    def format_edge_for_prompt(self, edge_result: Dict[str, Any]) -> str:
        """
        Format edge analysis for inclusion in LLM prompt.

        Args:
            edge_result: Result from get_combined_edge()

        Returns:
            Formatted string for prompt
        """
        lines = [
            f"\n=== CRYPTO EDGE ANALYSIS: {edge_result['token'].upper()} ===",
            f"Combined Signal: {edge_result['combined_signal'] or 'NONE'}",
            f"Confidence: {edge_result['combined_confidence']:.1%}",
            f"Should Trade: {'YES' if edge_result['should_trade'] else 'NO'}",
        ]

        if edge_result['skip_reason']:
            lines.append(f"Skip Reason: {edge_result['skip_reason']}")

        if edge_result['reasoning']:
            lines.append("\nSignal Breakdown:")
            for reason in edge_result['reasoning']:
                lines.append(f"  • {reason}")

        return "\n".join(lines)


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == "__main__":
    print("Testing CryptoEdgeDetector...")

    detector = CryptoEdgeDetector()

    # Test with Bitcoin
    print("\n" + "="*60)
    print("BITCOIN EDGE ANALYSIS")
    print("="*60)

    edge = detector.get_combined_edge("bitcoin", market_price=0.48)
    print(detector.format_edge_for_prompt(edge))

    # Test with Ethereum
    print("\n" + "="*60)
    print("ETHEREUM EDGE ANALYSIS")
    print("="*60)

    edge = detector.get_combined_edge("ethereum", market_price=0.52)
    print(detector.format_edge_for_prompt(edge))

    # Test with Solana
    print("\n" + "="*60)
    print("SOLANA EDGE ANALYSIS")
    print("="*60)

    edge = detector.get_combined_edge("solana", market_price=0.50)
    print(detector.format_edge_for_prompt(edge))
