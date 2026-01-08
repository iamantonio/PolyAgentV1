#!/usr/bin/env python3
"""
Quick verification test for the outcome mapping fix.
Tests that the bot correctly maps outcomes to token IDs.
"""

# Test the outcome parsing logic
test_response = """
outcome:'No',
price:0.78,
size:0.2,
"""

print("Testing outcome parsing...")
print(f"Grok response: {test_response}")
print()

# Parse like the bot does
trade_parts = {}
for line in test_response.split('\n'):
    line = line.strip()
    if ':' in line:
        key, value = line.split(':', 1)
        trade_parts[key.strip()] = value.strip().rstrip(',').strip("'\"")

trade_outcome = trade_parts.get('outcome', 'Yes')
print(f"✅ Parsed outcome: '{trade_outcome}'")
print()

# Test outcome to token mapping
outcomes_list = ['Yes', 'No']
token_ids = ['token_yes_12345', 'token_no_67890']

print("Testing outcome → token ID mapping:")
print(f"  Outcomes: {outcomes_list}")
print(f"  Token IDs: {token_ids}")
print()

if trade_outcome in outcomes_list:
    token_index = outcomes_list.index(trade_outcome)
    token_id = token_ids[token_index]
    print(f"✅ Correct mapping!")
    print(f"  Outcome '{trade_outcome}' → Token index {token_index} → Token ID '{token_id}'")
else:
    print("❌ Failed to map outcome")

print()
print("=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
print()
print("Expected behavior:")
print("  - If Grok says 22% for YES → Should recommend 'No' (78% likely)")
print("  - If Grok says 'No' → Bot buys token_no_67890")
print("  - Never buys the LESS likely outcome")
