"""
Analysis script for Phase 0 Validation Experiments

Run this after 48 hours of data collection to determine if infrastructure
improvements are the binding constraint.

Usage:
    python scripts/analyze_validation_experiment.py

Output:
    - API failure rates by endpoint
    - Decision on whether to proceed with Phase 1 Quick Wins
"""

import json
import pandas as pd
from pathlib import Path
from datetime import datetime


def load_validation_data(log_file: str = "logs/validation_experiment.jsonl"):
    """Load validation experiment data"""
    log_path = Path(log_file)

    if not log_path.exists():
        print(f"❌ Validation log file not found: {log_file}")
        print("Make sure the bot has been running with validation logging enabled.")
        return None

    with open(log_path) as f:
        data = [json.loads(line) for line in f]

    if not data:
        print(f"❌ Validation log file is empty: {log_file}")
        return None

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def analyze_failure_rates(df: pd.DataFrame):
    """Analyze API call success/failure rates"""
    print("\n" + "=" * 80)
    print(" EXPERIMENT 1: SILENT API FAILURE RATE ANALYSIS")
    print("=" * 80)

    # Overall stats
    total_calls = len(df)
    successful_calls = df["success"].sum()
    failed_calls = total_calls - successful_calls
    overall_failure_rate = (failed_calls / total_calls) * 100 if total_calls > 0 else 0

    print(f"\n📊 OVERALL STATISTICS")
    print(f"   Total API calls: {total_calls:,}")
    print(f"   Successful: {successful_calls:,} ({(successful_calls/total_calls)*100:.1f}%)")
    print(f"   Failed: {failed_calls:,} ({overall_failure_rate:.2f}%)")

    # Breakdown by endpoint
    print(f"\n📊 FAILURE RATES BY ENDPOINT")
    endpoint_stats = df.groupby("endpoint").agg({
        "success": ["count", "sum", lambda x: (1 - x.mean()) * 100],
        "duration_ms": "mean"
    }).round(2)

    endpoint_stats.columns = ["total_calls", "successful", "failure_rate_%", "avg_duration_ms"]
    endpoint_stats["failed"] = endpoint_stats["total_calls"] - endpoint_stats["successful"]
    endpoint_stats = endpoint_stats.sort_values("failure_rate_%", ascending=False)

    print(endpoint_stats.to_string())

    # THREAT 2: Check for failure clustering by endpoint
    print(f"\n⚠️  THREAT 2 CHECK: Failure Clustering by Endpoint")
    high_failure_endpoints = endpoint_stats[endpoint_stats["failure_rate_%"] > 10]
    if not high_failure_endpoints.empty:
        print(f"   🚨 WARNING: {len(high_failure_endpoints)} endpoint(s) with >10% failure rate:")
        print(high_failure_endpoints[["total_calls", "failure_rate_%"]].to_string())
        print(f"   → Even if aggregate <5%, these specific endpoints may corrupt edge")
    else:
        print(f"   ✅ No endpoints with >10% failure rate")

    # Error types
    if failed_calls > 0:
        print(f"\n📊 ERROR TYPES (Top 10)")
        error_counts = df[~df["success"]]["error"].value_counts().head(10)
        for error, count in error_counts.items():
            error_str = str(error)[:80]  # Truncate long errors
            print(f"   {count:3d}x  {error_str}")

    # THREAT 2: Check for temporal clustering (failures by hour)
    print(f"\n⚠️  THREAT 2 CHECK: Failure Clustering by Time")
    df["hour"] = df["timestamp"].dt.floor("H")
    hourly_failures = df.groupby("hour")["success"].agg(
        lambda x: (1 - x.mean()) * 100
    ).round(2)

    high_failure_hours = hourly_failures[hourly_failures > 10]
    if not high_failure_hours.empty:
        print(f"   🚨 WARNING: {len(high_failure_hours)} hour(s) with >10% failure rate:")
        for hour, rate in high_failure_hours.items():
            print(f"      {hour}: {rate:.1f}% failures")
        print(f"   → Failures may cluster during volatility/market events")
    else:
        print(f"   ✅ No hours with >10% failure rate (failures evenly distributed)")

    # THREAT 1: Check for incomplete payloads (silent success bias)
    print(f"\n⚠️  THREAT 1 CHECK: Incomplete Payload Detection")
    if "response_count" in df.columns:
        # Calculate rolling median response count per endpoint
        endpoint_medians = df[df["success"] & df["response_count"].notna()].groupby("endpoint")["response_count"].median()

        for endpoint in endpoint_medians.index:
            endpoint_data = df[(df["endpoint"] == endpoint) & df["success"] & df["response_count"].notna()]
            if len(endpoint_data) > 10:  # Need enough data
                median_count = endpoint_medians[endpoint]
                std_count = endpoint_data["response_count"].std()
                anomalous = endpoint_data[
                    abs(endpoint_data["response_count"] - median_count) > 2 * std_count
                ]

                if len(anomalous) > 0:
                    anomaly_rate = (len(anomalous) / len(endpoint_data)) * 100
                    print(f"   ⚠️  {endpoint}: {len(anomalous)} anomalous responses ({anomaly_rate:.1f}%)")
                    print(f"      Expected ~{median_count:.0f} items, got: {anomalous['response_count'].tolist()[:5]}")
                    print(f"      → Possible incomplete payloads logged as 'success'")
        print(f"   ℹ️  If no warnings above, payload sizes are consistent")
    else:
        print(f"   ⚠️  response_count not tracked - cannot detect incomplete payloads")

    # Performance stats
    print(f"\n📊 API LATENCY STATISTICS")
    latency_stats = df.groupby("endpoint")["duration_ms"].agg(["mean", "median", "max"]).round(2)
    latency_stats = latency_stats.sort_values("mean", ascending=False)
    print(latency_stats.to_string())

    # Decision criterion
    print(f"\n{'=' * 80}")
    print(" 🎯 DECISION CRITERION: H2 - Silent failures materially distort edge estimation")
    print(f"{'=' * 80}")
    print(f"\n   Overall failure rate: {overall_failure_rate:.2f}%")
    print(f"   Threshold: >5% = GO (silent failures are material)")
    print(f"   Threshold: <2% = NO-GO (silent failures are negligible)")

    if overall_failure_rate > 5:
        print(f"\n   🚨 FINDING: Silent failures >5% → H2 CONFIRMED")
        print(f"   ✅ RECOMMENDATION: Proceed with Quick Wins (QW-1 through QW-5)")
        print(f"   → Observability work is HIGH-LEVERAGE")
        return "GO"
    elif overall_failure_rate < 2:
        print(f"\n   ✅ FINDING: Silent failures <2% → H2 REJECTED")
        print(f"   ❌ RECOMMENDATION: Defer observability work")
        print(f"   → Current error handling is adequate for scale")
        return "NO_GO"
    else:
        print(f"\n   ⚠️  FINDING: Failure rate in middle zone (2-5%)")
        print(f"   → Review endpoint breakdown for selective improvements")
        print(f"   → Consider instrumenting only high-failure endpoints")
        return "PARTIAL"


def analyze_time_range(df: pd.DataFrame):
    """Analyze data collection time range"""
    if df.empty:
        return

    min_time = df["timestamp"].min()
    max_time = df["timestamp"].max()
    duration_hours = (max_time - min_time).total_seconds() / 3600

    print(f"\n📅 DATA COLLECTION PERIOD")
    print(f"   Start: {min_time}")
    print(f"   End:   {max_time}")
    print(f"   Duration: {duration_hours:.1f} hours")

    if duration_hours < 24:
        print(f"\n   ⚠️  WARNING: Less than 24 hours of data")
        print(f"   → Results may not be representative")
        print(f"   → Recommend collecting at least 48 hours")
    elif duration_hours >= 48:
        print(f"\n   ✅ Good: 48+ hours of data collected")


def main():
    """Main analysis function"""
    print("\n" + "=" * 80)
    print(" PHASE 0 VALIDATION EXPERIMENT ANALYSIS")
    print(" Testing H2: Silent failures materially distort edge estimation")
    print("=" * 80)

    # Load data
    df = load_validation_data()
    if df is None:
        return

    # Analyze time range
    analyze_time_range(df)

    # Analyze failure rates
    decision = analyze_failure_rates(df)

    # Final summary
    print(f"\n{'=' * 80}")
    print(" NEXT STEPS")
    print(f"={'=' * 80}\n")

    if decision == "GO":
        print("1. ✅ Experiment 1 confirms infrastructure gaps")
        print("2. 📋 Review Experiment 2-5 results")
        print("3. 🚀 If ≥3 experiments show GO → Execute Quick Wins immediately")
        print("4. 📊 Track impact: measure debugging time reduction")
    elif decision == "NO_GO":
        print("1. ✅ Experiment 1 rejects infrastructure hypothesis")
        print("2. 📋 Review other experiments for confirmation")
        print("3. 🎯 If ≥3 experiments show NO_GO → Focus on strategy, not infrastructure")
        print("4. 💡 Consider: market selection, position sizing, LLM prompts")
    else:
        print("1. ⚠️  Experiment 1 shows mixed results")
        print("2. 📋 Review endpoint breakdown for selective improvements")
        print("3. 🔍 Focus instrumentation on high-failure endpoints only")
        print("4. 📊 Continue with Experiments 2-5 for complete picture")

    print()


if __name__ == "__main__":
    main()
