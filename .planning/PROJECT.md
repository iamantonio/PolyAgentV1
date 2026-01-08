# Polymarket Autonomous Trading Bot - LLM Forecasting Engine

## Vision

Build a single-model LLM forecasting engine with superforecaster-style prompting to generate accurate probability predictions for Polymarket markets. The system must prioritize forecast accuracy and robust risk management to prevent losing money on bad predictions.

**Priority**: Start with a simple, reliable MVP that validates the approach before adding complexity.

## Goals

1. **Primary**: Implement single-model LLM forecasting with superforecaster prompting that outperforms naive market participation
2. **Risk Management**: Integrate fractional Kelly position sizing (25% fraction, 2% max per market) to protect capital
3. **Validation**: Establish backtesting/paper trading workflow to validate predictions before risking real capital
4. **Integration**: Clean integration with existing codebase (`agents/application/executor.py`, `agents/copytrader/risk_kernel.py`)

## Non-Goals (v1)

- Multi-model ensemble systems (future enhancement)
- Real-time learning/calibration loops (future enhancement)
- Automated market discovery (use existing RAG filtering)
- Complex portfolio optimization (use existing risk kernel)

## Success Criteria

1. **Forecast Accuracy**: LLM predictions calibrated within ±10% of actual outcomes over 20+ resolved markets
2. **Edge Detection**: Positive expected value on 60%+ of trades (calculated edge > 0)
3. **Capital Preservation**: No single trade loses >2% of capital, daily loss limit at -5%
4. **Integration**: Works seamlessly with existing `RiskKernel` and `PositionTracker`

## Context

### Existing Codebase (Brownfield Project)

This is a **brownfield project** with existing sophisticated infrastructure:

**Strengths**:
- Layered hexagonal architecture with clear separation of concerns
- Production CopyTrader system (v2) with 20-test suite
- Pure functional `RiskKernel` (no I/O, deterministic)
- RAG-based market filtering with ChromaDB
- Multi-agent reasoning system (Predictor → Critic → Synthesizer)
- Position tracking with SQLite persistence
- Existing LLM integration in `agents/application/executor.py`

**Critical Issues** (from CONCERNS.md):
- Bare `except:` clauses in trade.py (lines 20, 24) - swallow all errors
- Debug code in production: `pdb.set_trace()` at polymarket.py:440
- Print statements instead of structured logging (25+ instances)
- <5% test coverage overall
- Infinite recursion risk in retry logic (trade.py:63-65)

**Key Architecture**:
```
Entry Point → Application Layer → Domain Layer → Integration Layer → Data Layer
               (executor.py)      (risk_kernel)    (polymarket.py)    (storage.py)
```

### User's Detailed Requirements

From user specification document:

**LLM Forecasting Module**:
```python
class LLMForecaster:
    def forecast_market(self, market_data: MarketData) -> ForecastResult:
        """
        Generate probability forecast using superforecaster prompting.

        Returns:
            - base_probability: Our estimated P(event)
            - confidence: 0-100 scale
            - reasoning: Chain of thought
            - sources: Data used in forecast
        """
```

**Position Sizing** (Fractional Kelly):
```
Kelly Fraction = 25% * (edge / variance)
Where edge = (our_prob - market_prob) * confidence_factor

Constraints:
- Max 2% capital per market
- Max 5% across correlated markets
- Max 3 concurrent positions
```

**Key Insight from User**: "The biggest risk is overconfidence. Fractional Kelly at 25% is critical for survival."

### Technical Stack

- **Python**: 3.9+ (existing), user prefers 3.11+
- **LLM**: Start with Claude Sonnet or GPT-4 (user's spec mentions both)
- **Existing Dependencies**: py-clob-client 0.17.5, Web3.py 6.11.0, Pydantic 2.8.2
- **Database**: SQLite (existing) or PostgreSQL/TimescaleDB (user's preference for production)

## Scope

### In Scope (v1)

1. **Core Forecasting Engine**:
   - Single LLM model (Claude Sonnet or GPT-4)
   - Superforecaster-style prompt engineering
   - Return: probability, confidence, reasoning
   - Basic input preprocessing (market description, context)

2. **Risk Integration**:
   - Fractional Kelly position sizing calculation
   - Integration with existing `RiskKernel` for approval
   - Position limits enforcement (2% per market, 5% correlated, 3 concurrent)

3. **Validation Framework**:
   - Paper trading mode (mock executor)
   - Track predictions vs outcomes
   - Basic performance metrics (accuracy, edge)

4. **Code Quality**:
   - Fix critical issues blocking production (pdb, bare except)
   - Add structured logging for forecaster
   - Unit tests for forecasting logic (aim for 80% coverage)

### Out of Scope (v1)

- Multi-model ensemble (future: Phase 2)
- Real-time calibration/learning (future: Phase 3)
- Advanced market discovery (use existing RAG)
- Portfolio optimization beyond basic Kelly (future)
- Production deployment (Phase 4)

## Constraints

1. **Risk First**: No real money trades until validated on 20+ resolved markets in paper trading
2. **Existing Architecture**: Must work with current layered hexagonal structure
3. **Backward Compatibility**: Don't break existing CopyTrader v2 system
4. **API Costs**: Monitor LLM token usage, optimize prompts
5. **Test Coverage**: New code must have 80%+ test coverage

## Open Questions

1. Which LLM model to start with? (Claude Sonnet 3.5 vs GPT-4)
   - Hypothesis A: Claude better for reasoning-heavy forecasting
   - Hypothesis B: GPT-4 more reliable for structured output
   - Evidence needed: Run parallel tests on 10 sample markets

2. How to handle time-sensitive markets?
   - Hypothesis A: Cache forecasts with TTL based on market close time
   - Hypothesis B: Always regenerate fresh forecasts
   - Evidence needed: Measure forecast stability over time

3. Should we refactor `agents/application/executor.py` or build new module?
   - Hypothesis A: Refactor existing (faster, maintains compatibility)
   - Hypothesis B: New module (cleaner separation, easier testing)
   - Evidence needed: Code audit of current executor.py coupling

## Risks & Mitigations

### Risk 1: Bad Predictions → Capital Loss
**Severity**: Critical
**Mitigation**:
- Fractional Kelly at 25% (not full Kelly)
- Strict position limits (2% per market)
- Paper trading validation (20+ markets)
- Daily stop loss (-5%)
- Hard kill switch (-20%)

**Falsification**: If losses exceed limits despite mitigations, we're mis-estimating edge or variance.

### Risk 2: Integration Breaks Existing System
**Severity**: High
**Mitigation**:
- Use adapter pattern (similar to ExecutorAdapter)
- Comprehensive integration tests
- Feature flag for new forecaster
- Keep existing executor.py as fallback

**Falsification**: If integration tests pass but production fails, our test coverage missed critical paths.

### Risk 3: LLM Costs Spiral Out of Control
**Severity**: Medium
**Mitigation**:
- Token usage monitoring
- Prompt optimization (remove redundant context)
- Set daily API budget limits
- Use cheaper models for preprocessing

**Falsification**: If costs remain high despite optimizations, our architecture requires too many LLM calls.

### Risk 4: Forecasts No Better Than Market
**Severity**: Critical
**Mitigation**:
- Establish baseline (random walk, market implied prob)
- Measure edge on historical data
- Require positive edge before real trades
- Consider multi-model ensemble if single model fails

**Falsification**: If edge remains ≤0 after prompt optimization, LLM forecasting may not work for this domain.

## Technical Approach

### Architecture Decision: Refactor vs New Module

**Option A: Refactor `agents/application/executor.py`**
- Pros: Faster, maintains existing integrations, leverages tested code
- Cons: High coupling risk, harder to test in isolation, technical debt accumulation
- Confidence: 40%

**Option B: New `agents/forecasting/llm_forecaster.py` module**
- Pros: Clean separation, easier testing, clear interface boundaries
- Cons: More upfront work, duplicate some existing logic, integration overhead
- Confidence: 60%

**Recommendation**: Option B (new module) IF integration complexity is manageable. Otherwise Option A.

**Evidence needed**:
1. Map current executor.py dependencies
2. Estimate integration test effort for new module
3. Prototype both approaches in parallel branches

### Data Flow (Proposed)

```
1. Market Selection
   ├─→ Existing RAG filtering (agents/connectors/chroma.py)
   └─→ Filter tradeable markets (agents/polymarket/polymarket.py)

2. Forecasting (NEW)
   ├─→ LLMForecaster.forecast_market()
   │   ├─→ Prepare market context
   │   ├─→ Superforecaster prompt
   │   ├─→ LLM API call (Claude/GPT-4)
   │   └─→ Parse: probability, confidence, reasoning
   └─→ Output: ForecastResult

3. Position Sizing (NEW)
   ├─→ Calculate edge: (our_prob - market_prob) * confidence
   ├─→ Kelly fraction: 0.25 * (edge / variance)
   ├─→ Apply constraints: min(kelly, 2% capital)
   └─→ Output: TradeIntent

4. Risk Approval (EXISTING)
   ├─→ RiskKernel.evaluate(intent)
   └─→ Check: daily loss, position limits, anomaly detection

5. Execution (EXISTING)
   ├─→ ExecutorAdapter.execute() [Mock or Live]
   └─→ PositionTracker.record_trade()
```

### Testing Strategy

**Unit Tests** (80% coverage target):
- `test_llm_forecaster.py`: Mock LLM responses, test parsing logic
- `test_position_sizing.py`: Kelly calculation, constraint enforcement
- `test_forecast_validation.py`: Calibration metrics, edge calculation

**Integration Tests**:
- `test_forecaster_integration.py`: End-to-end with mock markets
- `test_risk_integration.py`: Forecaster → RiskKernel → Executor flow

**Validation Tests**:
- `test_paper_trading.py`: 20+ resolved markets, measure actual edge

## Success Metrics

### Phase 1: Development (Weeks 1-2)
- [ ] LLMForecaster module passes all unit tests
- [ ] Integration with RiskKernel complete
- [ ] Paper trading mode functional
- [ ] Code review: no bare except, pdb removed, logging added

### Phase 2: Validation (Weeks 3-4)
- [ ] 20+ paper trades executed
- [ ] Forecast calibration: actual outcomes within ±10% of predictions
- [ ] Positive edge on 60%+ of trades
- [ ] Zero critical bugs in production-ready code

### Phase 3: Production Ready (Week 5+)
- [ ] Test coverage >80% for new code
- [ ] Documentation complete (setup, usage, troubleshooting)
- [ ] Risk limits validated in paper trading
- [ ] User approval for live trading

## Dependencies

### On Other Work
- None (independent MVP)

### Blocking Others
- Future ensemble system depends on single-model forecaster interface
- Future learning/calibration depends on forecast tracking infrastructure

## Timeline Estimate

**Confidence: 50%** (high uncertainty due to LLM unpredictability)

- Week 1: Core forecasting module + unit tests (20-30 hours)
- Week 2: Risk integration + position sizing (15-20 hours)
- Week 3-4: Paper trading validation (10-15 hours + wait time)
- Week 5: Production hardening + docs (10-15 hours)

**Total**: 55-80 hours of development + 2-3 weeks validation time

**Assumptions**:
- LLM prompts work reasonably well on first attempt
- No major integration surprises with existing codebase
- Paper trading can run automatically (no manual intervention)

**Failure modes**:
- If LLM forecasts are garbage → add 2 weeks for prompt engineering
- If integration is complex → add 1 week for refactoring
- If edge remains negative → pivot to ensemble or abandon approach

## Notes

### Key Insights from User Spec

1. **Fractional Kelly is critical**: User emphasized 25% Kelly fraction multiple times. Full Kelly leads to ruin.

2. **Multi-source data helps**: User's spec includes news, sentiment, order flow. We can leverage existing connectors.

3. **Superforecaster prompting**: User specified decomposition, base rates, reference class forecasting. Need to research best practices.

4. **Confidence calibration**: User wants confidence-weighted edge calculation. This is a key differentiator.

### Existing Code to Leverage

- `agents/application/executor.py`: Has LLM calling infrastructure, token management
- `agents/copytrader/risk_kernel.py`: Pure risk logic, can plug in Kelly sizing
- `agents/connectors/chroma.py`: RAG market filtering already working
- `agents/copytrader/executor_adapter.py`: Mock/live execution pattern to copy

### Critical Issues to Fix First

Before starting new development:
1. Remove `pdb.set_trace()` at polymarket.py:440
2. Replace bare `except:` with specific exception handling
3. Add structured logging framework (replace print statements)
4. Fix infinite recursion in retry logic (trade.py:63-65)

These are production blockers that will cause failures during validation.

---

**Last Updated**: 2026-01-08
**Status**: Planning
**Owner**: User
**Reviewer**: Claude Code
