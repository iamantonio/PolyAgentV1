"""
Phase 2.2: CTF Approval Verification for Proxy Wallet

Checks and sets CTF ERC-1155 approvals for the proxy wallet to enable SELL operations.
NO live trades in this script - approval setup only.
"""

import os
import sys
from web3 import Web3
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
POLYGON_RPC = "https://polygon-rpc.com"
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
EXCHANGE_CTF = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
EXCHANGE_NEG_RISK = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

# ERC-1155 ABI for isApprovalForAll and setApprovalForAll
ERC1155_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "address", "name": "operator", "type": "address"}
        ],
        "name": "isApprovedForAll",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "operator", "type": "address"},
            {"internalType": "bool", "name": "approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]


def check_approvals(w3: Web3, ctf_contract, proxy_address: str) -> dict:
    """
    Read-only check of current approval status.

    Returns dict with approval status for each exchange.
    """
    print(f"\n=== Checking Approvals for Proxy ===")
    print(f"Proxy: {proxy_address}")
    print()

    approvals = {}

    for exchange_name, exchange_addr in [
        ("CTF Exchange", EXCHANGE_CTF),
        ("Neg Risk Exchange", EXCHANGE_NEG_RISK)
    ]:
        is_approved = ctf_contract.functions.isApprovedForAll(
            proxy_address,
            exchange_addr
        ).call()

        approvals[exchange_name] = {
            "address": exchange_addr,
            "approved": is_approved
        }

        status = "✅ APPROVED" if is_approved else "❌ NOT APPROVED"
        print(f"{exchange_name}: {status}")
        print(f"  Address: {exchange_addr}")
        print()

    return approvals


def main():
    """
    Phase 2.2 CTF Approval Verification

    Checks approval status for proxy wallet.
    Does NOT attempt to set approvals in this version.
    """
    print("=" * 60)
    print("PHASE 2.2: CTF APPROVAL VERIFICATION")
    print("=" * 60)

    # Get proxy address from env
    proxy_address = os.getenv("POLYMARKET_PROXY_ADDRESS")

    if not proxy_address:
        print("❌ ERROR: POLYMARKET_PROXY_ADDRESS not set in .env")
        sys.exit(1)

    proxy_address = Web3.to_checksum_address(proxy_address)

    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))

    if not w3.is_connected():
        print("❌ ERROR: Cannot connect to Polygon RPC")
        sys.exit(1)

    print(f"✅ Connected to Polygon")
    print()

    # Initialize CTF contract
    ctf_contract = w3.eth.contract(
        address=Web3.to_checksum_address(CTF_ADDRESS),
        abi=ERC1155_ABI
    )

    # Check current approvals (read-only)
    approvals = check_approvals(w3, ctf_contract, proxy_address)

    # Determine if approvals needed
    needs_approval = any(not v["approved"] for v in approvals.values())

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    if needs_approval:
        print("⚠️  Approvals MISSING - SELL operations will fail")
        print()
        print("Required action:")
        print("  Set CTF approvals for proxy wallet before attempting SELL")
        sys.exit(1)
    else:
        print("✅ All approvals SET - SELL operations should work")
        sys.exit(0)


if __name__ == "__main__":
    main()
