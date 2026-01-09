# Experiment 2: Losing Trade Reconstruction

**⚠️ CRITICAL: Execute this experiment BEFORE reading Experiment 1 results**

This prevents observer bias - you must measure current debugging difficulty without knowing the failure rates.

---

## Objective

Test whether current logs allow end-to-end debugging of losing trades.

**Hypothesis being tested**: H1 (observability is dominant failure mode) + H4 (trace IDs deliver nonlinear ROI)

**Falsification criterion**:
- >15 min median → H1/H4 confirmed (trace IDs are high ROI)
- <5 min median → H1/H4 rejected (current logs are sufficient)

---

## Method

### Step 1: Identify 3 Recent Losing Trades

```bash
cd /home/tony/Dev/agents

# Query database for recent losses
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('/tmp/trade_learning.db')
cursor = conn.execute('''
    SELECT
        timestamp,
        market_id,
        predicted_outcome,
        confidence,
        trade_size_usdc,
        profit_loss_usdc
    FROM predictions
    WHERE profit_loss_usdc < 0
    ORDER BY timestamp DESC
    LIMIT 3
''')

for row in cursor.fetchall():
    print(f'Loss: {row}')
"
```

### Step 2: For Each Trade, Answer These Questions

**Start timer** (use wall-clock, be honest)

For each losing trade, attempt to answer:

1. **What was the market state at decision time?**
   - Was the market open or near close?
   - What was the current price?
   - What was the trading volume?

2. **What was the LLM forecast and confidence?**
   - What outcome did the model predict?
   - What confidence level?
   - What was the reasoning?

3. **What was the market price vs predicted probability?**
   - Was there perceived edge?
   - How large was the expected value?

4. **Were there API failures during analysis?**
   - Did we fetch complete market data?
   - Were there timeouts or errors?
   - Did we skip any data sources?

5. **Was the data stale?**
   - When was the last market update?
   - How old was the price data?

**Stop timer** when you either:
- Have answers to all 5 questions, OR
- Give up (can't reconstruct the decision chain)

### Step 3: Document Your Process

Use this template for EACH trade:

```markdown
## Trade Reconstruction #1

**Market ID**: [from database]
**Loss Amount**: $X.XX
**Timestamp**: [from database]

**Start Time**: [HH:MM:SS]

**Reconstruction Steps**:
- [HH:MM:SS] Checked trade_history.db for trade details (X min)
- [HH:MM:SS] Searched logs/ for market_id (X min, Y grep attempts)
- [HH:MM:SS] Checked intent_log for validation (X min)
- [HH:MM:SS] [other steps...]

**End Time**: [HH:MM:SS]
**Total Time**: X minutes

**Questions Answered**: X / 5

1. Market state: [YES/NO/PARTIAL] - [your findings]
2. LLM forecast: [YES/NO/PARTIAL] - [your findings]
3. Price vs probability: [YES/NO/PARTIAL] - [your findings]
4. API failures: [YES/NO/PARTIAL] - [your findings]
5. Data staleness: [YES/NO/PARTIAL] - [your findings]

**Root Cause Identified**: YES / NO
**Could trace IDs have helped**: YES / NO / MAYBE
**Notes**: [any additional observations]
```

### Step 4: Calculate Metrics

After all 3 trades:

```
Median reconstruction time: X minutes
Questions answered rate: X / 15 (X%)
Root causes identified: X / 3
```

---

## Decision Criteria

| Median Time | Questions Answered | Decision |
|-------------|-------------------|----------|
| >15 min | <60% | **H1/H4 CONFIRMED** → Trace IDs have high ROI |
| 5-15 min | 60-80% | **PARTIAL** → Some observability improvements justified |
| <5 min | >80% | **H1/H4 REJECTED** → Current logs are sufficient |

---

## Anti-Patterns to Avoid (Threat 3: Observer Effect)

### ❌ DON'T:
- Look at Experiment 1 results first
- Assume "it would be faster with better logs" without measuring
- Open source code to "figure out what should have happened"
- Count time spent explaining to yourself as <5 min

### ✅ DO:
- Use only logs, database, and system output
- Be ruthlessly honest about wall-clock time
- If you can explain the loss WITHOUT opening code → count as ≤5 min
- If you're guessing or reconstructing from memory → you failed reconstruction

---

## Expected Outcome

After completing this experiment, you will have **empirical data** on:
- How long debugging actually takes (not estimates)
- What percentage of losses can be reconstructed
- Whether trace IDs would materially help

**IMPORTANT**: Do not proceed to read Experiment 1 results until this is complete.

Sequence: E2 (this) → E4 (SQLite stress) → E1 (read results) → E5 (correlation)

---

## Save Your Results

Save your reconstruction logs to:
```
docs/validation_results/experiment_2_reconstruction_log.md
```

This will be reviewed alongside E1-E5 results to make the final decision.
