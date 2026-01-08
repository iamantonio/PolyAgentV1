"""
Phase 2.3: Attribution Falsifier

Single-shot experiment: Test if SELL works when EOA holds shares instead of proxy.

Constraints:
- No new buys
- Transfer 2 shares proxy→EOA
- One SELL attempt (1 share)
- No retries
- Stop after SELL attempt
"""

import os
import sys
import json
import time
from decimal import Decimal
from web3 import Web3

# Navigate to project root
os.chdir('/home/tony/Dev/agents')

# Load env manually
with open('.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value.strip('"')

# Constants
POLYGON_RPC = "https://polygon-rpc.com"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
TRANSFER_SHARES = 2
SELL_SHARES = 1

# ERC-1155 ABI
ERC1155_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"}
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "id", "type": "uint256"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "bytes", "name": "data", "type": "bytes"}
        ],
        "name": "safeTransferFrom",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]


def print_safety_checklist():
    """Print safety constraints before execution."""
    print()
    print("=" * 60)
    print("PHASE 2.3 SAFETY CHECKLIST")
    print("=" * 60)
    print()
    print("✓ NO NEW BUYS")
    print(f"✓ TRANSFER_SHARES = {TRANSFER_SHARES}")
    print(f"✓ SELL_SHARES = {SELL_SHARES}")
    print("✓ ONE SELL ATTEMPT ONLY")
    print("✓ Execution will stop after SELL attempt")
    print()
    print("=" * 60)
    print()


def preflight_reads(w3, ctf_contract, proxy_addr, eoa_addr, token_id):
    """
    A. Preflight reads - check balances before transfer.

    Returns: dict with preflight state
    """
    print("=" * 60)
    print("A. PREFLIGHT READS")
    print("=" * 60)
    print()
    print(f"EOA:      {eoa_addr}")
    print(f"Proxy:    {proxy_addr}")
    print(f"Token ID: {token_id}")
    print()

    proxy_balance = ctf_contract.functions.balanceOf(proxy_addr, int(token_id)).call()
    eoa_balance = ctf_contract.functions.balanceOf(eoa_addr, int(token_id)).call()

    print(f"Proxy balance: {proxy_balance:,} shares")
    print(f"EOA balance:   {eoa_balance:,} shares")
    print()

    # Assertions
    assert proxy_balance >= TRANSFER_SHARES, f"Insufficient proxy balance: {proxy_balance} < {TRANSFER_SHARES}"

    if eoa_balance != 0:
        print(f"⚠️  WARNING: EOA already has {eoa_balance} shares (expected 0)")
    else:
        print("✓ EOA balance is 0 (as expected)")

    print()

    return {
        "proxy_balance_before": proxy_balance,
        "eoa_balance_before": eoa_balance
    }


def transfer_shares(w3, ctf_contract, private_key, proxy_addr, eoa_addr, token_id, amount):
    """
    B. Transfer shares from proxy to EOA using ERC-1155 safeTransferFrom.

    NOTE: For proxy wallets, this requires the controlling EOA to sign a transaction
    that the proxy executes. This may not work directly and might need proxy-specific
    transaction routing.

    Returns: dict with transfer results
    """
    print("=" * 60)
    print("B. TRANSFER (Proxy → EOA)")
    print("=" * 60)
    print()
    print(f"Transferring {amount} shares from Proxy to EOA...")
    print()

    try:
        # Get nonce for EOA (signing account)
        nonce = w3.eth.get_transaction_count(eoa_addr)

        # Build transfer transaction
        # NOTE: This attempts to call safeTransferFrom FROM the proxy address
        # For proxy wallets, this may require different transaction construction
        transfer_tx = ctf_contract.functions.safeTransferFrom(
            proxy_addr,  # from (proxy holds the shares)
            eoa_addr,    # to (EOA receiving shares)
            int(token_id),
            amount,
            b''          # data parameter (empty bytes)
        ).build_transaction({
            'chainId': 137,
            'from': eoa_addr,  # Transaction sender (EOA signs)
            'nonce': nonce,
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })

        # Sign transaction with EOA private key
        signed_tx = w3.eth.account.sign_transaction(transfer_tx, private_key=private_key)

        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transfer tx sent: {tx_hash.hex()}")

        # Wait for receipt
        print("Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        print(f"✓ Transfer confirmed in block {receipt['blockNumber']}")
        print(f"  Status: {'SUCCESS' if receipt['status'] == 1 else 'FAILED'}")
        print(f"  Gas used: {receipt['gasUsed']:,}")
        print()

        return {
            "tx_hash": tx_hash.hex(),
            "block": receipt['blockNumber'],
            "status": receipt['status'],
            "gas_used": receipt['gasUsed']
        }

    except Exception as e:
        print(f"❌ Transfer failed: {e}")
        raise


def read_balances_post_transfer(ctf_contract, proxy_addr, eoa_addr, token_id):
    """Re-read balances after transfer and print delta."""
    print("=" * 60)
    print("POST-TRANSFER BALANCE CHECK")
    print("=" * 60)
    print()

    proxy_balance = ctf_contract.functions.balanceOf(proxy_addr, int(token_id)).call()
    eoa_balance = ctf_contract.functions.balanceOf(eoa_addr, int(token_id)).call()

    print(f"Proxy balance: {proxy_balance:,} shares")
    print(f"EOA balance:   {eoa_balance:,} shares")
    print()

    return {
        "proxy_balance_after": proxy_balance,
        "eoa_balance_after": eoa_balance
    }


def sell_from_eoa(private_key, token_id, amount):
    """
    C. SELL using EOA-mode CLOB client (signature_type=0, no funder).

    Returns: dict with sell results
    """
    print("=" * 60)
    print("C. SELL (EOA-held shares)")
    print("=" * 60)
    print()
    print("Initializing EOA-mode CLOB client...")
    print(f"  signature_type: 0 (EOA mode)")
    print(f"  funder: None")
    print()

    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import MarketOrderArgs, OrderType

    # Create EOA-mode client (signature_type=0, no funder)
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137,
        signature_type=0  # EOA mode - no funder parameter
    )

    # Create and set API credentials
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)

    print("✓ EOA-mode client initialized")
    print()
    print(f"Placing SELL order for {amount} share(s)...")
    print()

    start_time = time.time()

    try:
        # Create market order
        order_args = MarketOrderArgs(
            token_id=token_id,
            amount=float(amount),
            side="SELL"
        )

        # Create and sign order
        signed_order = client.create_market_order(order_args)

        # Post order (Fill-or-Kill)
        response = client.post_order(signed_order, orderType=OrderType.FOK)

        latency = time.time() - start_time

        print("=== SELL RESPONSE ===")
        print(f"Response: {response}")
        print(f"Latency: {latency:.3f}s")
        print()

        # Parse response
        if response and isinstance(response, dict):
            order_id = response.get('orderID', None)
            status = response.get('status', 'unknown')
            success = status.upper() in ['MATCHED', 'FILLED', 'LIVE']

            result = {
                "success": success,
                "order_id": order_id,
                "status": status,
                "response": response,
                "latency": latency,
                "error": None if success else f"Order status: {status}"
            }

            if success:
                print("✅ SELL SUCCEEDED!")
            else:
                print(f"❌ SELL FAILED: {status}")

            return result
        else:
            return {
                "success": False,
                "error": f"Unexpected response: {response}",
                "latency": latency
            }

    except Exception as e:
        latency = time.time() - start_time
        print(f"❌ SELL EXCEPTION: {e}")
        return {
            "success": False,
            "error": str(e),
            "latency": latency
        }


def main():
    """Phase 2.3 Attribution Falsifier - Main execution."""
    print()
    print("=" * 60)
    print("PHASE 2.3: ATTRIBUTION FALSIFIER")
    print("=" * 60)

    # Print safety checklist
    print_safety_checklist()

    # Get configuration
    private_key = os.environ["POLYGON_WALLET_PRIVATE_KEY"]
    if private_key.startswith('0x'):
        private_key = private_key[2:]

    proxy_address = os.environ["POLYMARKET_PROXY_ADDRESS"]

    # Derive EOA from private key
    w3 = Web3()
    eoa_account = w3.eth.account.from_key(private_key)
    eoa_address = eoa_account.address

    # Load market data
    with open('/tmp/step4_market.json', 'r') as f:
        market_data = json.load(f)

    token_id = market_data['token_ids'][0]

    # Initialize Web3
    w3_polygon = Web3(Web3.HTTPProvider(POLYGON_RPC))

    if not w3_polygon.is_connected():
        print("❌ Cannot connect to Polygon RPC")
        sys.exit(1)

    # Initialize CTF contract
    ctf_contract = w3_polygon.eth.contract(
        address=Web3.to_checksum_address(CTF_ADDRESS),
        abi=ERC1155_ABI
    )

    proxy_addr = Web3.to_checksum_address(proxy_address)
    eoa_addr = Web3.to_checksum_address(eoa_address)

    # Initialize report
    report = {
        "phase": "2.3",
        "experiment": "attribution_falsifier",
        "addresses": {
            "eoa": eoa_addr,
            "proxy": proxy_addr
        },
        "token_id": token_id,
        "transfer_amount": TRANSFER_SHARES,
        "sell_amount": SELL_SHARES
    }

    try:
        # A. Preflight
        preflight = preflight_reads(w3_polygon, ctf_contract, proxy_addr, eoa_addr, token_id)
        report["preflight"] = preflight

        # B. Transfer
        transfer_result = transfer_shares(
            w3_polygon, ctf_contract, private_key,
            proxy_addr, eoa_addr, token_id, TRANSFER_SHARES
        )
        report["transfer"] = transfer_result

        # Read balances after transfer
        post_transfer = read_balances_post_transfer(ctf_contract, proxy_addr, eoa_addr, token_id)
        report["post_transfer"] = post_transfer

        # C. SELL from EOA
        sell_result = sell_from_eoa(private_key, token_id, SELL_SHARES)
        report["sell"] = sell_result

        # D. Save report
        report_path = '/tmp/phase23_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print()
        print("=" * 60)
        print("PHASE 2.3 COMPLETE")
        print("=" * 60)
        print(f"Report saved: {report_path}")
        print()

        # Summary
        transfer_success = transfer_result['status'] == 1
        sell_success = sell_result['success']

        print("SUMMARY:")
        print(f"  Transfer: {'✅ SUCCESS' if transfer_success else '❌ FAILED'}")
        print(f"  SELL:     {'✅ SUCCESS' if sell_success else '❌ FAILED'}")
        print()

        if transfer_success and sell_success:
            print("✅ ATTRIBUTION HYPOTHESIS CONFIRMED")
            print("   SELL works when EOA holds shares")
            sys.exit(0)
        elif transfer_success and not sell_success:
            print("❌ SELL FAILED EVEN WITH EOA CUSTODY")
            print(f"   Error: {sell_result.get('error')}")
            sys.exit(1)
        else:
            print("❌ TRANSFER FAILED")
            sys.exit(1)

    except Exception as e:
        print()
        print("=" * 60)
        print("EXPERIMENT FAILED")
        print("=" * 60)
        print(f"Error: {e}")

        # Save partial report
        report["error"] = str(e)
        with open('/tmp/phase23_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)

        sys.exit(1)


if __name__ == "__main__":
    main()
