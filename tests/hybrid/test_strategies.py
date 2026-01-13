"""Tests for hybrid bot strategies."""

import pytest
from decimal import Decimal
from datetime import datetime, timezone

from agents.hybrid.strategies.base import (
    StrategyIntent,
    OrderBook,
    DualOrderBook,
    BaseStrategy,
    LearningStrategy,
    StrategyManager,
)
from agents.hybrid.strategies.arbitrage import (
    BinaryArbitrageStrategy,
    create_arbitrage_strategy,
)
from agents.hybrid.config import ArbitrageConfig


class TestStrategyIntent:
    """Tests for StrategyIntent dataclass."""

    def test_create_intent(self):
        """Test creating a strategy intent."""
        intent = StrategyIntent(
            market_id="test-market",
            token_id="token-123",
            outcome="YES",
            side="buy",
            price=Decimal("0.55"),
            size=Decimal("10"),
            reason="Test trade",
            strategy_name="test",
        )
        assert intent.market_id == "test-market"
        assert intent.is_buy is True
        assert intent.is_sell is False

    def test_intent_immutability(self):
        """Test intent is frozen."""
        intent = StrategyIntent(
            market_id="test",
            token_id="token",
            outcome="YES",
            side="buy",
            price=Decimal("0.50"),
            size=Decimal("5"),
            reason="Test",
            strategy_name="test",
        )
        with pytest.raises(Exception):
            intent.price = Decimal("0.60")

    def test_intent_repr(self):
        """Test intent string representation."""
        intent = StrategyIntent(
            market_id="test",
            token_id="token",
            outcome="YES",
            side="buy",
            price=Decimal("0.50"),
            size=Decimal("5"),
            reason="Test",
            strategy_name="test_strat",
            confidence=Decimal("0.75"),
        )
        repr_str = repr(intent)
        assert "test_strat" in repr_str
        assert "BUY" in repr_str
        assert "0.75" in repr_str


class TestOrderBook:
    """Tests for OrderBook dataclass."""

    def test_best_bid_ask(self):
        """Test best bid/ask extraction."""
        book = OrderBook(
            market_id="test",
            token_id="token",
            outcome="YES",
            bids=[
                (Decimal("0.50"), Decimal("100")),
                (Decimal("0.49"), Decimal("50")),
            ],
            asks=[
                (Decimal("0.52"), Decimal("75")),
                (Decimal("0.53"), Decimal("100")),
            ],
        )
        assert book.best_bid == (Decimal("0.50"), Decimal("100"))
        assert book.best_ask == (Decimal("0.52"), Decimal("75"))
        assert book.best_bid_price == Decimal("0.50")
        assert book.best_ask_price == Decimal("0.52")

    def test_mid_price(self):
        """Test mid-price calculation."""
        book = OrderBook(
            market_id="test",
            token_id="token",
            outcome="YES",
            bids=[(Decimal("0.50"), Decimal("100"))],
            asks=[(Decimal("0.54"), Decimal("100"))],
        )
        assert book.mid_price == Decimal("0.52")

    def test_spread(self):
        """Test spread calculation."""
        book = OrderBook(
            market_id="test",
            token_id="token",
            outcome="YES",
            bids=[(Decimal("0.50"), Decimal("100"))],
            asks=[(Decimal("0.54"), Decimal("100"))],
        )
        assert book.spread == Decimal("0.04")

    def test_empty_book(self):
        """Test empty orderbook."""
        book = OrderBook(
            market_id="test",
            token_id="token",
            outcome="YES",
            bids=[],
            asks=[],
        )
        assert book.best_bid is None
        assert book.best_ask is None
        assert book.mid_price is None
        assert book.spread is None


class TestDualOrderBook:
    """Tests for DualOrderBook."""

    def test_is_complete(self):
        """Test completeness check."""
        yes_book = OrderBook(
            market_id="test",
            token_id="yes-token",
            outcome="YES",
            bids=[(Decimal("0.50"), Decimal("100"))],
            asks=[(Decimal("0.52"), Decimal("100"))],
        )
        no_book = OrderBook(
            market_id="test",
            token_id="no-token",
            outcome="NO",
            bids=[(Decimal("0.48"), Decimal("100"))],
            asks=[(Decimal("0.50"), Decimal("100"))],
        )

        # Complete dual book
        dual = DualOrderBook(
            market_id="test",
            yes_book=yes_book,
            no_book=no_book,
        )
        assert dual.is_complete is True

        # Incomplete dual book
        partial = DualOrderBook(market_id="test", yes_book=yes_book)
        assert partial.is_complete is False


class TestBinaryArbitrageStrategy:
    """Tests for BinaryArbitrageStrategy."""

    def test_no_arbitrage_when_combined_above_one(self):
        """Test no arbitrage when prices sum to >= 1."""
        strategy = BinaryArbitrageStrategy()

        yes_book = OrderBook(
            market_id="test",
            token_id="yes",
            outcome="YES",
            bids=[],
            asks=[(Decimal("0.55"), Decimal("100"))],
        )
        no_book = OrderBook(
            market_id="test",
            token_id="no",
            outcome="NO",
            bids=[],
            asks=[(Decimal("0.50"), Decimal("100"))],
        )
        dual = DualOrderBook(market_id="test", yes_book=yes_book, no_book=no_book)

        result = strategy.analyze_dual(dual)
        assert result is None  # 0.55 + 0.50 = 1.05 >= 1.00

    def test_arbitrage_detected(self):
        """Test arbitrage detected when profitable."""
        config = ArbitrageConfig(min_profit=Decimal("0.001"))
        strategy = BinaryArbitrageStrategy(config=config)

        yes_book = OrderBook(
            market_id="test",
            token_id="yes",
            outcome="YES",
            bids=[],
            asks=[(Decimal("0.45"), Decimal("100"))],
        )
        no_book = OrderBook(
            market_id="test",
            token_id="no",
            outcome="NO",
            bids=[],
            asks=[(Decimal("0.45"), Decimal("100"))],
        )
        dual = DualOrderBook(market_id="test", yes_book=yes_book, no_book=no_book)

        result = strategy.analyze_dual(dual)
        assert result is not None

        yes_intent, no_intent = result
        assert yes_intent.side == "buy"
        assert yes_intent.outcome == "YES"
        assert no_intent.side == "buy"
        assert no_intent.outcome == "NO"

    def test_arbitrage_below_min_profit(self):
        """Test arbitrage rejected if below min profit."""
        config = ArbitrageConfig(min_profit=Decimal("0.10"))  # 10% min
        strategy = BinaryArbitrageStrategy(config=config)

        # 0.48 + 0.48 = 0.96, profit = 4% - fees
        yes_book = OrderBook(
            market_id="test",
            token_id="yes",
            outcome="YES",
            bids=[],
            asks=[(Decimal("0.48"), Decimal("100"))],
        )
        no_book = OrderBook(
            market_id="test",
            token_id="no",
            outcome="NO",
            bids=[],
            asks=[(Decimal("0.48"), Decimal("100"))],
        )
        dual = DualOrderBook(market_id="test", yes_book=yes_book, no_book=no_book)

        result = strategy.analyze_dual(dual)
        assert result is None  # Profit too low

    def test_is_profitable_quick_check(self):
        """Test quick profitability check."""
        strategy = BinaryArbitrageStrategy()

        yes_book = OrderBook(
            market_id="test",
            token_id="yes",
            outcome="YES",
            bids=[],
            asks=[(Decimal("0.40"), Decimal("100"))],
        )
        no_book = OrderBook(
            market_id="test",
            token_id="no",
            outcome="NO",
            bids=[],
            asks=[(Decimal("0.40"), Decimal("100"))],
        )
        dual = DualOrderBook(market_id="test", yes_book=yes_book, no_book=no_book)

        assert strategy.is_profitable(dual) is True

    def test_single_book_returns_none(self):
        """Test analyze() returns None (needs dual book)."""
        strategy = BinaryArbitrageStrategy()
        book = OrderBook(
            market_id="test",
            token_id="token",
            outcome="YES",
            bids=[],
            asks=[],
        )
        assert strategy.analyze(book) is None


class TestLearningStrategy:
    """Tests for LearningStrategy base class."""

    def test_edge_detection(self):
        """Test edge detection by market type."""

        class TestStrategy(LearningStrategy):
            def analyze(self, orderbook):
                return None

        strategy = TestStrategy("test")

        # No edge data = assume edge
        assert strategy.has_edge("crypto") is True

        # With edge data
        strategy.update_edge_data({
            "crypto": Decimal("5.0"),
            "sports": Decimal("-2.0"),
        })
        assert strategy.has_edge("crypto") is True
        assert strategy.has_edge("sports") is False
        assert strategy.has_edge("unknown") is True  # No data = assume edge

    def test_confidence_calibration(self):
        """Test confidence calibration."""

        class TestStrategy(LearningStrategy):
            def analyze(self, orderbook):
                return None

        strategy = TestStrategy("test")
        strategy.set_calibration_shift(Decimal("-0.10"))

        # Should reduce confidence by 10%
        calibrated = strategy.calibrate_confidence(Decimal("0.70"))
        assert calibrated == Decimal("0.60")

        # Should clamp to 0
        calibrated = strategy.calibrate_confidence(Decimal("0.05"))
        assert calibrated == Decimal("0")


class TestStrategyManager:
    """Tests for StrategyManager."""

    def test_add_remove_strategy(self):
        """Test adding and removing strategies."""
        manager = StrategyManager()
        strategy = create_arbitrage_strategy()

        manager.add_strategy(strategy)
        assert len(manager.strategies) == 1
        assert manager.get_strategy("arbitrage") is not None

        removed = manager.remove_strategy("arbitrage")
        assert removed is True
        assert len(manager.strategies) == 0

    def test_enabled_strategies(self):
        """Test enabled strategy filtering."""
        manager = StrategyManager()
        strategy = create_arbitrage_strategy()

        manager.add_strategy(strategy)
        assert len(manager.enabled_strategies) == 1

        strategy.disable()
        assert len(manager.enabled_strategies) == 0

    def test_analyze_all(self):
        """Test running all strategies."""
        manager = StrategyManager()
        strategy = create_arbitrage_strategy()
        manager.add_strategy(strategy)

        book = OrderBook(
            market_id="test",
            token_id="token",
            outcome="YES",
            bids=[],
            asks=[],
        )

        # Single book analysis returns empty (arbitrage needs dual)
        intents = manager.analyze_all(book)
        assert intents == []
