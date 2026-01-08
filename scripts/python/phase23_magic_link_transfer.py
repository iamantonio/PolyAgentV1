"""
Phase 2.3: Attribution Falsifier - Magic.Link Mode

Same experiment but using proxy wallet to initiate transfer (proxy pays gas).
Constraints: Same as original - NO NEW BUYS, transfer 2, sell 1, one attempt only.
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
    print("PHASE 2.3 SAFETY CHECKLIST (MAGIC.LINK MODE)")
    print("=" * 60)
    print()
    print("✓ NO NEW BUYS")
    print(f"✓ TRANSFER_SHARES = {TRANSFER_SHARES}")
    print(f"✓ SELL_SHARES = {SELL_SHARES}")
    print("✓ ONE SELL ATTEMPT ONLY")
    print("✓ Proxy wallet pays gas for transfer")
    print()
    print("=" * 60)
    print()


def preflight_reads(w3, ctf_contract, proxy_addr, eoa_addr, token_id):
    """Preflight reads - check balances and gas."""
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

    # Check gas balances
    proxy_matic = w3.eth.get_balance(proxy_addr)
    eoa_matic = w3.eth.get_balance(eoa_addr)

    print(f"Proxy balance: {proxy_balance:,} shares, {w3.from_wei(proxy_matic, 'ether'):.4f} MATIC")
    print(f"EOA balance:   {eoa_balance:,} shares, {w3.from_wei(eoa_matic, 'ether'):.4f} MATIC")
    print()

    # Assertions
    assert proxy_balance >= TRANSFER_SHARES, f"Insufficient proxy balance: {proxy_balance} < {TRANSFER_SHARES}"

    if proxy_matic == 0:
        print("⚠️  WARNING: Proxy has 0 MATIC - transfer will fail")
        raise Exception("PREFLIGHT FAILED: Proxy has no MATIC for gas")

    print(f"✓ Proxy has {w3.from_wei(proxy_matic, 'ether'):.4f} MATIC for gas")
    print()

    return {
        "proxy_balance_before": proxy_balance,
        "eoa_balance_before": eoa_balance,
        "proxy_matic": float(w3.from_wei(proxy_matic, 'ether')),
        "eoa_matic": float(w3.from_wei(eoa_matic, 'ether'))
    }


def transfer_shares_proxy_mode(w3, ctf_contract, private_key, proxy_addr, eoa_addr, token_id, amount):
    """
    Attempt transfer with proxy as transaction sender.

    NOTE: This may not work for proxy wallets - they typically need special
    transaction routing through their own contract methods.
    """
    print("=" * 60)
    print("B. TRANSFER (Proxy → EOA, Proxy Pays Gas)")
    print("=" * 60)
    print()
    print(f"Attempting proxy-initiated transfer of {amount} shares...")
    print("⚠️  This may fail - proxy wallets typically need special tx routing")
    print()

    try:
        # Build transfer transaction with PROXY as sender
        # This is unlikely to work for smart contract wallets
        transfer_tx = ctf_contract.functions.safeTransferFrom(
            proxy_addr,
            eoa_addr,
            int(token_id),
            amount,
            b''
        ).build_transaction({
            'chainId': 137,
            'from': proxy_addr,  # Proxy as sender (not EOA)
            'nonce': w3.eth.get_transaction_count(proxy_addr),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })

        # Try to sign with EOA key
        # This will likely fail - smart contracts can't be "signed" this way
        signed_tx = w3.eth.account.sign_transaction(transfer_tx, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"Transfer tx sent: {tx_hash.hex()}")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        print(f"✓ Transfer confirmed in block {receipt['blockNumber']}")
        print()

        return {
            "tx_hash": tx_hash.hex(),
            "block": receipt['blockNumber'],
            "status": receipt['status']
        }

    except Exception as e:
        print(f"❌ Transfer failed: {e}")
        print()
        print("EXPECTED: Proxy wallets need special transaction routing")
        print("Magic.Link proxies are smart contracts, not EOAs")
        raise


def sell_from_magic_link(private_key, proxy_address, token_id, amount):
    """SELL using Magic.Link mode (signature_type=1, funder=proxy)."""
    print("=" * 60)
    print("C. SELL (Magic.Link Mode)")
    print("=" * 60)
    print()
    print("Initializing Magic.Link CLOB client...")
    print(f"  signature_type: 1")
    print(f"  funder: {proxy_address}")
    print()

    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import MarketOrderArgs, OrderType

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        chain_id=137,
        signature_type=1,
        funder=proxy_address
    )

    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)

    print(f"Placing SELL order for {amount} share(s)...")
    print()

    start_time = time.time()

    try:
        order_args = MarketOrderArgs(
            token_id=token_id,
            amount=float(amount),
            side="SELL"
        )

        signed_order = client.create_market_order(order_args)
        response = client.post_order(signed_order, orderType=OrderType.FOK)

        latency = time.time() - start_time

        print("=== SELL RESPONSE ===")
        print(f"Response: {response}")
        print(f"Latency: {latency:.3f}s")
        print()

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
    """Phase 2.3 Attribution Falsifier - Magic.Link Mode."""
    print()
    print("=" * 60)
    print("PHASE 2.3: ATTRIBUTION FALSIFIER (MAGIC.LINK MODE)")
    print("=" * 60)

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
        "experiment": "attribution_falsifier_magic_link",
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

        # B. Attempt proxy-mode transfer
        print("⚠️  ATTEMPTING PROXY-INITIATED TRANSFER")
        print("   This will likely fail - included for diagnostic purposes")
        print()

        try:
            transfer_result = transfer_shares_proxy_mode(
                w3_polygon, ctf_contract, private_key,
                proxy_addr, eoa_addr, token_id, TRANSFER_SHARES
            )
            report["transfer"] = transfer_result
        except Exception as e:
            print(f"Transfer failed as expected: {e}")
            report["transfer"] = {
                "attempted": True,
                "success": False,
                "error": str(e),
                "note": "Smart contract wallets cannot be directly signed - need proxy-specific routing"
            }

        # C. SELL from Magic.Link (regardless of transfer outcome)
        print()
        print("=" * 60)
        print("PROCEEDING TO SELL TEST (shares still in proxy)")
        print("=" * 60)
        print()

        sell_result = sell_from_magic_link(private_key, proxy_addr, token_id, SELL_SHARES)
        report["sell"] = sell_result

        # D. Save report
        report_path = '/tmp/phase23_magic_link_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print()
        print("=" * 60)
        print("PHASE 2.3 COMPLETE (MAGIC.LINK MODE)")
        print("=" * 60)
        print(f"Report saved: {report_path}")
        print()

        # Summary
        sell_success = sell_result['success']

        print("SUMMARY:")
        print(f"  Transfer: ⚠️  NOT APPLICABLE (proxy wallets need special routing)")
        print(f"  SELL:     {'✅ SUCCESS' if sell_success else '❌ FAILED'}")
        print()

        if sell_success:
            print("✅ SELL WORKS WITH MAGIC.LINK")
            print("   But this was already known - we tested this in Phase 2.2")
            sys.exit(0)
        else:
            print("❌ SELL STILL FAILS WITH MAGIC.LINK")
            print(f"   Error: {sell_result.get('error')}")
            print()
            print("   This confirms Phase 2.2 findings")
            sys.exit(1)

    except Exception as e:
        print()
        print("=" * 60)
        print("EXPERIMENT FAILED")
        print("=" * 60)
        print(f"Error: {e}")

        # Save partial report
        report["error"] = str(e)
        with open('/tmp/phase23_magic_link_report.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)

        sys.exit(1)


if __name__ == "__main__":
    main()
