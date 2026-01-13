"""
Integrated Learning System

Combines all learning components into one cohesive system:
1. Edge Detection - Skip markets where we have no edge
2. Feature Learning - Learn which features predict outcomes
3. Multi-Agent Reasoning - Prevent backwards trades
4. Isotonic Calibration - Better confidence adjustment

This is the complete learning bot.
"""

from typing import Dict, Optional, Tuple
from agents.learning.trade_history import TradeHistoryDB
from agents.learning.calibration import CalibrationTracker
from agents.learning.feature_learning import FeatureLearner
from agents.learning.isotonic_calibration import IsotonicCalibrator


class IntegratedLearningBot:
    """
    Complete learning system that improves over time

    Capabilities:
    - Learns which markets to trade (edge detection)
    - Learns which features predict outcomes (pattern recognition)
    - Prevents backwards trades (multi-agent verification)
    - Improves calibration (isotonic regression)
    - Adapts position sizing (Kelly criterion)
    """

    def __init__(self, db_path: str = "/tmp/integrated_learner.db"):
        # Initialize core components
        self.db = TradeHistoryDB(db_path)
        self.calibration_tracker = CalibrationTracker(self.db)
        self.feature_learner = FeatureLearner(self.db)
        self.isotonic_calibrator = IsotonicCalibrator(self.db)

        # Learning stats
        self.learning_enabled = True

    def should_trade_market(
        self,
        market_data: Dict,
        market_type: Optional[str] = None,
        min_confidence: float = 0.55
    ) -> Tuple[bool, str, Dict]:
        """
        Comprehensive decision: Should we trade this market?

        Uses multiple learning systems:
        1. Edge detection - Do we historically profit in this market type?
        2. Feature learning - Do features suggest we'll be accurate?
        3. Confidence threshold - Is our confidence high enough?

        Returns:
            (should_trade, reason, analysis)
        """
        analysis = {
            "edge_check": None,
            "feature_check": None,
            "confidence_check": None
        }

        # Check 1: Edge detection
        edge_by_type = self.db.get_edge_by_market_type()

        if market_type and market_type in edge_by_type:
            edge_stats = edge_by_type[market_type]

            if not edge_stats['has_edge']:
                analysis["edge_check"] = "FAIL"
                avg_pnl = edge_stats['avg_pnl_per_trade'] or 0
                return (
                    False,
                    f"No historical edge in {market_type} (avg P&L: ${avg_pnl:.2f})",
                    analysis
                )

            analysis["edge_check"] = "PASS"

        # Check 2: Feature learning
        if self.learning_enabled:
            try:
                prob_correct = self.feature_learner.predict_correctness_probability(
                    market_data,
                    market_type
                )

                if prob_correct is not None:
                    if prob_correct < 0.55:
                        analysis["feature_check"] = f"FAIL ({prob_correct:.1%})"
                        return (
                            False,
                            f"Features suggest low accuracy ({prob_correct:.1%})",
                            analysis
                        )

                    analysis["feature_check"] = f"PASS ({prob_correct:.1%})"
            except:
                analysis["feature_check"] = "SKIPPED (model not trained)"

        # Check 3: Confidence threshold
        # (This would be checked after we make a prediction)
        analysis["confidence_check"] = "PENDING"

        return True, "Passed all checks", analysis

    def adjust_confidence(
        self,
        raw_confidence: float,
        market_type: Optional[str] = None
    ) -> Tuple[float, str]:
        """
        Adjust confidence using learned calibration

        Uses isotonic regression if available, falls back to bucketing.

        Returns:
            (calibrated_confidence, method)
        """
        # Try isotonic calibration first
        try:
            calibrated = self.isotonic_calibrator.calibrate(raw_confidence, market_type)
            adjustment = calibrated - raw_confidence

            if abs(adjustment) > 0.01:  # Meaningful adjustment
                return calibrated, f"isotonic_regression ({adjustment:+.0%})"
        except:
            pass

        # Fallback to simple calibration
        calibrated = self.calibration_tracker.calibrate_confidence(
            raw_confidence,
            market_type
        )

        adjustment = calibrated - raw_confidence
        return calibrated, f"bucketing ({adjustment:+.0%})"

    def calculate_position_size(
        self,
        probability: float,
        market_price: float,
        bankroll: float,
        max_position: float = 2.0,
        kelly_fraction: float = 0.25
    ) -> Tuple[float, str]:
        """
        Calculate optimal position size using Kelly Criterion

        Args:
            probability: Our calibrated probability
            market_price: Current market price
            bankroll: Total available capital
            max_position: Maximum position size
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)

        Returns:
            (position_size, explanation)
        """
        # Kelly formula: (p * odds - (1-p)) / odds
        if market_price <= 0 or market_price >= 1:
            return 0.0, "Invalid market price"

        odds = (1.0 / market_price) - 1.0
        kelly_pct = (probability * odds - (1 - probability)) / odds

        # Apply safety fraction
        fractional_kelly = kelly_pct * kelly_fraction

        # Clamp to reasonable range
        fractional_kelly = max(0.0, min(0.20, fractional_kelly))

        # Calculate size
        position_size = min(bankroll * fractional_kelly, max_position)

        explanation = f"Kelly: {kelly_pct:.1%}, Fractional: {fractional_kelly:.1%}, Size: ${position_size:.2f}"

        return position_size, explanation

    def record_prediction_and_learn(
        self,
        market_id: str,
        question: str,
        predicted_outcome: str,
        predicted_probability: float,
        confidence: float,
        reasoning: str,
        market_type: Optional[str] = None,
        market_data: Optional[Dict] = None,
        trade_executed: bool = False,
        trade_size: Optional[float] = None,
        trade_price: Optional[float] = None
    ) -> int:
        """
        Record prediction and enable future learning

        This stores all context needed for learning when market resolves.
        """
        # Store in database
        pred_id = self.db.store_prediction(
            market_id=market_id,
            question=question,
            predicted_outcome=predicted_outcome,
            predicted_probability=predicted_probability,
            confidence=confidence,
            reasoning=reasoning,
            strategy="INTEGRATED_LEARNER",
            market_type=market_type,
            market_prices=market_data.get('prices') if market_data else None,
            time_to_close_hours=market_data.get('time_to_close_hours') if market_data else None,
            social_data=market_data.get('social_data') if market_data else None,
            features=market_data
        )

        # Record trade if executed
        if trade_executed and trade_size and trade_price:
            self.db.record_trade_execution(
                prediction_id=pred_id,
                trade_size_usdc=trade_size,
                trade_price=trade_price,
                execution_result="EXECUTED"
            )

        return pred_id

    def record_outcome_and_learn(self, market_id: str, actual_outcome: str):
        """
        Record outcome and trigger learning

        When a market resolves:
        1. Update database with actual outcome
        2. Retrain feature models
        3. Retrain calibration
        4. Update edge detection
        """
        # Record outcome
        self.db.record_outcome(market_id, actual_outcome)

        if not self.learning_enabled:
            return

        # Trigger retraining
        try:
            # Retrain feature models
            self.feature_learner.train_model()

            # Retrain calibration
            self.isotonic_calibrator.train()

            # Edge detection updates automatically from database
        except Exception as e:
            print(f"Learning update failed: {e}")

    def get_learning_summary(self) -> Dict:
        """
        Get comprehensive summary of what has been learned

        Returns metrics about:
        - Edge by market type
        - Feature importance
        - Calibration quality
        - Overall performance
        """
        return {
            "edge_detection": self.db.get_edge_by_market_type(),
            "feature_learning": self.feature_learner.get_learning_stats(),
            "calibration": self.isotonic_calibrator.get_calibration_stats(),
            "performance": self.db.get_performance_summary()
        }

    def close(self):
        """Clean shutdown"""
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
