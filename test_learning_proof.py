#!/usr/bin/env python3
"""
Scientific Test: Does the Learning System Actually Learn?

Tests:
1. Calibration improvement over time (Brier score)
2. Edge detection accuracy
3. Kelly sizing vs fixed sizing
4. Market selection improvement

Hypothesis: Learning system improves prediction accuracy over time
Null hypothesis: No improvement (random walk)

Statistical rigor:
- Sample size calculations
- Confidence intervals
- Control vs treatment comparison
"""

import sys
import os
import numpy as np
from typing import List, Tuple
import json

os.chdir('/home/tony/Dev/agents')
sys.path.insert(0, '/home/tony/Dev/agents')

from agents.learning.trade_history import TradeHistoryDB
from agents.learning.calibration import CalibrationTracker

print("=" * 80)
print("SCIENTIFIC TEST: DOES THE LEARNING SYSTEM ACTUALLY LEARN?")
print("=" * 80)
print()

# Clean slate
import os
if os.path.exists("/tmp/test_learning_proof.db"):
    os.remove("/tmp/test_learning_proof.db")

db = TradeHistoryDB(db_path="/tmp/test_learning_proof.db")
calibration = CalibrationTracker(db)

print("EXPERIMENTAL DESIGN")
print("-" * 80)
print("Simulating 100 predictions over time:")
print("  - First 50: Bot with no calibration (baseline)")
print("  - Last 50: Bot WITH calibration learning")
print("  - Same underlying prediction quality")
print("  - Measure: Does Brier score improve?")
print()

# Simulate a bot that's systematically overconfident by 20%
# TRUE skill: When it says 70%, it's really 50%
# Question: Can the learning system detect and correct this bias?

def simulate_outcome(true_probability: float) -> str:
    """Simulate market outcome based on true probability"""
    return "Yes" if np.random.random() < true_probability else "No"

def bot_raw_prediction(market_difficulty: float) -> Tuple[float, float]:
    """
    Simulate bot's raw prediction

    market_difficulty: 0.0 = easy (bot is 80% accurate), 1.0 = hard (50% accurate)

    Returns: (raw_confidence, true_probability)
    """
    # Bot's true skill varies by difficulty
    true_probability = 0.5 + (0.3 * (1 - market_difficulty)) * np.random.choice([-1, 1])
    true_probability = max(0.1, min(0.9, true_probability))

    # Bot is systematically overconfident by 20%
    # If true probability is 60%, bot predicts 80%
    raw_confidence = min(0.95, true_probability + 0.20)

    return raw_confidence, true_probability

print("PHASE 1: UNCALIBRATED BOT (Predictions 1-50)")
print("-" * 80)

brier_scores_uncalibrated = []
predictions_phase1 = []

for i in range(50):
    # Random market difficulty
    difficulty = np.random.random()

    raw_confidence, true_prob = bot_raw_prediction(difficulty)

    # NO CALIBRATION - use raw confidence
    used_confidence = raw_confidence

    # Predict based on confidence
    predicted_outcome = "Yes" if used_confidence > 0.5 else "No"
    predicted_probability = used_confidence if predicted_outcome == "Yes" else (1 - used_confidence)

    # Simulate actual outcome
    actual_outcome = simulate_outcome(true_prob)

    # Store prediction
    market_id = f"uncalibrated_{i}"
    pred_id = db.store_prediction(
        market_id=market_id,
        question=f"Test market {i}",
        predicted_outcome=predicted_outcome,
        predicted_probability=predicted_probability,
        confidence=used_confidence,
        reasoning="Uncalibrated prediction",
        strategy="NO_CALIBRATION",
        market_type="test",
        time_to_close_hours=24
    )

    # Record outcome
    db.record_outcome(market_id, actual_outcome)

    # Calculate Brier score for this prediction
    was_correct = (predicted_outcome == actual_outcome)
    brier = (predicted_probability - (1.0 if was_correct else 0.0)) ** 2
    brier_scores_uncalibrated.append(brier)

    predictions_phase1.append({
        "raw_confidence": raw_confidence,
        "used_confidence": used_confidence,
        "true_prob": true_prob,
        "predicted": predicted_outcome,
        "actual": actual_outcome,
        "correct": was_correct
    })

avg_brier_uncalibrated = np.mean(brier_scores_uncalibrated)
win_rate_uncalibrated = np.mean([p["correct"] for p in predictions_phase1])

print(f"Results:")
print(f"  Average Brier Score: {avg_brier_uncalibrated:.4f}")
print(f"  Win Rate: {win_rate_uncalibrated:.1%}")
print(f"  Average Overconfidence: {np.mean([p['used_confidence'] - p['true_prob'] for p in predictions_phase1]):.1%}")
print()

print("PHASE 2: CALIBRATED BOT (Predictions 51-100)")
print("-" * 80)
print("Now applying calibration based on Phase 1 data...")
print()

brier_scores_calibrated = []
predictions_phase2 = []

for i in range(50, 100):
    # Same market difficulty distribution
    difficulty = np.random.random()

    raw_confidence, true_prob = bot_raw_prediction(difficulty)

    # WITH CALIBRATION - adjust based on historical performance
    used_confidence = calibration.calibrate_confidence(
        raw_confidence,
        market_type="test",
        strategy="NO_CALIBRATION"
    )

    # Predict based on CALIBRATED confidence
    predicted_outcome = "Yes" if used_confidence > 0.5 else "No"
    predicted_probability = used_confidence if predicted_outcome == "Yes" else (1 - used_confidence)

    # Simulate actual outcome
    actual_outcome = simulate_outcome(true_prob)

    # Store prediction
    market_id = f"calibrated_{i}"
    pred_id = db.store_prediction(
        market_id=market_id,
        question=f"Test market {i}",
        predicted_outcome=predicted_outcome,
        predicted_probability=predicted_probability,
        confidence=used_confidence,
        reasoning="Calibrated prediction",
        strategy="WITH_CALIBRATION",
        market_type="test",
        time_to_close_hours=24
    )

    # Record outcome
    db.record_outcome(market_id, actual_outcome)

    # Calculate Brier score
    was_correct = (predicted_outcome == actual_outcome)
    brier = (predicted_probability - (1.0 if was_correct else 0.0)) ** 2
    brier_scores_calibrated.append(brier)

    predictions_phase2.append({
        "raw_confidence": raw_confidence,
        "used_confidence": used_confidence,
        "true_prob": true_prob,
        "predicted": predicted_outcome,
        "actual": actual_outcome,
        "correct": was_correct,
        "calibration_adjustment": used_confidence - raw_confidence
    })

avg_brier_calibrated = np.mean(brier_scores_calibrated)
win_rate_calibrated = np.mean([p["correct"] for p in predictions_phase2])
avg_adjustment = np.mean([p["calibration_adjustment"] for p in predictions_phase2])

print(f"Results:")
print(f"  Average Brier Score: {avg_brier_calibrated:.4f}")
print(f"  Win Rate: {win_rate_calibrated:.1%}")
print(f"  Average Calibration Adjustment: {avg_adjustment:+.1%}")
print(f"  Average Overconfidence After Calibration: {np.mean([p['used_confidence'] - p['true_prob'] for p in predictions_phase2]):.1%}")
print()

# Statistical significance test
print("=" * 80)
print("STATISTICAL ANALYSIS")
print("=" * 80)
print()

print("HYPOTHESIS TEST: Did calibration improve prediction accuracy?")
print("-" * 80)

improvement = avg_brier_uncalibrated - avg_brier_calibrated
improvement_pct = (improvement / avg_brier_uncalibrated) * 100

print(f"Brier Score Improvement: {improvement:.4f} ({improvement_pct:+.1f}%)")
print()

# Calculate standard error and confidence interval
se_uncalibrated = np.std(brier_scores_uncalibrated) / np.sqrt(len(brier_scores_uncalibrated))
se_calibrated = np.std(brier_scores_calibrated) / np.sqrt(len(brier_scores_calibrated))

ci_95_uncalibrated = 1.96 * se_uncalibrated
ci_95_calibrated = 1.96 * se_calibrated

print(f"Uncalibrated: {avg_brier_uncalibrated:.4f} ± {ci_95_uncalibrated:.4f} (95% CI)")
print(f"Calibrated:   {avg_brier_calibrated:.4f} ± {ci_95_calibrated:.4f} (95% CI)")
print()

# T-test
from scipy import stats
t_stat, p_value = stats.ttest_ind(brier_scores_uncalibrated, brier_scores_calibrated)
print(f"T-statistic: {t_stat:.3f}")
print(f"P-value: {p_value:.4f}")
print()

if p_value < 0.05:
    print("✅ RESULT: Statistically significant improvement (p < 0.05)")
    print("   Reject null hypothesis: Learning system DOES improve accuracy")
else:
    print("❌ RESULT: Not statistically significant (p >= 0.05)")
    print("   Cannot reject null hypothesis: No evidence of improvement")
print()

# Effect size (Cohen's d)
pooled_std = np.sqrt((np.var(brier_scores_uncalibrated) + np.var(brier_scores_calibrated)) / 2)
cohens_d = improvement / pooled_std
print(f"Effect Size (Cohen's d): {cohens_d:.3f}")
if abs(cohens_d) < 0.2:
    print("   Interpretation: Small effect")
elif abs(cohens_d) < 0.5:
    print("   Interpretation: Medium effect")
else:
    print("   Interpretation: Large effect")
print()

# Calibration curve analysis
print("=" * 80)
print("CALIBRATION CURVE ANALYSIS")
print("=" * 80)
print()

stats = calibration.get_calibration_stats(strategy="NO_CALIBRATION")
if stats:
    print("Phase 1 (Uncalibrated):")
    print(f"  Brier Score: {stats.brier_score:.4f}")
    print(f"  Overconfidence Bias: {stats.average_bias:+.1%}")
    print()

stats2 = calibration.get_calibration_stats(strategy="WITH_CALIBRATION")
if stats2:
    print("Phase 2 (Calibrated):")
    print(f"  Brier Score: {stats2.brier_score:.4f}")
    print(f"  Overconfidence Bias: {stats2.average_bias:+.1%}")
    print()

# Failure modes
print("=" * 80)
print("FAILURE MODES & LIMITATIONS")
print("=" * 80)
print()

print("1. SAMPLE SIZE")
print(f"   - Current: {len(brier_scores_uncalibrated) + len(brier_scores_calibrated)} predictions")
print(f"   - Needed for robust calibration: 200+ predictions")
print(f"   - Status: {'✅ Sufficient' if len(brier_scores_uncalibrated) + len(brier_scores_calibrated) >= 200 else '⚠️ Marginal'}")
print()

print("2. OVERFITTING RISK")
print("   - Learning from random noise vs true patterns")
print("   - Mitigation: Separate train/test splits (not implemented in demo)")
print(f"   - Status: ⚠️ Risk present with small sample")
print()

print("3. REGIME CHANGE")
print("   - Market conditions may shift over time")
print("   - Past calibration may not apply to future")
print(f"   - Status: ⚠️ Cannot detect regime changes yet")
print()

print("4. SURVIVORSHIP BIAS")
print("   - Only seeing predictions that were made")
print("   - May skip markets where we'd be most wrong")
print(f"   - Status: ⚠️ Present in edge detection")
print()

# Summary
print("=" * 80)
print("CONCLUSION: CONDITIONAL ASSESSMENT")
print("=" * 80)
print()

print("IF the p-value < 0.05 AND effect size > 0.3:")
print(f"  → Evidence supports learning hypothesis")
print(f"  → Confidence: 70-80% (limited by sample size)")
print()

print("IF the p-value >= 0.05 OR effect size < 0.2:")
print(f"  → Insufficient evidence of learning")
print(f"  → May need more data or different approach")
print()

print("ACTUAL RESULTS:")
print(f"  P-value: {p_value:.4f} {'< 0.05 ✅' if p_value < 0.05 else '>= 0.05 ❌'}")
print(f"  Effect size: {cohens_d:.3f} {'> 0.3 ✅' if abs(cohens_d) > 0.3 else '< 0.3 ❌'}")
print()

if p_value < 0.05 and abs(cohens_d) > 0.3:
    print("VERDICT: Evidence supports learning (with caveats)")
    print()
    print("Caveats:")
    print("  1. Simulated data, not real markets")
    print("  2. Small sample size (100 predictions)")
    print("  3. No regime changes tested")
    print("  4. Assumes stationarity")
else:
    print("VERDICT: Insufficient evidence of learning")
    print()
    print("Possible explanations:")
    print("  1. Sample size too small")
    print("  2. Calibration mechanism ineffective")
    print("  3. Random variation masking signal")
    print("  4. Test design flawed")

print()
print("=" * 80)

# Save detailed results
results = {
    "uncalibrated": {
        "brier_score": float(avg_brier_uncalibrated),
        "win_rate": float(win_rate_uncalibrated),
        "predictions": predictions_phase1
    },
    "calibrated": {
        "brier_score": float(avg_brier_calibrated),
        "win_rate": float(win_rate_calibrated),
        "predictions": predictions_phase2
    },
    "statistics": {
        "improvement": float(improvement),
        "improvement_pct": float(improvement_pct),
        "t_statistic": float(t_stat),
        "p_value": float(p_value),
        "cohens_d": float(cohens_d)
    }
}

with open("/tmp/learning_test_results.json", "w") as f:
    json.dump(results, f, indent=2)

print()
print("Detailed results saved to: /tmp/learning_test_results.json")
print("Database saved to: /tmp/test_learning_proof.db")
print()

db.close()
