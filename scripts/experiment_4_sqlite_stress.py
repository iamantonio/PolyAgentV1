#!/usr/bin/env python3
"""
Experiment 4: SQLite Concurrency Stress Test

Tests H3a vs H3b:
- H3a (benign): SQLite is fine at current write pattern
- H3b (binding): Actual concurrency causes lock contention

Methodology:
- 3 phases: single writer, N threads, N processes
- 2 configs: default vs WAL+optimized
- Measure: failure rate, p50/p95/p99 latency
"""

import sqlite3
import time
import sys
import statistics
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import List, Tuple, Dict
import multiprocessing


class SQLiteStressTest:
    """SQLite concurrency stress test"""

    def __init__(self, db_path: str = "/tmp/sqlite_stress.db"):
        self.db_path = db_path

    def setup_test_db(self, config: str = "default"):
        """Create test database with specified config"""
        # Remove existing DB
        Path(self.db_path).unlink(missing_ok=True)

        conn = sqlite3.connect(self.db_path)

        if config == "optimized":
            # WAL mode + optimizations
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=5000")  # 5 second timeout
            print(f"✓ Configured: WAL mode, NORMAL sync, 5s busy timeout")
        else:
            # Check default settings
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            sync = conn.execute("PRAGMA synchronous").fetchone()[0]
            timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
            print(f"✓ Default: journal_mode={mode}, sync={sync}, timeout={timeout}ms")

        # Create test table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stress_test (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                writer_id TEXT NOT NULL,
                iteration INTEGER NOT NULL,
                random_data TEXT
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON stress_test(timestamp)")
        conn.commit()
        conn.close()

    def single_write_attempt(self, writer_id: str, iteration: int) -> Tuple[bool, float, str]:
        """
        Single write attempt with latency measurement

        Returns: (success, latency_ms, error_msg)
        """
        start = time.time()
        error_msg = ""

        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()

            # BEGIN IMMEDIATE to acquire write lock immediately
            cursor.execute("BEGIN IMMEDIATE")

            cursor.execute("""
                INSERT INTO stress_test (timestamp, writer_id, iteration, random_data)
                VALUES (?, ?, ?, ?)
            """, (
                datetime.utcnow().isoformat(),
                writer_id,
                iteration,
                f"data_{writer_id}_{iteration}"
            ))

            conn.commit()
            conn.close()

            latency_ms = (time.time() - start) * 1000
            return (True, latency_ms, "")

        except Exception as e:
            latency_ms = (time.time() - start) * 1000
            error_msg = str(e)[:100]
            return (False, latency_ms, error_msg)

    def run_writer(self, writer_id: str, num_iterations: int) -> Dict:
        """Run a single writer for N iterations"""
        results = {
            "writer_id": writer_id,
            "attempts": 0,
            "successes": 0,
            "failures": 0,
            "latencies": [],
            "errors": []
        }

        for i in range(num_iterations):
            success, latency, error = self.single_write_attempt(writer_id, i)

            results["attempts"] += 1
            results["latencies"].append(latency)

            if success:
                results["successes"] += 1
            else:
                results["failures"] += 1
                results["errors"].append(error)

            # Small sleep to simulate realistic write pattern
            time.sleep(0.01)

        return results

    def run_phase(self, phase_name: str, num_writers: int,
                  executor_type: str = "thread") -> Dict:
        """
        Run a test phase with N concurrent writers

        Args:
            phase_name: Description of phase
            num_writers: Number of concurrent writers
            executor_type: "thread" or "process"
        """
        print(f"\n{'='*80}")
        print(f"PHASE: {phase_name}")
        print(f"Writers: {num_writers} ({executor_type})")
        print(f"{'='*80}")

        iterations_per_writer = 100

        start_time = time.time()

        # Choose executor
        if executor_type == "process":
            Executor = ProcessPoolExecutor
        else:
            Executor = ThreadPoolExecutor

        with Executor(max_workers=num_writers) as executor:
            futures = []
            for i in range(num_writers):
                writer_id = f"{executor_type}_{i}"
                future = executor.submit(self.run_writer, writer_id, iterations_per_writer)
                futures.append(future)

            # Collect results
            all_results = [f.result() for f in futures]

        duration = time.time() - start_time

        # Aggregate results
        total_attempts = sum(r["attempts"] for r in all_results)
        total_successes = sum(r["successes"] for r in all_results)
        total_failures = sum(r["failures"] for r in all_results)
        all_latencies = [lat for r in all_results for lat in r["latencies"]]
        all_errors = [err for r in all_results for err in r["errors"]]

        failure_rate = (total_failures / total_attempts * 100) if total_attempts > 0 else 0

        # Latency percentiles
        if all_latencies:
            p50 = statistics.median(all_latencies)
            p95 = statistics.quantiles(all_latencies, n=20)[18]  # 95th percentile
            p99 = statistics.quantiles(all_latencies, n=100)[98]  # 99th percentile
        else:
            p50 = p95 = p99 = 0

        results = {
            "phase": phase_name,
            "num_writers": num_writers,
            "executor_type": executor_type,
            "duration_sec": duration,
            "total_attempts": total_attempts,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "failure_rate_pct": failure_rate,
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "p99_latency_ms": p99,
            "unique_errors": list(set(all_errors))
        }

        # Print results
        print(f"\n📊 RESULTS:")
        print(f"  Total attempts: {total_attempts}")
        print(f"  Successes: {total_successes}")
        print(f"  Failures: {total_failures} ({failure_rate:.2f}%)")
        print(f"\n⏱️  LATENCY:")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        if all_errors:
            print(f"\n❌ ERRORS ({len(all_errors)} total, {len(set(all_errors))} unique):")
            for err in list(set(all_errors))[:5]:
                print(f"  - {err}")

        return results

    def run_full_test(self, config: str = "default") -> List[Dict]:
        """Run complete 3-phase stress test"""
        print(f"\n{'#'*80}")
        print(f"# E4: SQLite Stress Test - Config: {config.upper()}")
        print(f"# Test DB: {self.db_path}")
        print(f"{'#'*80}")

        self.setup_test_db(config)

        phases = [
            ("Phase 1: Single Writer (sanity)", 1, "thread"),
            ("Phase 2: 5 Threads", 5, "thread"),
            ("Phase 3: 10 Threads", 10, "thread"),
            ("Phase 4: 2 Processes", 2, "process"),
            ("Phase 5: 4 Processes", 4, "process"),
        ]

        results = []
        for phase_name, num_writers, executor_type in phases:
            phase_result = self.run_phase(phase_name, num_writers, executor_type)
            results.append(phase_result)
            time.sleep(1)  # Brief pause between phases

        return results


def analyze_results(default_results: List[Dict], optimized_results: List[Dict]):
    """Analyze and compare results from both configs"""
    print(f"\n{'='*80}")
    print("E4 FINAL ANALYSIS")
    print(f"{'='*80}")

    print(f"\n📋 SUMMARY TABLE:")
    print(f"\n{'Phase':<30} {'Config':<10} {'Fail %':<10} {'p95 (ms)':<12} {'p99 (ms)':<12}")
    print("-" * 80)

    for dr, optr in zip(default_results, optimized_results):
        print(f"{dr['phase']:<30} DEFAULT    {dr['failure_rate_pct']:>6.2f}%    "
              f"{dr['p95_latency_ms']:>8.2f}     {dr['p99_latency_ms']:>8.2f}")
        print(f"{' '*30} OPTIMIZED  {optr['failure_rate_pct']:>6.2f}%    "
              f"{optr['p95_latency_ms']:>8.2f}     {optr['p99_latency_ms']:>8.2f}")
        print()

    # Decision criteria
    print(f"\n{'='*80}")
    print("DECISION CRITERIA")
    print(f"{'='*80}")

    # Check optimized config results
    max_failure_rate = max(r['failure_rate_pct'] for r in optimized_results)
    max_p95_latency = max(r['p95_latency_ms'] for r in optimized_results)

    print(f"\nOptimized Config Performance:")
    print(f"  Max failure rate: {max_failure_rate:.2f}%")
    print(f"  Max p95 latency: {max_p95_latency:.2f}ms")

    print(f"\nThresholds:")
    print(f"  Failure rate: ≥1% = GO for Postgres")
    print(f"  P95 latency: >250ms = degraded decisions")

    # Decision
    if max_failure_rate >= 1.0:
        decision = "GO"
        reason = f"Failure rate {max_failure_rate:.2f}% exceeds 1% threshold"
    elif max_p95_latency > 250:
        decision = "PARTIAL GO"
        reason = f"P95 latency {max_p95_latency:.2f}ms may degrade decision loop"
    else:
        decision = "NO-GO"
        reason = f"Optimized config handles concurrency well (<1% failures, <250ms p95)"

    print(f"\n🎯 DECISION: {decision}")
    print(f"   Reason: {reason}")

    # Config comparison
    default_max_fail = max(r['failure_rate_pct'] for r in default_results)
    improvement = default_max_fail - max_failure_rate

    if improvement > 0.5:
        print(f"\n💡 Config optimization effect: -{improvement:.2f}% failure rate")
        print(f"   Recommendation: Enable WAL + busy_timeout before considering Postgres")


def main():
    """Run E4 experiment"""
    print("="*80)
    print("EXPERIMENT 4: SQLite Concurrency Stress Test")
    print("Testing H3a (SQLite is fine) vs H3b (contention is binding)")
    print("="*80)

    test = SQLiteStressTest()

    # Run with default config
    print("\n\n")
    default_results = test.run_full_test(config="default")

    # Run with optimized config
    print("\n\n")
    optimized_results = test.run_full_test(config="optimized")

    # Analyze
    analyze_results(default_results, optimized_results)

    print(f"\n{'='*80}")
    print("E4 COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
