# Self-Learning Trading System Architecture

## Vision
Build a trading bot that learns from every trade, calibrates its confidence, and continuously improves through meta-learning and feedback loops.

## Core Principles
1. **Every trade is a learning opportunity** - Track prediction vs outcome
2. **Probabilistic thinking** - Calibrated confidence, not false certainty
3. **Meta-cognition** - Know what you know, and what you don't
4. **Adversarial testing** - Red team every decision
5. **Continuous improvement** - Measure, learn, adapt

---

## System Architecture

### Layer 1: Learning & Memory
**Persistent knowledge that accumulates over time**

#### 1.1 Trade History Database (`agents/learning/trade_history.py`)
```python
class TradeHistoryDB:
    """Persistent database of all predictions and outcomes"""

    - store_prediction(market_id, prediction, confidence, reasoning)
    - store_outcome(market_id, actual_outcome, resolution_date)
    - get_prediction_accuracy(time_range, market_type, strategy)
    - get_similar_past_markets(current_market) -> vector search
```

**Schema:**
```
trades:
  - id, timestamp, market_id, question
  - predicted_outcome, confidence, actual_outcome
  - market_type (crypto, politics, sports, etc.)
  - strategy_used (AI, arbitrage, hybrid)
  - features: {social_sentiment, volume, time_to_close, etc.}
  - reasoning: full analysis text
  - result: win/loss/pending
  - profit_loss: actual P&L
```

#### 1.2 Calibration Tracker (`agents/learning/calibration.py`)
```python
class CalibrationTracker:
    """Track how well-calibrated our probabilities are"""

    - calculate_brier_score(predictions, outcomes)
    - get_calibration_curve() -> plot predicted vs actual
    - identify_overconfidence_bias()
    - identify_underconfidence_bias()
    - suggest_confidence_adjustment(raw_confidence) -> calibrated_confidence
```

**Key Metrics:**
- **Brier Score**: Mean squared error of probability predictions (lower is better)
- **Calibration Curve**: Do 70% predictions happen 70% of the time?
- **Sharpness**: How confident are we (high variance = decisive)
- **Resolution**: Can we distinguish likely from unlikely events?

#### 1.3 Pattern Recognition (`agents/learning/pattern_recognition.py`)
```python
class PatternRecognizer:
    """Learn which signals are actually predictive"""

    - identify_predictive_features(market_type)
    - learn_winning_patterns()
    - detect_regime_changes() -> market conditions that shift
    - find_edge_conditions() -> when do we have an edge?
```

**Patterns to Learn:**
- Which social sentiment levels predict outcomes
- Which market types we're good/bad at
- Optimal time-to-close windows
- Volume/liquidity thresholds that matter

#### 1.4 Market Knowledge Base (`agents/learning/market_database.py`)
```python
class MarketKnowledgeBase:
    """ChromaDB of resolved markets for similarity search"""

    - index_resolved_market(market, outcome, analysis)
    - find_similar_markets(current_market, n=10)
    - extract_lessons_from_similar(similar_markets)
    - build_base_rate(market_type, features)
```

---

### Layer 2: Multi-Agent Reasoning
**Multiple perspectives before every trade**

#### 2.1 Prediction Agent (`agents/reasoning/predictor.py`)
```python
class PredictionAgent:
    """Makes initial probability prediction"""

    - analyze_market(market, social_data, news)
    - search_similar_past_markets() -> base rates
    - generate_prediction(outcome_probabilities, reasoning)
    - provide_evidence(supporting, contradicting)
```

**Output:**
```
{
  "prediction": {"Yes": 0.35, "No": 0.65},
  "confidence": 0.7,
  "reasoning": "...",
  "supporting_evidence": [...],
  "contradicting_evidence": [...]
}
```

#### 2.2 Critique Agent (`agents/reasoning/critic.py`)
```python
class CritiqueAgent:
    """Red team challenges the prediction"""

    - identify_assumptions(prediction)
    - challenge_reasoning(prediction)
    - propose_alternative_hypotheses()
    - assess_blind_spots()
    - rate_confidence_appropriateness()
```

**Key Questions:**
- What would make this prediction wrong?
- What evidence contradicts this view?
- Are we anchoring on recent events?
- Is our confidence justified by the evidence?
- What are we not considering?

#### 2.3 Synthesis Agent (`agents/reasoning/synthesizer.py`)
```python
class SynthesisAgent:
    """Combines prediction and critique into final decision"""

    - reconcile_perspectives(prediction, critique)
    - adjust_confidence_based_on_critique()
    - apply_calibration_corrections()
    - make_final_decision(trade_or_skip)
    - explain_decision()
```

#### 2.4 Confidence Calibrator (`agents/reasoning/confidence_calibrator.py`)
```python
class ConfidenceCalibrator:
    """Adjust confidence based on historical calibration"""

    - load_historical_calibration()
    - adjust_confidence(raw_confidence, market_type, features)
    - apply_underconfidence_correction()
    - apply_overconfidence_correction()
```

**Example:**
- Raw confidence: 0.8
- Historical: When we say 0.8, we're right 0.6 of the time
- Calibrated: Adjust to 0.6

---

### Layer 3: Meta-Learning
**Learning about learning - what strategies work when**

#### 3.1 Strategy Evaluator (`agents/meta/strategy_evaluator.py`)
```python
class StrategyEvaluator:
    """Evaluate performance of different strategies"""

    - compare_strategies(time_range) -> ROI by strategy
    - identify_best_strategy_by_context(market_type, conditions)
    - measure_strategy_edge(strategy, conditions)
    - recommend_strategy_weights()
```

**Strategies to Evaluate:**
- Pure AI prediction
- Arbitrage
- Social sentiment following
- Contrarian (fade the market)
- Momentum following
- Base rate + adjustment

#### 3.2 Edge Detector (`agents/meta/edge_detector.py`)
```python
class EdgeDetector:
    """Identify where we actually have an edge"""

    - calculate_edge_by_market_type()
    - calculate_edge_by_time_to_close()
    - calculate_edge_by_social_sentiment()
    - identify_no_edge_conditions() -> skip these
```

**Edge = Expected Value > 0**
- Track ROI by market type, time window, sentiment level
- Identify conditions where we're profitable
- Identify conditions where we're losing
- Skip markets where we have no edge

#### 3.3 Performance Tracker (`agents/meta/performance_tracker.py`)
```python
class PerformanceTracker:
    """Track comprehensive performance metrics"""

    - calculate_sharpe_ratio()
    - calculate_win_rate_by_context()
    - calculate_average_roi_by_context()
    - identify_improvement_areas()
    - track_learning_curve() -> are we getting better?
```

---

### Layer 4: Adaptive Execution
**Dynamic strategy based on meta-learning**

#### 4.1 Position Sizer (`agents/adaptive/position_sizer.py`)
```python
class PositionSizer:
    """Kelly Criterion + Edge-aware position sizing"""

    - calculate_kelly_size(probability, price, edge)
    - apply_safety_factor() -> fractional Kelly
    - adjust_for_uncertainty(confidence)
    - respect_risk_limits()
```

**Formula:**
```
Kelly % = (edge / odds)
Fractional Kelly = Kelly % * safety_factor
Adjusted for confidence = Fractional Kelly * confidence_score
```

#### 4.2 Market Selector (`agents/adaptive/market_selector.py`)
```python
class MarketSelector:
    """Intelligently skip markets where we have no edge"""

    - estimate_edge(market)
    - check_historical_performance(similar_markets)
    - calculate_confidence_threshold()
    - decide_trade_or_skip()
```

**Skip Conditions:**
- No historical edge in this market type
- Confidence too low (uncertain)
- Similar past markets were unprofitable
- Outside our circle of competence

#### 4.3 Strategy Router (`agents/adaptive/strategy_router.py`)
```python
class StrategyRouter:
    """Route to best strategy based on context"""

    - detect_market_context(market)
    - select_optimal_strategy(context)
    - blend_strategies(weights_from_meta_learning)
    - execute_with_chosen_strategy()
```

---

## Data Flow

```
1. NEW MARKET ARRIVES
   ↓
2. MARKET SELECTOR
   - Check historical edge
   - Decide: analyze or skip
   ↓
3. MULTI-AGENT REASONING
   - Predictor: Make prediction
   - Critic: Challenge prediction
   - Synthesizer: Final decision
   ↓
4. CONFIDENCE CALIBRATION
   - Load historical calibration
   - Adjust confidence
   ↓
5. EDGE DETECTOR
   - Estimate expected value
   - Decide: trade or skip
   ↓
6. POSITION SIZER
   - Calculate Kelly size
   - Adjust for confidence
   ↓
7. EXECUTE TRADE
   ↓
8. TRADE HISTORY DATABASE
   - Store prediction + reasoning
   ↓
9. [WAIT FOR RESOLUTION]
   ↓
10. POST-TRADE ANALYSIS
    - Compare prediction vs outcome
    - Calculate Brier score
    - Update calibration
    - Learn patterns
    ↓
11. META-LEARNING
    - Update strategy performance
    - Update edge detection
    - Improve for next trade
```

---

## Implementation Plan

### Phase 1: Learning Infrastructure (Foundation)
1. ✅ Design architecture
2. ⏳ Build TradeHistoryDB with SQLite + vector store
3. ⏳ Build CalibrationTracker
4. ⏳ Build MarketKnowledgeBase with ChromaDB

### Phase 2: Multi-Agent Reasoning
1. Build PredictionAgent (refactor existing)
2. Build CritiqueAgent (new)
3. Build SynthesisAgent (new)
4. Build ConfidenceCalibrator

### Phase 3: Meta-Learning
1. Build StrategyEvaluator
2. Build EdgeDetector
3. Build PerformanceTracker

### Phase 4: Adaptive Execution
1. Build PositionSizer (Kelly)
2. Build MarketSelector (skip low-edge)
3. Build StrategyRouter

### Phase 5: Integration & Testing
1. Wire all components together
2. Backtest on historical data
3. Dry run for 1 week
4. Analyze learning curves
5. Go live with small positions

---

## Success Metrics

### Learning Metrics
- **Brier Score** improving over time (lower is better)
- **Calibration** curve approaches diagonal (predicted = actual)
- **Edge Detection** accuracy (correctly identify profitable markets)

### Performance Metrics
- **ROI** positive and improving
- **Sharpe Ratio** > 1.0 (risk-adjusted returns)
- **Win Rate** calibrated to confidence levels
- **Drawdown** controlled and recovering

### Meta Metrics
- **Learning Rate** positive (getting better over time)
- **Circle of Competence** expanding (profitable in more market types)
- **Skip Rate** optimal (not trading unprofitable markets)

---

## Technology Stack

- **SQLite** - Trade history database (simple, persistent)
- **ChromaDB** - Vector store for market similarity
- **Pandas** - Data analysis and metrics
- **NumPy** - Numerical calculations (Brier, Kelly)
- **Matplotlib** - Visualization (calibration curves, learning curves)
- **OpenAI GPT-4** - Reasoning agents
- **Grok** - Alternative reasoning agent
- **LangChain** - Agent orchestration

---

## Key Innovations

1. **Multi-Agent Verification** - Never trust a single LLM
2. **Persistent Memory** - Learn from every trade
3. **Calibration** - Know when we're overconfident
4. **Meta-Learning** - Learn which strategies work when
5. **Edge-Aware Execution** - Only trade when we have an edge
6. **Continuous Improvement** - System gets smarter over time

---

## Next Steps

Start with Phase 1: Build the learning infrastructure.
This is the foundation everything else builds on.
