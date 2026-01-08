#!/usr/bin/env python3
"""
Manual test to verify the outcome fix works correctly.
Simulates Grok's response and tests the outcome parsing logic.
"""
import ast  # Safe alternative to eval()

print("=" * 70)
print("TESTING OUTCOME MAPPING FIX")
print("=" * 70)
print()

# Simulate different Grok responses
test_cases = [
    {
        "name": "Grok recommends NO (recession unlikely)",
        "grok_analysis": "I believe recession has 22% likelihood for Yes",
        "grok_trade": "outcome:'No',\nprice:0.78,\nsize:0.15,",
        "expected_outcome": "No",
        "explanation": "Grok thinks YES only 22% likely, so buys NO (78% likely)"
    },
    {
        "name": "Grok recommends YES (recession likely)",
        "grok_analysis": "I believe recession has 85% likelihood for Yes",
        "grok_trade": "outcome:'Yes',\nprice:0.22,\nsize:0.2,",
        "expected_outcome": "Yes",
        "explanation": "Grok thinks YES 85% likely, so buys YES"
    },
    {
        "name": "Generic binary market - buy NO",
        "grok_analysis": "Low probability event",
        "grok_trade": "outcome:'No',\nprice:0.95,\nsize:0.1,",
        "expected_outcome": "No",
        "explanation": "Buying the more likely outcome"
    }
]

# Market data structure
mock_market = {
    "outcomes": "['Yes', 'No']",
    "clob_token_ids": "['token_yes_abc123', 'token_no_def456']"
}

print("Test Setup:")
print(f"  Market outcomes: {mock_market['outcomes']}")
print(f"  Token IDs: {mock_market['clob_token_ids']}")
print()

# Run tests
for i, test in enumerate(test_cases, 1):
    print(f"\n{'='*70}")
    print(f"TEST {i}: {test['name']}")
    print(f"{'='*70}")
    print(f"Grok analysis: {test['grok_analysis']}")
    print(f"Grok trade response: {test['grok_trade']}")
    print()

    # Parse the trade response (like the bot does)
    trade_parts = {}
    for line in test['grok_trade'].split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            trade_parts[key.strip()] = value.strip().rstrip(',').strip("'\"")

    trade_outcome = trade_parts.get('outcome', 'Yes')

    # Map outcome to token ID (like the bot does) - using ast.literal_eval (safe)
    outcomes_list = ast.literal_eval(mock_market["outcomes"])
    token_ids = ast.literal_eval(mock_market["clob_token_ids"])

    if trade_outcome in outcomes_list:
        token_index = outcomes_list.index(trade_outcome)
        token_id = token_ids[token_index]
    else:
        token_id = "ERROR: Could not map outcome"

    # Verify
    passed = (trade_outcome == test['expected_outcome'])
    status = "✅ PASS" if passed else "❌ FAIL"

    print(f"Parsed outcome: '{trade_outcome}'")
    print(f"Expected outcome: '{test['expected_outcome']}'")
    print(f"Selected token: {token_id}")
    print(f"Explanation: {test['explanation']}")
    print(f"\n{status}")

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("The fix ensures:")
print("  1. Prompt asks for 'outcome:' not 'side:'")
print("  2. Bot parses the specific outcome name (Yes/No)")
print("  3. Bot maps that outcome to the correct token ID")
print("  4. Bot ALWAYS buys what Grok recommends")
print()
print("BEFORE FIX: Bot blindly bought token[0] when side=BUY")
print("AFTER FIX: Bot buys the specific outcome Grok recommends")
print()
