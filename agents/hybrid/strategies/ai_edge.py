"""
AI Edge Detection Strategy for Hybrid Bot

Combines multi-agent reasoning from Learning Autonomous Trader
with the StrategyIntent pattern from PolyAgentVPS.

This strategy:
1. Uses LLM (xAI/OpenAI) for market analysis
2. Applies edge detection by market type
3. Uses Kelly sizing for position sizing
4. Calibrates confidence to fix overconfidence
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
import logging

from agents.hybrid.strategies.base import (
    LearningStrategy,
    OrderBook,
    StrategyIntent,
)
from agents.hybrid.config import LearningConfig, KellySizingConfig

logger = logging.getLogger(__name__)


@dataclass
class MarketAnalysis:
    """Result of AI market analysis."""
    direction: str           # "YES" or "NO"
    confidence: float        # 0.0 to 1.0
    reasoning: str          # Explanation
    market_type: str        # "crypto", "sports", "other"


class AIEdgeStrategy(LearningStrategy):
    """
    AI-powered edge detection strategy.

    Uses multi-agent reasoning to analyze markets and make
    trading decisions based on learned edge patterns.
    """

    def __init__(
        self,
        learning_config: LearningConfig,
        kelly_config: KellySizingConfig,
        multi_agent_reasoner: Optional[Any] = None,
        crypto_edge_detector: Optional[Any] = None,
        base_position_size: Decimal = Decimal("5"),
        bankroll: Decimal = Decimal("100"),
    ):
        """
        Initialize AI edge strategy.

        Args:
            learning_config: Learning system configuration
            kelly_config: Kelly sizing configuration
            multi_agent_reasoner: MultiAgentReasoning instance
            crypto_edge_detector: CryptoEdgeDetector instance
            base_position_size: Default position size
            bankroll: Total capital for Kelly sizing
        """
        super().__init__(name="ai_edge")
        self._learning_config = learning_config
        self._kelly_config = kelly_config
        self._multi_agent = multi_agent_reasoner
        self._crypto_edge = crypto_edge_detector
        self._base_size = base_position_size
        self._bankroll = bankroll

        # Market analysis cache (to avoid repeated API calls)
        self._analysis_cache: Dict[str, MarketAnalysis] = {}
        self._cache_expiry: Dict[str, float] = {}
        self._cache_ttl = 300  # 5 minutes

    def set_multi_agent(self, reasoner: Any) -> None:
        """Set the multi-agent reasoner."""
        self._multi_agent = reasoner

    def set_crypto_edge(self, detector: Any) -> None:
        """Set the crypto edge detector."""
        self._crypto_edge = detector

    def analyze(self, orderbook: OrderBook) -> Optional[StrategyIntent]:
        """
        Analyze orderbook using AI and return trading intent.

        Steps:
        1. Check if we have edge in this market type
        2. Get AI analysis (multi-agent reasoning)
        3. Apply calibration to confidence
        4. Calculate position size (Kelly)
        5. Create intent if all criteria met
        """
        import time

        # Skip if AI reasoning not available
        if self._multi_agent is None:
            return None

        market_id = orderbook.market_id
        market_type = self._classify_market_type(orderbook)

        # 1. Check edge in this market type
        if not self.has_edge(market_type):
            logger.debug(f"Skipping {market_id}: no edge in {market_type}")
            return None

        # 2. Get AI analysis (with caching)
        analysis = self._get_ai_analysis(orderbook)
        if analysis is None:
            return None

        # 3. Apply calibration
        raw_confidence = Decimal(str(analysis.confidence))
        calibrated_confidence = self.calibrate_confidence(raw_confidence)

        # Check minimum confidence
        if calibrated_confidence < self._learning_config.min_confidence:
            logger.debug(
                f"Skipping {market_id}: confidence {calibrated_confidence} "
                f"< {self._learning_config.min_confidence}"
            )
            return None

        # 4. Calculate position size
        size = self._calculate_kelly_size(
            calibrated_confidence,
            market_type,
        )

        if size < Decimal("1"):
            logger.debug(f"Skipping {market_id}: Kelly size too small")
            return None

        # 5. Determine price and side
        if analysis.direction == "YES":
            # Buy YES at the ask
            if orderbook.best_ask is None:
                return None
            price, available = orderbook.best_ask
            side = "buy"
            outcome = "YES"
        else:
            # Buy NO (sell YES) at the bid
            if orderbook.best_bid is None:
                return None
            price, available = orderbook.best_bid
            side = "sell"
            outcome = "NO"

        # Don't exceed available liquidity
        if size > available:
            size = available

        return StrategyIntent(
            market_id=market_id,
            token_id=orderbook.token_id,
            outcome=outcome,
            side=side,
            price=price,
            size=size,
            reason=f"AI: {analysis.reasoning[:100]}",
            strategy_name=self.name,
            confidence=calibrated_confidence,
            metadata={
                "market_type": market_type,
                "raw_confidence": float(raw_confidence),
                "calibrated_confidence": float(calibrated_confidence),
                "kelly_size": float(size),
            }
        )

    def _get_ai_analysis(self, orderbook: OrderBook) -> Optional[MarketAnalysis]:
        """
        Get AI analysis for a market.

        Uses caching to avoid repeated API calls.
        """
        import time

        market_id = orderbook.market_id
        now = time.time()

        # Check cache
        if market_id in self._analysis_cache:
            expiry = self._cache_expiry.get(market_id, 0)
            if now < expiry:
                return self._analysis_cache[market_id]

        # Call multi-agent reasoner
        try:
            # This should be the actual multi-agent call
            # For now, return None if no multi-agent is set
            if self._multi_agent is None:
                return None

            # The actual implementation would call:
            # result = self._multi_agent.analyze_market(market_data)
            # For now, we'll stub this
            logger.info(f"AI analysis would be called for {market_id}")
            return None  # Placeholder

        except Exception as e:
            logger.error(f"AI analysis failed for {market_id}: {e}")
            return None

    def _calculate_kelly_size(
        self,
        confidence: Decimal,
        market_type: str,
    ) -> Decimal:
        """
        Calculate position size using Kelly criterion.

        Kelly formula: f* = (bp - q) / b
        Where:
        - b = odds (payout ratio)
        - p = probability of winning
        - q = probability of losing (1-p)
        - f* = fraction of bankroll to bet

        For binary markets at fair odds:
        f* = 2p - 1 (simplified)

        We use fractional Kelly for safety.
        """
        if not self._kelly_config.enabled:
            return self._base_size

        # Estimate edge from confidence
        p = float(confidence)
        q = 1 - p

        # Simplified Kelly for 1:1 payout
        edge = 2 * p - 1

        if edge < float(self._kelly_config.min_edge):
            return self._base_size

        # Full Kelly fraction
        kelly_fraction = edge

        # Apply our fractional Kelly (conservative)
        adjusted_fraction = kelly_fraction * float(self._kelly_config.fraction)

        # Apply max bet limit
        adjusted_fraction = min(
            adjusted_fraction,
            float(self._kelly_config.max_bet_fraction)
        )

        # Calculate size
        size = self._bankroll * Decimal(str(adjusted_fraction))

        # Apply edge multiplier based on market type edge
        type_edge = self._edge_by_type.get(market_type, Decimal("0"))
        if type_edge > Decimal("10"):  # Strong historical edge
            size *= Decimal("1.25")  # 25% bonus
        elif type_edge < Decimal("0"):  # Negative edge (shouldn't happen)
            size *= Decimal("0.5")  # 50% reduction

        return max(Decimal("1"), size.quantize(Decimal("0.01")))

    def _classify_market_type(self, orderbook: OrderBook) -> str:
        """
        Classify market type from orderbook metadata.

        Falls back to "other" if unknown.
        """
        # Try to get from metadata if available
        # This would be populated by the market fetcher
        return "other"

    def enhance_with_crypto_signals(
        self,
        intent: StrategyIntent,
        symbol: str,
    ) -> StrategyIntent:
        """
        Enhance an intent with crypto-specific signals.

        Uses CryptoEdgeDetector for:
        - Funding rate bias
        - Order book imbalance
        - Sentiment analysis
        """
        if self._crypto_edge is None:
            return intent

        try:
            # Get crypto signals
            signal = self._crypto_edge.get_signal(symbol)
            if signal is None:
                return intent

            # Adjust confidence based on signal alignment
            signal_direction = "YES" if signal.direction > 0 else "NO"
            intent_direction = intent.outcome

            if signal_direction == intent_direction:
                # Signals align - boost confidence
                boost = Decimal(str(min(0.1, abs(signal.strength) * 0.2)))
                new_confidence = min(Decimal("0.95"), intent.confidence + boost)
            else:
                # Signals conflict - reduce confidence
                reduction = Decimal(str(min(0.1, abs(signal.strength) * 0.2)))
                new_confidence = max(Decimal("0.5"), intent.confidence - reduction)

            # Create new intent with adjusted confidence
            return StrategyIntent(
                market_id=intent.market_id,
                token_id=intent.token_id,
                outcome=intent.outcome,
                side=intent.side,
                price=intent.price,
                size=intent.size,
                reason=f"{intent.reason} [crypto signal: {signal_direction}]",
                strategy_name=intent.strategy_name,
                confidence=new_confidence,
                timestamp=intent.timestamp,
                metadata={
                    **intent.metadata,
                    "crypto_signal": signal_direction,
                    "signal_strength": signal.strength,
                }
            )

        except Exception as e:
            logger.error(f"Crypto signal enhancement failed: {e}")
            return intent

    def reset(self) -> None:
        """Reset analysis cache."""
        self._analysis_cache.clear()
        self._cache_expiry.clear()


def create_ai_edge_strategy(
    learning_config: Optional[LearningConfig] = None,
    kelly_config: Optional[KellySizingConfig] = None,
    bankroll: Decimal = Decimal("100"),
) -> AIEdgeStrategy:
    """
    Factory function to create an AI edge strategy.

    Lazily loads AI components to avoid import errors.
    """
    from agents.hybrid.config import LearningConfig, KellySizingConfig

    learning_config = learning_config or LearningConfig()
    kelly_config = kelly_config or KellySizingConfig()

    strategy = AIEdgeStrategy(
        learning_config=learning_config,
        kelly_config=kelly_config,
        bankroll=bankroll,
    )

    # Try to load multi-agent reasoner
    try:
        from agents.reasoning.multi_agent import MultiAgentReasoning
        strategy.set_multi_agent(MultiAgentReasoning())
        logger.info("MultiAgentReasoning loaded")
    except ImportError:
        logger.warning("MultiAgentReasoning not available")

    # Try to load crypto edge detector
    try:
        from agents.connectors.crypto_edge import CryptoEdgeDetector
        strategy.set_crypto_edge(CryptoEdgeDetector())
        logger.info("CryptoEdgeDetector loaded")
    except ImportError:
        logger.warning("CryptoEdgeDetector not available")

    return strategy
