"""
Calibration Tracker - Measure and Improve Prediction Accuracy

Tracks how well-calibrated our probability predictions are:
- When we say 70%, does it happen 70% of the time?
- Are we overconfident or underconfident?
- How should we adjust raw confidence scores?
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CalibrationStats:
    """Statistics about prediction calibration"""
    brier_score: float  # Lower is better (0 = perfect)
    is_overconfident: bool  # Predicting higher than actual
    is_underconfident: bool  # Predicting lower than actual
    average_bias: float  # Positive = overconfident, negative = underconfident
    calibration_curve: List[Tuple[float, float, int]]  # (predicted, actual, count)
    sample_size: int


class CalibrationTracker:
    """Track and analyze prediction calibration"""

    def __init__(self, trade_history_db):
        self.db = trade_history_db

    def get_calibration_stats(
        self,
        market_type: Optional[str] = None,
        strategy: Optional[str] = None,
        min_samples: int = 10
    ) -> Optional[CalibrationStats]:
        """
        Get comprehensive calibration statistics

        Args:
            market_type: Filter by market type
            strategy: Filter by strategy
            min_samples: Minimum resolved predictions needed

        Returns:
            CalibrationStats or None if insufficient data
        """
        # Get calibration curve from database
        curve = self.db.get_calibration_curve()

        if not curve:
            return None

        total_samples = sum(count for _, _, count in curve)

        if total_samples < min_samples:
            return None

        # Calculate Brier score
        brier_score = self.db.calculate_brier_score(market_type, strategy)

        if brier_score is None:
            return None

        # Calculate bias (predicted - actual)
        biases = []
        for predicted, actual, count in curve:
            if actual is not None and count > 0:
                bias = predicted - actual
                biases.extend([bias] * count)

        if not biases:
            return None

        average_bias = np.mean(biases)
        is_overconfident = average_bias > 0.05  # More than 5% overconfident
        is_underconfident = average_bias < -0.05  # More than 5% underconfident

        return CalibrationStats(
            brier_score=brier_score,
            is_overconfident=is_overconfident,
            is_underconfident=is_underconfident,
            average_bias=average_bias,
            calibration_curve=curve,
            sample_size=total_samples
        )

    def calibrate_confidence(
        self,
        raw_confidence: float,
        market_type: Optional[str] = None,
        strategy: Optional[str] = None
    ) -> float:
        """
        Adjust raw confidence based on historical calibration

        If we're historically overconfident, reduce confidence.
        If we're historically underconfident, increase confidence.

        Args:
            raw_confidence: The model's raw confidence (0.0 - 1.0)
            market_type: Context for calibration
            strategy: Context for calibration

        Returns:
            Calibrated confidence (0.0 - 1.0)
        """
        stats = self.get_calibration_stats(market_type, strategy)

        if stats is None or stats.sample_size < 20:
            # Not enough data, return raw confidence
            return raw_confidence

        # Find the bucket this confidence falls into
        curve = stats.calibration_curve

        # Find nearest calibration point
        nearest = min(curve, key=lambda x: abs(x[0] - raw_confidence))
        predicted_bucket, actual_accuracy, sample_count = nearest

        if sample_count < 5:
            # Not enough samples in this bucket
            return raw_confidence

        if actual_accuracy is None:
            return raw_confidence

        # Blend between raw and calibrated based on sample size
        # More samples = more trust in calibration
        blend_weight = min(sample_count / 50.0, 0.8)  # Max 80% weight on calibration

        calibrated = (blend_weight * actual_accuracy) + ((1 - blend_weight) * raw_confidence)

        # Clamp to valid range
        return max(0.01, min(0.99, calibrated))

    def should_trade(
        self,
        confidence: float,
        edge_estimate: float,
        market_type: Optional[str] = None,
        min_confidence: float = 0.6,
        min_edge: float = 0.05
    ) -> Tuple[bool, str]:
        """
        Decide whether to trade based on calibrated confidence and edge

        Args:
            confidence: Confidence in prediction (after calibration)
            edge_estimate: Estimated edge (expected profit %)
            market_type: Type of market
            min_confidence: Minimum confidence threshold
            min_edge: Minimum edge threshold

        Returns:
            (should_trade, reason)
        """
        # Check historical performance in this market type
        edge_by_type = self.db.get_edge_by_market_type()

        if market_type and market_type in edge_by_type:
            historical_edge = edge_by_type[market_type]

            if not historical_edge['has_edge']:
                return (
                    False,
                    f"No historical edge in {market_type} markets "
                    f"(avg P&L: ${historical_edge['avg_pnl_per_trade']:.2f})"
                )

        # Check confidence threshold
        if confidence < min_confidence:
            return (
                False,
                f"Confidence {confidence:.1%} below threshold {min_confidence:.1%}"
            )

        # Check edge threshold
        if edge_estimate < min_edge:
            return (
                False,
                f"Edge {edge_estimate:.1%} below threshold {min_edge:.1%}"
            )

        # Get calibration stats to check if we're reliable at this confidence level
        stats = self.get_calibration_stats(market_type=market_type)

        if stats and stats.sample_size >= 20:
            # Find accuracy at this confidence level
            for predicted, actual, count in stats.calibration_curve:
                if abs(predicted - confidence) < 0.15 and count >= 5:  # Within 15% bucket
                    if actual is not None and actual < 0.55:  # Historically poor at this level
                        return (
                            False,
                            f"Poor historical accuracy ({actual:.1%}) at this confidence level"
                        )

        return (True, f"Confidence {confidence:.1%}, Edge {edge_estimate:.1%}")

    def get_optimal_bet_size(
        self,
        probability: float,
        market_price: float,
        bankroll: float,
        kelly_fraction: float = 0.25
    ) -> float:
        """
        Calculate optimal bet size using fractional Kelly Criterion

        Kelly % = (probability * odds - (1 - probability)) / odds
        Where odds = (1 / price) - 1

        Args:
            probability: Our calibrated probability of winning
            market_price: Current market price
            bankroll: Total bankroll
            kelly_fraction: Fraction of Kelly to bet (0.25 = quarter Kelly)

        Returns:
            Optimal bet size in USDC
        """
        # Calculate odds
        if market_price >= 1.0 or market_price <= 0.0:
            return 0.0

        odds = (1.0 / market_price) - 1.0

        # Calculate Kelly percentage
        kelly_pct = (probability * odds - (1 - probability)) / odds

        # Apply safety fraction
        fractional_kelly = kelly_pct * kelly_fraction

        # Clamp to reasonable range (0-20% of bankroll per trade)
        fractional_kelly = max(0.0, min(0.20, fractional_kelly))

        # Calculate bet size
        bet_size = bankroll * fractional_kelly

        return bet_size

    def generate_report(
        self,
        market_type: Optional[str] = None,
        strategy: Optional[str] = None
    ) -> str:
        """Generate a human-readable calibration report"""
        stats = self.get_calibration_stats(market_type, strategy)

        if stats is None:
            return "Insufficient data for calibration report (need at least 10 resolved predictions)"

        report = []
        report.append("=" * 70)
        report.append("CALIBRATION REPORT")
        report.append("=" * 70)
        report.append("")

        report.append(f"Sample Size: {stats.sample_size} resolved predictions")
        report.append(f"Brier Score: {stats.brier_score:.4f} (lower is better, 0 = perfect)")
        report.append("")

        # Calibration assessment
        if stats.is_overconfident:
            report.append(f"⚠️  OVERCONFIDENT: Predictions are {abs(stats.average_bias):.1%} too high on average")
            report.append("   → Reduce confidence in future predictions")
        elif stats.is_underconfident:
            report.append(f"⚠️  UNDERCONFIDENT: Predictions are {abs(stats.average_bias):.1%} too low on average")
            report.append("   → Increase confidence in future predictions")
        else:
            report.append(f"✅ WELL-CALIBRATED: Average bias only {abs(stats.average_bias):.1%}")

        report.append("")
        report.append("Calibration Curve:")
        report.append(f"{'Predicted':>12} {'Actual':>12} {'Samples':>12} {'Status':>12}")
        report.append("-" * 50)

        for predicted, actual, count in stats.calibration_curve:
            if count > 0 and actual is not None:
                diff = abs(predicted - actual)
                status = "✅" if diff < 0.10 else "⚠️" if diff < 0.20 else "❌"
                report.append(
                    f"{predicted:>11.0%} {actual:>11.0%} {count:>12} {status:>12}"
                )

        report.append("")
        report.append("=" * 70)

        return "\n".join(report)
