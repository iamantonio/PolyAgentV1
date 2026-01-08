"""
Phase 2.2: Diagnostic SELL Attempt

ONE micro-sell with full instrumentation to identify SELL failure cause.
Constraints: 1 share only, full logging, hard stop after attempt.
"""

import os
import sys
import json
import time
from decimal import Decimal
from web3 import Web3
from dotenv import load_dotenv

# Load environment
os.chdir('/home/tony/Dev/agents')
load_dotenv()

from agents.copytrader.executor_adapter import create_executor

# Constants
POLYGON_RPC = "https://polygon-rpc.com"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

# ERC-1155 ABI for balanceOf
ERC1155_BALANCE_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"}
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def get_onchain_balance(w3: Web3, proxy_address: str, token_id: str) -> int:
    """
    Read on-chain ERC-1155 balance for specific token.

    Returns: Balance in smallest units (shares)
    """
    ctf_contract = w3.eth.contract(
        address=Web3.to_checksum_address(CTF_ADDRESS),
        abi=ERC1155_BALANCE_ABI
    )

    # Convert token_id string to int
    token_id_int = int(token_id)

    balance = ctf_contract.functions.balanceOf(
        Web3.to_checksum_address(proxy_address),
        token_id_int
    ).call()

    return balance


def sell_preflight(proxy_address: str, token_id: str, sell_size: Decimal) -> dict:
    """
    SELL preflight checks - read-only validation before attempting SELL.

    Returns: dict with preflight results
    Raises: Exception if preflight fails
    """
    print("\n" + "=" * 60)
    print("SELL PREFLIGHT CHECKS")
    print("=" * 60)

    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))

    if not w3.is_connected():
        raise Exception("Cannot connect to Polygon RPC")

    # Get on-chain balance
    onchain_balance = get_onchain_balance(w3, proxy_address, token_id)

    # Convert to decimal for comparison
    sell_size_int = int(sell_size)

    preflight = {
        "proxy_address": proxy_address,
        "token_id": token_id,
        "expected_outcome": "YES (Tim Cook CEO exit)",
        "onchain_balance_shares": onchain_balance,
        "requested_sell_size_shares": sell_size_int,
        "balance_sufficient": onchain_balance >= sell_size_int
    }

    print(f"\nProxy Address: {preflight['proxy_address']}")
    print(f"Token ID: {preflight['token_id']}")
    print(f"Expected Outcome: {preflight['expected_outcome']}")
    print()
    print(f"On-Chain Balance: {preflight['onchain_balance_shares']} shares")
    print(f"Requested Sell Size: {preflight['requested_sell_size_shares']} shares")
    print()

    if not preflight['balance_sufficient']:
        print(f"❌ FAIL: Insufficient balance!")
        print(f"   Need: {sell_size_int}")
        print(f"   Have: {onchain_balance}")
        raise Exception("PREFLIGHT FAILED: Insufficient on-chain balance")

    print("✅ PASS: Sufficient balance for micro-sell")
    print("=" * 60)

    return preflight


def execute_instrumented_sell(token_id: str, sell_size: Decimal) -> dict:
    """
    Execute ONE micro-sell with full instrumentation.

    Returns: dict with execution details
    """
    print("\n" + "=" * 60)
    print("EXECUTING INSTRUMENTED MICRO-SELL")
    print("=" * 60)

    print(f"\nToken ID: {token_id}")
    print(f"Side: SELL")
    print(f"Size: {sell_size} shares")
    print()

    # Create executor
    executor = create_executor(use_real=True)

    print(f"Executor: {executor.get_name()}")
    print()

    # Prepare diagnostic payload
    diagnostic = {
        "request": {
            "token_id": token_id,
            "side": "sell",
            "size": str(sell_size),
            "executor": executor.get_name()
        },
        "timestamp_start": time.time()
    }

    # Execute
    print("Sending SELL order to CLOB...")
    start_time = time.time()

    try:
        result = executor.execute_market_order(
            market_id=token_id,
            side='sell',
            size=sell_size
        )

        latency = time.time() - start_time

        diagnostic["timestamp_end"] = time.time()
        diagnostic["latency"] = latency
        diagnostic["response"] = {
            "success": result.success,
            "price": str(result.price),
            "size": str(result.size),
            "execution_id": result.execution_id,
            "error": result.error,
            "timestamp": result.timestamp
        }

        print()
        print("=== CLOB RESPONSE ===")
        print(f"Success: {result.success}")
        print(f"Price: {result.price}")
        print(f"Size: {result.size}")
        print(f"Execution ID: {result.execution_id}")
        print(f"Error: {result.error}")
        print(f"Latency: {latency:.3f}s")
        print()

        return diagnostic

    except Exception as e:
        diagnostic["timestamp_end"] = time.time()
        diagnostic["exception"] = str(e)
        print(f"\n❌ EXCEPTION: {e}")
        raise


def main():
    """
    Phase 2.2 Diagnostic SELL

    ONE micro-sell attempt with full instrumentation.
    """
    print("=" * 60)
    print("PHASE 2.2: DIAGNOSTIC SELL ATTEMPT")
    print("=" * 60)

    # Load market data
    with open('/tmp/step4_market.json', 'r') as f:
        market_data = json.load(f)

    token_id = market_data['token_ids'][0]  # YES token
    proxy_address = os.getenv("POLYMARKET_PROXY_ADDRESS")

    if not proxy_address:
        print("❌ ERROR: POLYMARKET_PROXY_ADDRESS not set")
        sys.exit(1)

    # Micro-sell size: 1 share (minimum viable test)
    MICRO_SELL_SIZE = Decimal('1')

    print(f"\nMarket: {market_data['market_question']}")
    print(f"Proxy: {proxy_address}")
    print(f"Micro-sell size: {MICRO_SELL_SIZE} share")
    print()

    try:
        # STEP 1: Preflight checks
        preflight = sell_preflight(proxy_address, token_id, MICRO_SELL_SIZE)

        # STEP 2: Execute instrumented sell
        diagnostic = execute_instrumented_sell(token_id, MICRO_SELL_SIZE)

        # STEP 3: Save full diagnostic report
        report = {
            "phase": "2.2",
            "experiment": "diagnostic_micro_sell",
            "preflight": preflight,
            "execution": diagnostic
        }

        report_path = '/tmp/phase22_diagnostic_sell.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        print()
        print("=" * 60)
        print("DIAGNOSTIC REPORT SAVED")
        print("=" * 60)
        print(f"Location: {report_path}")
        print()

        # Determine result
        if diagnostic['response']['success']:
            print("✅ MICRO-SELL SUCCEEDED")
            print()
            print("This confirms SELL mechanics work.")
            print("Full position close should be viable.")
            sys.exit(0)
        else:
            print("❌ MICRO-SELL FAILED")
            print()
            print(f"Error: {diagnostic['response']['error']}")
            print()
            print("Hypothesis analysis required - see diagnostic report.")
            sys.exit(1)

    except Exception as e:
        print()
        print("=" * 60)
        print("EXPERIMENT FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
