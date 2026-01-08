#!/usr/bin/env python3
"""
Larger Sample Test: 500 predictions to see if learning signal emerges
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

# Clean slate
if os.path.exists("/tmp/test_learning_large.db"):
    os.remove("/tmp/test_learning_large.db")

db = TradeHistoryDB(db_path="/tmp/test_learning_large.db")
calibration = CalibrationTracker(db)

print("LARGE SAMPLE TEST: 500 PREDICTIONS")
print("=" * 80)
print()

def simulate_outcome(true_probability: float) -> str:
    return "Yes" if np.random.random() < true_probability else "No"

def bot_raw_prediction(market_difficulty: float) -> Tuple[float, float]:
    true_probability = 0.5 + (0.3 * (1 - market_difficulty)) * np.random.choice([-1, 1])
    true_probability = max(0.1, min(0.9, true_probability))

    # Systematic overconfidence by 15%
    raw_confidence = min(0.95, true_probability + 0.15)

    return raw_confidence, true_probability

# Phase 1: 250 uncalibrated predictions
print("Phase 1: Collecting 250 uncalibrated predictions...")
brier_uncalibrated = []
for i in range(250):
    difficulty = np.random.random()
    raw_confidence, true_prob = bot_raw_prediction(difficulty)

    predicted_outcome = "Yes" if raw_confidence > 0.5 else "No"
    predicted_probability = raw_confidence if predicted_outcome == "Yes" else (1 - raw_confidence)

    actual_outcome = simulate_outcome(true_prob)

    market_id = f"uncal_{i}"
    db.store_prediction(
        market_id=market_id,
        question=f"Market {i}",
        predicted_outcome=predicted_outcome,
        predicted_probability=predicted_probability,
        confidence=raw_confidence,
        reasoning="No calibration",
        strategy="UNCALIBRATED",
        market_type="test"
    )
    db.record_outcome(market_id, actual_outcome)

    was_correct = (predicted_outcome == actual_outcome)
    brier = (predicted_probability - (1.0 if was_correct else 0.0)) ** 2
    brier_uncalibrated.append(brier)

avg_brier_uncal = np.mean(brier_uncalibrated)
print(f"  Avg Brier: {avg_brier_uncal:.4f}")
print()

# Phase 2: 250 calibrated predictions
print("Phase 2: Testing 250 calibrated predictions...")
brier_calibrated = []
for i in range(250, 500):
    difficulty = np.random.random()
    raw_confidence, true_prob = bot_raw_prediction(difficulty)

    # Apply calibration
    calibrated_confidence = calibration.calibrate_confidence(
        raw_confidence,
        market_type="test",
        strategy="UNCALIBRATED"
    )

    predicted_outcome = "Yes" if calibrated_confidence > 0.5 else "No"
    predicted_probability = calibrated_confidence if predicted_outcome == "Yes" else (1 - calibrated_confidence)

    actual_outcome = simulate_outcome(true_prob)

    market_id = f"cal_{i}"
    db.store_prediction(
        market_id=market_id,
        question=f"Market {i}",
        predicted_outcome=predicted_outcome,
        predicted_probability=predicted_probability,
        confidence=calibrated_confidence,
        reasoning="With calibration",
        strategy="CALIBRATED",
        market_type="test"
    )
    db.record_outcome(market_id, actual_outcome)

    was_correct = (predicted_outcome == actual_outcome)
    brier = (predicted_probability - (1.0 if was_correct else 0.0)) ** 2
    brier_calibrated.append(brier)

avg_brier_cal = np.mean(brier_calibrated)
print(f"  Avg Brier: {avg_brier_cal:.4f}")
print()

# Statistical test
from scipy import stats
improvement = avg_brier_uncal - avg_brier_cal
improvement_pct = (improvement / avg_brier_uncal) * 100
t_stat, p_value = stats.ttest_ind(brier_uncalibrated, brier_calibrated)

pooled_std = np.sqrt((np.var(brier_uncalibrated) + np.var(brier_calibrated)) / 2)
cohens_d = improvement / pooled_std

print("RESULTS:")
print("=" * 80)
print(f"Improvement: {improvement:.4f} ({improvement_pct:+.1f}%)")
print(f"T-statistic: {t_stat:.3f}")
print(f"P-value: {p_value:.4f}")
print(f"Cohen's d: {cohens_d:.3f}")
print()

if p_value < 0.05:
    print("✅ STATISTICALLY SIGNIFICANT (p < 0.05)")
    if abs(cohens_d) > 0.5:
        print(f"✅ LARGE EFFECT SIZE (|d| = {abs(cohens_d):.2f} > 0.5)")
    elif abs(cohens_d) > 0.3:
        print(f"⚠️  MEDIUM EFFECT SIZE (|d| = {abs(cohens_d):.2f})")
    else:
        print(f"⚠️  SMALL EFFECT SIZE (|d| = {abs(cohens_d):.2f})")
else:
    print("❌ NOT STATISTICALLY SIGNIFICANT (p >= 0.05)")

print()
print("=" * 80)

db.close()
