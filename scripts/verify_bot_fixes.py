#!/usr/bin/env python3
"""
Verification script to confirm all fixes are working.
Run this after applying all fixes.

Usage:
    python scripts/verify_bot_fixes.py
"""

import os
import sys
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.expanduser("~/.polymarket/learning_trader.db")


def check_database_location():
    """Check database is in persistent location."""
    print("\n1. DATABASE LOCATION")
    print("-" * 40)

    if os.path.exists(DB_PATH):
        print(f"   Location: {DB_PATH}")
        print(f"   Persistent: YES")
        size = os.path.getsize(DB_PATH)
        print(f"   Size: {size:,} bytes")
        return True
    else:
        print(f"   ERROR: Database not found at {DB_PATH}")
        print(f"   Run: python scripts/migrate_database.py")
        return False


def check_outcomes_recorded():
    """Check if outcomes are being recorded."""
    print("\n2. OUTCOME RECORDING")
    print("-" * 40)

    if not os.path.exists(DB_PATH):
        print("   Skipped (database not found)")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(trade_executed) as executed,
               SUM(actual_outcome IS NOT NULL) as with_outcome,
               SUM(pnl IS NOT NULL) as with_pnl
        FROM predictions
    ''')
    total, executed, with_outcome, with_pnl = cursor.fetchone()

    print(f"   Total predictions: {total or 0}")
    print(f"   Trades executed: {executed or 0}")
    print(f"   With outcomes: {with_outcome or 0}")
    print(f"   With P&L: {with_pnl or 0}")

    if executed and executed > 0:
        outcome_rate = (with_outcome or 0) / executed * 100
        print(f"   Outcome coverage: {outcome_rate:.1f}%")

        if outcome_rate < 50:
            print("   WARNING: Low outcome coverage - run outcome_sync")

    conn.close()
    return (with_outcome or 0) > 0


def check_edge_data():
    """Check edge data by market type."""
    print("\n3. EDGE DATA BY MARKET TYPE")
    print("-" * 40)

    if not os.path.exists(DB_PATH):
        print("   Skipped (database not found)")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT market_type,
               COUNT(*) as trades,
               SUM(CASE WHEN actual_outcome = 1 THEN 1 ELSE 0 END) as wins,
               AVG(pnl) as avg_pnl,
               SUM(pnl) as total_pnl
        FROM predictions
        WHERE trade_executed = 1
        AND actual_outcome IS NOT NULL
        GROUP BY market_type
    ''')

    results = cursor.fetchall()

    if not results:
        print("   No edge data available")
        print("   Run: python -m agents.polymarket.outcome_sync")
        conn.close()
        return False

    for market_type, trades, wins, avg_pnl, total_pnl in results:
        win_rate = wins / trades if trades else 0
        edge = "EDGE" if (avg_pnl or 0) > 0 else "NO EDGE"
        print(f"   {market_type or 'unknown'}: {trades} trades, "
              f"{win_rate:.1%} win rate, "
              f"${avg_pnl or 0:.2f} avg P&L, "
              f"${total_pnl or 0:.2f} total - {edge}")

    conn.close()
    return True


def check_env_variables():
    """Check required environment variables."""
    print("\n4. ENVIRONMENT VARIABLES")
    print("-" * 40)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("   Warning: python-dotenv not installed")

    required = [
        "POLYMARKET_PROXY_ADDRESS",
        "POLYMARKET_API_KEY",
        "POLYMARKET_API_SECRET"
    ]

    all_set = True
    for var in required:
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." if len(value) > 8 else value
            print(f"   {var}: {masked}")
        else:
            print(f"   {var}: NOT SET")
            all_set = False

    return all_set


def check_outcome_sync_module():
    """Check if outcome_sync module exists and works."""
    print("\n5. OUTCOME SYNC MODULE")
    print("-" * 40)

    try:
        from agents.polymarket.outcome_sync import OutcomeSync
        print("   Module imported: YES")

        try:
            sync = OutcomeSync()
            print("   Initialized: YES")
            return True
        except ValueError as e:
            print(f"   Initialization error: {e}")
            return False
    except ImportError as e:
        print(f"   Module import error: {e}")
        return False


def main():
    print("=" * 60)
    print("POLYMARKET BOT FIX VERIFICATION")
    print("=" * 60)

    results = {
        "database": check_database_location(),
        "outcomes": check_outcomes_recorded(),
        "edge_data": check_edge_data(),
        "env_vars": check_env_variables(),
        "outcome_sync": check_outcome_sync_module()
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_good = True
    for check, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"   {check}: {status}")
        if not passed:
            all_good = False

    if all_good:
        print("\n   All checks passed! Bot is ready.")
    else:
        print("\n   Some checks failed. Review above and fix issues.")
        print("\n   Quick fix steps:")
        print("   1. python scripts/migrate_database.py")
        print("   2. python -m agents.polymarket.outcome_sync")
        print("   3. python scripts/verify_bot_fixes.py")

    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())
