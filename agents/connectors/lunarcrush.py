"""
LunarCrush API Connector

Provides social intelligence data for cryptocurrency markets.
Individual Plan: 10 requests/minute rate limit.
"""

import os
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import httpx
from dotenv import load_dotenv


class LunarCrush:
    """
    LunarCrush API client for fetching crypto social intelligence.

    Individual Plan Limits:
    - 10 requests/minute
    - Implements caching to respect rate limits
    """

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("LUNARCRUSH_API_KEY")
        if not self.api_key:
            raise ValueError("LUNARCRUSH_API_KEY not found in .env")

        self.base_url = "https://lunarcrush.com/api4/public"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        # Cache to respect 10 req/min rate limit
        # Cache entries: {topic: {data: {...}, timestamp: datetime}}
        self._cache = {}
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes

        # Rate limiting: 10 req/min = 1 req per 6 seconds
        self._last_request_time = None
        self._min_request_interval = 6  # seconds

    def _wait_for_rate_limit(self):
        """Enforce rate limit: 10 req/min (1 per 6 seconds)."""
        if self._last_request_time is not None:
            elapsed = time.time() - self._last_request_time
            if elapsed < self._min_request_interval:
                wait_time = self._min_request_interval - elapsed
                print(f"  ⏱️  Rate limit: waiting {wait_time:.1f}s...")
                time.sleep(wait_time)

        self._last_request_time = time.time()

    def _get_from_cache(self, topic: str) -> Optional[Dict[str, Any]]:
        """Get cached data if still valid."""
        if topic in self._cache:
            entry = self._cache[topic]
            age = datetime.now() - entry["timestamp"]
            if age < self._cache_ttl:
                print(f"  💾 Using cached LunarCrush data for {topic} (age: {age.seconds}s)")
                return entry["data"]
        return None

    def _save_to_cache(self, topic: str, data: Dict[str, Any]):
        """Save data to cache."""
        self._cache[topic] = {
            "data": data,
            "timestamp": datetime.now()
        }

    def get_topic_data(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        Get social intelligence data for a crypto topic (coin/token).

        Args:
            topic: Coin/token name (e.g., "bitcoin", "ethereum", "solana")

        Returns:
            Dict with LunarCrush metrics or None if error

        Example response:
        {
            "galaxy_score": 75,
            "alt_rank": 12,
            "sentiment": 68.5,
            "social_mentions_24h": 15234,
            "social_contributors": 3421,
            "interactions": 45678,
            "price": 3456.78,
            "percent_change_24h": 2.34,
            "market_cap": 123456789,
            "volatility": 0.045
        }
        """
        # Check cache first
        cached_data = self._get_from_cache(topic.lower())
        if cached_data:
            return cached_data

        # Enforce rate limit
        self._wait_for_rate_limit()

        # Fetch from API
        url = f"{self.base_url}/topic/{topic.lower()}/v1"

        try:
            print(f"  🌙 Fetching LunarCrush data for {topic}...")
            response = httpx.get(url, headers=self.headers, timeout=10.0)

            if response.status_code == 200:
                data = response.json()

                # Extract and flatten relevant metrics
                formatted_data = self._format_response(data)

                # Cache the result
                self._save_to_cache(topic.lower(), formatted_data)

                return formatted_data
            elif response.status_code == 404:
                print(f"  ⚠️ Topic '{topic}' not found on LunarCrush")
                return None
            else:
                print(f"  ⚠️ LunarCrush API error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            print(f"  ⚠️ LunarCrush request failed: {e}")
            return None

    def _format_response(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format key metrics from LunarCrush API v4 response."""
        data = raw_data.get("data", raw_data)

        # Calculate average sentiment from types_sentiment (sentiment per platform)
        avg_sentiment = None
        types_sentiment = data.get("types_sentiment")
        if types_sentiment and isinstance(types_sentiment, dict):
            sentiment_values = [v for v in types_sentiment.values() if isinstance(v, (int, float))]
            if sentiment_values:
                avg_sentiment = sum(sentiment_values) / len(sentiment_values)

        return {
            # Social Metrics (API v4 field mapping)
            "galaxy_score": data.get("galaxy_score"),  # Not in v4
            "alt_rank": data.get("topic_rank"),  # v4: topic_rank
            "sentiment": avg_sentiment,  # v4: calculated from types_sentiment
            "social_mentions_24h": data.get("num_posts"),  # v4: num_posts
            "social_contributors": data.get("num_contributors"),  # v4: num_contributors
            "interactions": data.get("interactions_24h"),  # v4: interactions_24h
            "posts_active": data.get("num_posts"),  # v4: num_posts
            "posts_created": data.get("num_posts"),  # v4: num_posts
            "social_dominance": data.get("social_dominance"),  # Not in v4
            "spam": None,  # Not in v4 API

            # Market Metrics
            "price": data.get("price"),
            "percent_change_24h": data.get("percent_change_24h"),
            "market_cap": data.get("market_cap"),
            "market_cap_rank": data.get("market_cap_rank"),
            "volume_24h": data.get("volume_24h"),
            "volatility": data.get("volatility"),

            # Metadata
            "symbol": data.get("symbol"),
            "name": data.get("title"),  # v4: title instead of name

            # Additional v4 fields
            "trend": data.get("trend"),  # v4: momentum indicator (up/down)
        }

    def format_for_prompt(self, topic: str, data: Dict[str, Any]) -> str:
        """
        Format LunarCrush data for inclusion in Grok's analysis prompt.

        Args:
            topic: Coin/token name
            data: LunarCrush metrics dict

        Returns:
            Formatted string for prompt inclusion
        """
        if not data:
            return f"LunarCrush data unavailable for {topic}."

        # Determine sentiment interpretation
        sentiment = data.get("sentiment")
        if sentiment is not None:
            if sentiment >= 60:
                sentiment_text = f"{sentiment:.1f}% (bullish)"
            elif sentiment >= 40:
                sentiment_text = f"{sentiment:.1f}% (neutral)"
            else:
                sentiment_text = f"{sentiment:.1f}% (bearish)"
        else:
            sentiment_text = "N/A"

        # Determine Galaxy Score interpretation
        galaxy_score = data.get("galaxy_score")
        if galaxy_score is not None:
            if galaxy_score >= 75:
                galaxy_text = f"{galaxy_score}/100 (very high engagement)"
            elif galaxy_score >= 50:
                galaxy_text = f"{galaxy_score}/100 (moderate engagement)"
            else:
                galaxy_text = f"{galaxy_score}/100 (low engagement)"
        else:
            galaxy_text = "N/A"

        # Get trend indicator
        trend = data.get("trend", "").upper()
        trend_text = f"{trend} momentum" if trend else "N/A"

        prompt_text = f"""
LunarCrush Social Intelligence for {topic.title()}:
- Topic Rank: #{data.get('alt_rank') or 'N/A'} (relative performance ranking)
- Sentiment: {sentiment_text}
- Trend: {trend_text}
- Social Volume (24h): {(data.get('social_mentions_24h') or 0):,} posts
- Social Contributors: {(data.get('social_contributors') or 0):,} unique users
- Total Interactions (24h): {(data.get('interactions') or 0):,}
- Price Change (24h): {data.get('percent_change_24h') or 'N/A'}%
- Volatility: {data.get('volatility') or 'N/A'}

Use this social intelligence data alongside market fundamentals for your prediction.
High interaction volume + positive sentiment = bullish signal. Declining trend + low sentiment = bearish signal.
"""
        return prompt_text.strip()

    def detect_crypto_token(self, market_question: str, market_description: str) -> Optional[str]:
        """
        Detect if a market is about crypto and extract the token name.

        Args:
            market_question: Market question text
            market_description: Market description text

        Returns:
            Token name (e.g., "bitcoin", "ethereum") or None if not crypto
        """
        import re

        # Common crypto tokens to detect with word boundary matching
        crypto_keywords = {
            "bitcoin": ["bitcoin", r"\bbtc\b"],
            "ethereum": ["ethereum", r"\beth\b", "ether"],
            "solana": ["solana", r"\bsol\b"],  # Use word boundary to avoid matching "console", "solace"
            "cardano": ["cardano", r"\bada\b"],
            "polkadot": ["polkadot", r"\bdot\b"],
            "avalanche": ["avalanche", r"\bavax\b"],
            "polygon": ["polygon", r"\bmatic\b"],
            "chainlink": ["chainlink", r"\blink\b"],
            "uniswap": ["uniswap", r"\buni\b"],
            "litecoin": ["litecoin", r"\bltc\b"],
            "dogecoin": ["dogecoin", r"\bdoge\b"],
            "shiba": ["shiba", r"\bshib\b"],
            "ripple": ["ripple", r"\bxrp\b"],
            "binance": ["binance", r"\bbnb\b"],
        }

        combined_text = f"{market_question} {market_description}".lower()

        for token, keywords in crypto_keywords.items():
            for keyword in keywords:
                # Use regex for word boundary patterns
                if keyword.startswith(r"\b"):
                    if re.search(keyword, combined_text):
                        return token
                else:
                    # Simple substring match for full names
                    if keyword in combined_text:
                        return token

        return None
