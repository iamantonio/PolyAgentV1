#!/usr/bin/env python3
"""
Test XAI/Grok API health check before starting bot
"""
import sys
import os
sys.path.insert(0, '/home/tony/Dev/agents')

from dotenv import load_dotenv
load_dotenv()

from agents.reasoning.multi_agent import MultiAgentReasoning

print("=" * 80)
print("XAI (GROK-4) API HEALTH CHECK")
print("=" * 80)
print()

try:
    # Initialize with XAI
    print("Initializing Multi-Agent Reasoning with XAI...")
    multi_agent = MultiAgentReasoning(use_xai=True)
    print(f"✅ Initialized: {multi_agent.provider}")
    print(f"   Model: {multi_agent.model}")
    print(f"   Base URL: {multi_agent.client.base_url}")
    print()

    # Run health check
    print("Running API health check...")
    is_healthy, message = multi_agent.health_check()

    if is_healthy:
        print(f"✅ HEALTH CHECK PASSED")
        print(f"   {message}")
        print()
        print("🎉 XAI/Grok-4 is ready for live trading!")
        sys.exit(0)
    else:
        print(f"❌ HEALTH CHECK FAILED")
        print(f"   {message}")
        sys.exit(1)

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
