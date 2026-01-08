"""
Test Phase 0 budget enforcement.

This test directly exercises the budget enforcement without relying on
market data from Polymarket API.
"""

import os
import sys

# Set PYTHONPATH
sys.path.insert(0, '/home/tony/Dev/agents')

from decimal import Decimal
from agents.application.executor import Executor
from agents.application.budget_enforcer import BudgetEnforcer

def test_budget_enforcement():
    """Test that budget limits are enforced correctly."""

    print("\n" + "="*60)
    print("PHASE 0: BUDGET ENFORCEMENT TEST")
    print("="*60)

    # Initialize executor (which creates budget enforcer)
    print("\n1. Initializing Executor with BudgetEnforcer...")
    executor = Executor()

    # Check initial budget stats
    print("\n2. Initial Budget Stats:")
    stats = executor.budget.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # Test 1: Call LLM within budget
    print("\n3. Test 1: First LLM call (should succeed)")
    result = executor.get_llm_response("What is 2+2? Reply with just the number.")
    if result:
        print(f"   ✅ SUCCESS: Got response (length: {len(result)} chars)")
        print(f"   Response: {result[:100]}")
    else:
        print(f"   ⛔ BLOCKED: Budget limit hit")

    # Check updated stats
    print("\n4. Budget Stats After First Call:")
    stats = executor.budget.get_stats()
    print(f"   Daily spend: ${stats['daily_spend']:.4f} / ${stats['daily_budget']:.2f}")
    print(f"   Hourly spend: ${stats['hourly_spend']:.4f} / ${stats['hourly_budget']:.2f}")
    print(f"   Calls this hour: {stats['calls_this_hour']} / {stats['max_calls_per_hour']}")

    # Test 2: Make multiple calls to hit hourly limit
    print(f"\n5. Test 2: Making {stats['max_calls_per_hour']} more calls to hit hourly limit...")
    blocked_count = 0
    success_count = 0

    for i in range(stats['max_calls_per_hour']):
        result = executor.get_llm_response(f"Count to {i+1}")
        if result:
            success_count += 1
            print(f"   Call {i+1}: ✅ Success")
        else:
            blocked_count += 1
            print(f"   Call {i+1}: ⛔ BLOCKED")

            # Show why it was blocked
            stats = executor.budget.get_stats()
            if stats['blocked']:
                print(f"      Reason: {stats['block_reason']}")
            break

    # Final stats
    print("\n6. Final Budget Stats:")
    stats = executor.budget.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Successful calls: {success_count + 1}")  # +1 for first call
    print(f"Blocked calls: {blocked_count}")
    print(f"Total spend: ${stats['daily_spend']:.4f}")
    print(f"Budget remaining: ${stats['daily_remaining']:.4f}")

    if stats['blocked']:
        print(f"\n✅ BUDGET ENFORCEMENT WORKING")
        print(f"   System blocked at: {stats['block_reason']}")
    else:
        print(f"\n⚠️  Did not hit budget limit (configured limits may be high)")

    print("="*60 + "\n")

if __name__ == "__main__":
    test_budget_enforcement()
