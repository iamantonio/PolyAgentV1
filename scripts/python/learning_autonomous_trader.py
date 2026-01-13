#!/usr/bin/env python3
"""
Learning Autonomous Trader

Integrates ALL learning components:
1. Edge Detection - Skip unprofitable market types
2. Feature Learning - ML-based pattern recognition
3. Multi-Agent Reasoning - Prevent backwards trades
4. Isotonic Calibration - Fix overconfidence
5. Kelly Sizing - Optimal position sizing
6. Discord Alerts - Real-time notifications

This is the REAL learning bot that gets smarter with data.
"""

import os
import sys
import time
import json
import ast
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List
from decimal import Decimal

os.chdir('/home/tony/Dev/agents')
sys.path.insert(0, '/home/tony/Dev/agents')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from agents.polymarket.polymarket import Polymarket
from agents.polymarket.gamma import GammaMarketClient as Gamma
from agents.learning.integrated_learner import IntegratedLearningBot
from agents.reasoning.multi_agent import MultiAgentReasoning
from agents.utils.discord_alerts import DiscordAlerter

# Crypto edge detection - multi-signal ensemble
try:
    from agents.connectors.crypto_edge import CryptoEdgeDetector
    CRYPTO_EDGE_AVAILABLE = True
except ImportError:
    CRYPTO_EDGE_AVAILABLE = False
    print("⚠️ CryptoEdgeDetector not available - crypto edge detection disabled")

# Position sync - reconcile DB with on-chain positions
try:
    from agents.polymarket.position_sync import PositionSync
    POSITION_SYNC_AVAILABLE = True
except ImportError:
    POSITION_SYNC_AVAILABLE = False
    print("⚠️ PositionSync not available - position reconciliation disabled")

# Outcome sync - record resolved market outcomes for edge detection
try:
    from agents.polymarket.outcome_sync import OutcomeSync
    OUTCOME_SYNC_AVAILABLE = True
except ImportError:
    OUTCOME_SYNC_AVAILABLE = False
    print("⚠️ OutcomeSync not available - outcome recording disabled")


# ============================================================================
# CRITICAL INCIDENT HANDLING
# ============================================================================

class CriticalIncident(RuntimeError):
    """
    Fail-closed incident that must halt trading until operator intervention.

    Use this for dangerous recovery paths where automated retry could cause
    duplicate orders, position drift, or accounting errors.

    This exception should NEVER be caught and swallowed - it must propagate
    to the top-level loop and cause process termination.
    """
    pass


# Configuration - PERSISTENT DATABASE (survives restarts)
import os as _os
_DB_DIR = _os.path.expanduser("~/.polymarket")
_os.makedirs(_DB_DIR, exist_ok=True)
DB_PATH = _os.path.join(_DB_DIR, "learning_trader.db")
DRY_RUN = False  # LIVE TRADING ENABLED - User confirmed
MIN_CONFIDENCE = 0.20  # Minimum confidence to trade (20% = very aggressive micro-market mode)
MIN_SAMPLE_SIZE = 20  # Minimum trades before trusting learning

# CRITICAL: Bankroll must match actual exchange balance
# Risk: If real balance < BANKROLL → exposure cap won't prevent overdraft
# Risk: If real balance > BANKROLL → undertrading and missed opportunities
# TODO: Sync this with actual Polymarket balance before each run
BANKROLL = 100.0  # Available capital in USDC

# Risk Management - Exposure Cap
MAX_OPEN_EXPOSURE_PCT = 2.00  # Never exceed 200% of bankroll in open positions (allows $200 exposure on $100 bankroll)
APPLY_CALIBRATION_SHIFT = False  # Set True to apply systematic overconfidence adjustment
CALIBRATION_SHIFT = -0.044  # From 54 trades: predicted 62%, actual 57.4%

# Idempotency - Persisted Dedupe (ENABLED FOR PRODUCTION)
PERSIST_IDEMPOTENCY = True  # Hard guarantee against duplicate trades across restarts
IDEMPOTENCY_WINDOW_HOURS = 24  # How long to remember trade intents

# SAFETY LIMITS (Live Trading) - DISABLED FOR MICRO-MARKET TESTING
MAX_TRADES_PER_HOUR = 1000  # Effectively unlimited
MAX_DAILY_LOSS = 1000.0  # Effectively unlimited
EMERGENCY_STOP_LOSS = 1000.0  # Effectively unlimited

# DYNAMIC POSITION SIZING - Auto-scales based on performance milestones
ENABLE_AUTO_SCALING = True  # Automatically increase position size based on performance
BASE_POSITION_SIZE = 5.0    # Starting position size (Polymarket minimum is $5)
MAX_AUTO_POSITION_SIZE = 10.0  # Maximum auto-scaling limit (1/4 Kelly ~$9)
SCALING_START_TRADES = 25   # Minimum trades with XAI before first scaling
SCALING_WIN_RATE_THRESHOLD = 0.58  # Minimum win rate to trigger scaling (58%)

# Position size tiers based on milestones:
# 0-24 trades: $2.00 (baseline, validating XAI)
# 25-74 trades @ 58%+ WR: $5.00 (cautious increase)
# 75-149 trades @ 60%+ WR: $8.00 (approaching 1/4 Kelly)
# 150+ trades @ 60%+ WR: $10.00 (full 1/4 Kelly)

MAX_POSITION_SIZE = 2.0  # Maximum $ per trade (will auto-increase based on milestones)


class LearningAutonomousTrader:
    """
    Autonomous trader with integrated learning system

    This bot LEARNS by:
    - Tracking all predictions and outcomes
    - Identifying which markets are profitable (edge detection)
    - Learning feature patterns (ML)
    - Calibrating confidence (isotonic regression)
    - Adapting position sizes (Kelly criterion)
    """

    def __init__(self, db_path: str = DB_PATH, dry_run: bool = DRY_RUN):
        print("=" * 80)
        print("LEARNING AUTONOMOUS TRADER")
        print("=" * 80)
        print()

        self.dry_run = dry_run
        self.polymarket = Polymarket()
        self.gamma = Gamma()

        # Learning system
        self.learner = IntegratedLearningBot(db_path)

        # Multi-agent reasoning (prevents backwards trades)
        self.multi_agent = MultiAgentReasoning()

        # Discord alerts
        self.discord = DiscordAlerter()

        # Crypto edge detection (multi-signal ensemble)
        self.crypto_edge = None
        if CRYPTO_EDGE_AVAILABLE:
            try:
                self.crypto_edge = CryptoEdgeDetector()
                print("  ✅ CryptoEdgeDetector initialized (funding + OBI + sentiment)")
            except Exception as e:
                print(f"  ⚠️ CryptoEdgeDetector init failed: {e}")

        # Position sync - reconcile DB with on-chain positions
        self.position_sync = None
        self.last_sync_time = 0
        self.sync_interval = 1800  # Sync every 30 minutes
        if POSITION_SYNC_AVAILABLE:
            try:
                self.position_sync = PositionSync(db_path)
                print("  ✅ PositionSync initialized (Polymarket Data API)")
                # Sync on startup
                self._sync_positions_with_chain()
            except Exception as e:
                print(f"  ⚠️ PositionSync init failed: {e}")

        # Outcome sync - record resolved market outcomes for edge detection
        # CRITICAL: Without this, edge detection uses empty/stale data!
        self.outcome_sync = None
        self.last_outcome_sync_time = 0
        self.outcome_sync_interval = 600  # Sync outcomes every 10 minutes
        if OUTCOME_SYNC_AVAILABLE:
            try:
                self.outcome_sync = OutcomeSync(db_path)
                print("  ✅ OutcomeSync initialized (REDEEM event tracking)")
                # Sync on startup to populate historical P&L
                self._sync_resolved_outcomes()
            except Exception as e:
                print(f"  ⚠️ OutcomeSync init failed: {e}")

        # Health check: Test XAI API before trading
        print(f"Testing {self.multi_agent.provider} API access...")
        is_healthy, error_msg = self.multi_agent.health_check()

        if not is_healthy:
            print("=" * 80)
            print("🚨 STARTUP FAILED - API HEALTH CHECK")
            print("=" * 80)
            print(error_msg)
            print()
            print("Bot will NOT trade until this is resolved.")
            print("=" * 80)

            # Send Discord alert if configured
            try:
                self.discord.alert_error(
                    "Bot startup failed",
                    error_msg,
                    "Fix required before trading"
                )
            except:
                pass  # Discord alert optional

            # FAIL-CLOSED: Exit immediately
            raise RuntimeError(f"API health check failed: {error_msg}")

        print(f"✅ {self.multi_agent.provider} API healthy")
        print()

        # INCIDENT check: Refuse to start if unreconciled incidents exist
        if PERSIST_IDEMPOTENCY:
            cursor = self.learner.db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='trade_intents'")
            table_exists = cursor.fetchone()[0] > 0

            if table_exists:
                # Schema drift protection: verify required columns exist
                cursor.execute("PRAGMA table_info(trade_intents)")
                columns = {row[1] for row in cursor.fetchall()}  # row[1] = column name
                required_columns = {'intent_hash', 'status', 'timestamp', 'market_id', 'token_id'}
                missing_columns = required_columns - columns

                if missing_columns:
                    print("=" * 80)
                    print("🚨 STARTUP FAILED - DATABASE SCHEMA MISMATCH")
                    print("=" * 80)
                    print(f"   Table 'trade_intents' exists but missing columns:")
                    for col in missing_columns:
                        print(f"     - {col}")
                    print()
                    print("   Database may be partially migrated or corrupted")
                    print("   FAIL-CLOSED: Bot will NOT start until schema is fixed")
                    print("=" * 80)

                    raise CriticalIncident(
                        f"STARTUP FAILED: Database schema mismatch\n"
                        f"Missing columns in trade_intents: {missing_columns}\n\n"
                        f"Database may be partially migrated or corrupted.\n"
                        f"Manual intervention required to fix schema."
                    )

                # Now safe to query (columns verified)
                try:
                    cursor.execute("SELECT COUNT(*), MIN(timestamp) FROM trade_intents WHERE status = 'INCIDENT'")
                    incident_count, oldest_ts = cursor.fetchone()
                except Exception as query_err:
                    print("=" * 80)
                    print("🚨 STARTUP FAILED - DATABASE QUERY ERROR")
                    print("=" * 80)
                    print(f"   Error querying trade_intents: {query_err}")
                    print("   Schema appears correct but query failed")
                    print("   Database may be corrupted or locked")
                    print("=" * 80)

                    raise CriticalIncident(
                        f"STARTUP FAILED: Database query error\n"
                        f"Schema correct but query failed: {query_err}\n\n"
                        f"Database may be corrupted or locked.\n"
                        f"Manual intervention required."
                    )

                if incident_count > 0:
                    import time
                    age_hours = (time.time() - oldest_ts) / 3600 if oldest_ts else 0

                    print("=" * 80)
                    print("🚨 STARTUP BLOCKED - UNRECONCILED INCIDENTS")
                    print("=" * 80)
                    print(f"   Found {incident_count} INCIDENT marker(s) in database")
                    print(f"   Oldest incident: {age_hours:.1f}h ago")
                    print()
                    print("   These incidents require manual reconciliation before restart")
                    print("   See FINAL_CHECKLIST.md Exception Response Procedure")
                    print()
                    print("   To view incidents:")
                    print("   sqlite3 /tmp/learning_trader.db")
                    print("   SELECT * FROM trade_intents WHERE status='INCIDENT';")
                    print("=" * 80)

                    try:
                        self.discord.alert_error(
                            "🚨 Startup blocked - Unreconciled incidents",
                            f"Found {incident_count} INCIDENT marker(s)\n"
                            f"Oldest: {age_hours:.1f}h ago\n\n"
                            f"Bot will NOT start until incidents are reconciled",
                            "See FINAL_CHECKLIST.md Exception Response Procedure"
                        )
                    except Exception as discord_err:
                        print("⚠️  DISCORD ALERT FAILED")
                        print(f"   Discord error: {discord_err}")

                    # FAIL-CLOSED: Raise CriticalIncident to prevent startup
                    raise CriticalIncident(
                        f"STARTUP BLOCKED: {incident_count} unreconciled INCIDENT(s) in database\n"
                        f"Oldest incident: {age_hours:.1f}h ago\n\n"
                        f"Manual reconciliation required before restart.\n"
                        f"See FINAL_CHECKLIST.md Exception Response Procedure.\n"
                        f"Query: SELECT * FROM trade_intents WHERE status='INCIDENT';"
                    )

        # Stats
        self.trades_executed = 0
        self.markets_skipped = 0
        self.backwards_trades_prevented = 0

        # Safety tracking (live trading)
        self.trade_times = []  # Track trade timestamps
        self.daily_pnl = 0.0  # Track daily P&L
        self.total_loss = 0.0  # Track total losses

        # Duplicate trade prevention
        self.traded_market_ids = set()  # Track markets we've already traded

        # Data quality tracking (E1/E2 discrimination)
        self._invalid_market_keys = set()  # Dedupe for unique market_id failures

        # Dedupe guardrails (H3b protection)
        self.trade_attempts = {}  # market_id -> {'timestamp': ..., 'attempts': N}
        self.dedupe_window_seconds = 300  # 5 minutes

        print(f"Mode: {'🧪 DRY RUN' if self.dry_run else '💰 LIVE TRADING'}")
        print(f"Database: {db_path}")
        print(f"Min Confidence: {MIN_CONFIDENCE:.0%}")
        print()

        # Load learning summary
        self._print_learning_summary()

    def _print_learning_summary(self):
        """Print what the bot has learned so far"""
        summary = self.learner.get_learning_summary()

        print("LEARNING STATUS")
        print("-" * 80)

        # Edge detection
        edge_stats = summary.get('edge_detection', {})
        if edge_stats:
            print("Edge Detection (by market type):")
            for market_type, stats in edge_stats.items():
                symbol = "✅" if stats.get('has_edge') else "❌"
                win_rate = stats.get('win_rate') or 0
                avg_pnl = stats.get('avg_pnl_per_trade') or 0
                total_trades = stats.get('total_trades') or 0
                print(f"  {symbol} {market_type}: {win_rate:.1%} win rate, "
                      f"${avg_pnl:+.2f} avg P&L ({total_trades} trades)")
        else:
            print("Edge Detection: Not enough data yet (need 20+ trades)")

        print()

        # Feature learning
        feature_stats = summary.get('feature_learning', {})
        if feature_stats.get('trained'):
            print(f"Feature Learning: ✅ Trained on {feature_stats['total_samples']} samples")
        else:
            print("Feature Learning: Not trained yet (need 20+ samples)")

        print()

        # Calibration
        calibration_stats = summary.get('calibration', {})
        if calibration_stats.get('trained'):
            print(f"Calibration: ✅ {calibration_stats['method']} on {calibration_stats['total_samples']} samples")
        else:
            print("Calibration: Not trained yet (need 30+ samples)")

        print()
        print("=" * 80)
        print()

    def _get_dynamic_position_size(self) -> float:
        """Auto-scale position size based on performance"""
        if not ENABLE_AUTO_SCALING:
            return BASE_POSITION_SIZE
        summary = self.learner.get_learning_summary()
        edge_stats = summary.get('edge_detection', {})
        sports = edge_stats.get('sports', {})
        if not sports:
            return BASE_POSITION_SIZE
        n = sports.get('total_trades', 0)
        wr = sports.get('win_rate', 0.0)
        if n < SCALING_START_TRADES:
            size = BASE_POSITION_SIZE
        elif n < 75 and wr >= SCALING_WIN_RATE_THRESHOLD:
            size = 5.0
        elif n < 150 and wr >= 0.60:
            size = 8.0
        elif n >= 150 and wr >= 0.60:
            size = MAX_AUTO_POSITION_SIZE
        else:
            size = BASE_POSITION_SIZE
        if size != getattr(self, 'last_position_size', BASE_POSITION_SIZE):
            print(f"\n📈 AUTO-SCALE: ${getattr(self, 'last_position_size', BASE_POSITION_SIZE):.2f}→${size:.2f} ({n} trades, {wr:.1%} WR)\n")
            self.last_position_size = size
        return min(size, MAX_AUTO_POSITION_SIZE)

    def _sync_positions_with_chain(self):
        """
        Synchronize local DB with actual on-chain positions.
        Uses Polymarket Data API: https://data-api.polymarket.com/positions
        """
        if not self.position_sync:
            return

        try:
            import time
            current_time = time.time()

            # Only sync if enough time has passed (or forced on startup)
            if self.last_sync_time > 0 and (current_time - self.last_sync_time) < self.sync_interval:
                return

            print("\n🔄 Syncing positions with Polymarket...")
            result = self.position_sync.reconcile_positions(verbose=True)
            self.last_sync_time = current_time

            # Cache actual exposure for faster lookups
            self._cached_exposure = self.position_sync.get_open_exposure()
            self._cached_exposure_time = current_time

        except Exception as e:
            print(f"⚠️ Position sync error: {e}")

    def _sync_resolved_outcomes(self):
        """
        Sync resolved market outcomes from Polymarket REDEEM events.

        CRITICAL: This is what populates actual P&L data for edge detection!
        Without this, the bot makes decisions based on empty/stale data.

        Uses Polymarket Data API: https://data-api.polymarket.com/activity?type=REDEEM
        """
        if not self.outcome_sync:
            return

        try:
            import time
            current_time = time.time()

            # Only sync if enough time has passed (or forced on startup)
            if self.last_outcome_sync_time > 0 and (current_time - self.last_outcome_sync_time) < self.outcome_sync_interval:
                return

            print("\n📊 Syncing resolved outcomes from Polymarket...")
            result = self.outcome_sync.sync_outcomes(verbose=True)
            self.last_outcome_sync_time = current_time

            if result.get("matched", 0) > 0:
                print(f"   ✅ Synced {result['matched']} outcomes: {result['wins']}W/{result['losses']}L")
                print(f"   📈 P&L from synced outcomes: ${result['total_pnl']:.2f}")

                # Show updated edge data by market type
                by_type = self.outcome_sync.get_pnl_by_market_type()
                if by_type:
                    print("\n   Edge by market type (updated):")
                    for mtype, stats in by_type.items():
                        edge = "EDGE" if stats["has_edge"] else "NO EDGE"
                        print(f"      {mtype}: {stats['trades']} trades, "
                              f"{stats['win_rate']:.1%} WR, "
                              f"${stats['avg_pnl']:.2f} avg - {edge}")

        except Exception as e:
            print(f"⚠️ Outcome sync error: {e}")

    def get_current_exposure(self) -> tuple:
        """
        Calculate current open exposure across all positions.

        Uses actual on-chain positions via Polymarket Data API when available.
        Falls back to DB-based calculation if API unavailable.

        Returns:
            (total_cost: float, exposure_pct: float, remaining_capacity: float)
        """
        import time

        # Periodically sync with on-chain positions
        if self.position_sync:
            self._sync_positions_with_chain()

            # Use cached on-chain exposure if fresh (within 5 minutes)
            if hasattr(self, '_cached_exposure_time'):
                if time.time() - self._cached_exposure_time < 300:  # 5 min cache
                    total_cost = self._cached_exposure
                    exposure_pct = total_cost / BANKROLL if BANKROLL > 0 else 0
                    max_exposure = BANKROLL * MAX_OPEN_EXPOSURE_PCT
                    remaining_capacity = max(0, max_exposure - total_cost)
                    return (total_cost, exposure_pct, remaining_capacity)

        # Fallback: Use DB-based calculation
        open_positions = self.learner.db.get_open_positions()
        total_cost = sum(float(p.get('size', 0) or 0) for p in open_positions)

        exposure_pct = total_cost / BANKROLL if BANKROLL > 0 else 0
        max_exposure = BANKROLL * MAX_OPEN_EXPOSURE_PCT
        remaining_capacity = max(0, max_exposure - total_cost)

        return (total_cost, exposure_pct, remaining_capacity)

    def is_duplicate_trade_attempt(self, market_id: str, token_id: str, price: float = None, size: float = None) -> tuple:
        """
        Check if this is a duplicate trade attempt.

        Uses in-memory dedupe by default (5-minute window).
        If PERSIST_IDEMPOTENCY=True, also checks DB for hard guarantee across restarts.

        Two-phase commit:
        - Inserts PENDING intent before trade
        - Caller must call confirm_trade_intent() after success
        - Caller must call fail_trade_intent() after failure
        - Only blocks on CONFIRMED intents, not PENDING

        Returns:
            (is_duplicate: bool, reason: str, intent_hash: str or None)
        """
        import time
        import hashlib

        now = time.time()
        key = f"{market_id}:{token_id}"
        intent_hash_value = None

        # Optional: Persisted idempotency (H3b2 protection)
        if PERSIST_IDEMPOTENCY and price is not None and size is not None:
            # Create idempotency key from intent
            # Include market_id + token_id + side (BUY) + rounded price + rounded size
            intent_key = f"{market_id}:{token_id}:BUY:{price:.4f}:{size:.2f}"
            intent_hash_value = hashlib.sha256(intent_key.encode()).hexdigest()[:16]

            # Check DB for this intent
            cursor = self.learner.db.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_intents (
                    intent_hash TEXT PRIMARY KEY,
                    intent_key TEXT,
                    status TEXT,
                    timestamp REAL,
                    market_id TEXT,
                    token_id TEXT
                )
            """)

            # Clean old intents beyond window (only delete FAILED or old PENDING)
            window_start = now - (IDEMPOTENCY_WINDOW_HOURS * 3600)
            cursor.execute("""
                DELETE FROM trade_intents
                WHERE timestamp < ?
                AND (status = 'FAILED' OR status = 'PENDING')
            """, (window_start,))

            # Check if blocking intent exists (CONFIRMED or INCIDENT)
            # Single query is safer: no risk of forgetting new block statuses
            cursor.execute("""
                SELECT timestamp, intent_key, status FROM trade_intents
                WHERE intent_hash = ?
                  AND status IN ('CONFIRMED', 'INCIDENT')
                LIMIT 1
            """, (intent_hash_value,))

            blocking = cursor.fetchone()
            if blocking:
                blocking_ts, blocking_key, status = blocking
                age_hours = (now - blocking_ts) / 3600

                if status == 'CONFIRMED':
                    return (True, f"Persisted dedupe: Intent CONFIRMED {age_hours:.1f}h ago (window: {IDEMPOTENCY_WINDOW_HOURS}h)", None)

                elif status == 'INCIDENT':
                    print("=" * 80)
                    print("🚨 BLOCKED: INCIDENT marker found in database")
                    print(f"   Intent hash: {intent_hash_value}")
                    print(f"   Age: {age_hours:.1f}h ago")
                    print(f"   Market: {market_id}")
                    print(f"   Token: {token_id}")
                    print()
                    print("   This intent was marked INCIDENT during previous run")
                    print("   Operator must reconcile before retry is allowed")
                    print()
                    print("   See FINAL_CHECKLIST.md Exception Response Procedure")
                    print("=" * 80)
                    return (True, f"BLOCKED: INCIDENT marker (age: {age_hours:.1f}h) - operator must reconcile first", None)

            # Check for PENDING intent (warn but don't block - may be retry after crash)
            cursor.execute("""
                SELECT timestamp, intent_key, status FROM trade_intents
                WHERE intent_hash = ? AND status = 'PENDING'
            """, (intent_hash_value,))

            pending = cursor.fetchone()
            if pending:
                pending_ts, pending_key, status = pending
                age_seconds = now - pending_ts
                # If PENDING is recent (<60s), block it (likely in-flight)
                # If PENDING is old (>60s), allow retry (likely crash recovery)
                if age_seconds < 60:
                    return (True, f"Persisted dedupe: Intent PENDING {age_seconds:.0f}s ago (likely in-flight)", None)
                else:
                    # ⚠️ INCIDENT: Old PENDING cleanup - HARD STOP REQUIRED
                    print("=" * 80)
                    print("🚨 CRITICAL INCIDENT: Old PENDING cleanup triggered")
                    print(f"   Intent age: {age_seconds:.0f}s (threshold: 60s)")
                    print(f"   Market: {market_id}")
                    print(f"   Token: {token_id}")
                    print(f"   Intent hash: {intent_hash_value}")
                    print()
                    print("   This is exactly where silent duplicates happen!")
                    print()
                    print("   🛑 TRADING HALTED - Manual intervention required")
                    print()
                    print("   NEXT STEPS:")
                    print("   1. Check Polymarket exchange for this market/token")
                    print("   2. Verify if order actually filled")
                    print("   3. Run Exception Response Procedure (see FINAL_CHECKLIST.md)")
                    print("   4. Reconcile DB to match exchange reality")
                    print("   5. Only then restart bot")
                    print("=" * 80)

                    # Alert on Discord
                    try:
                        self.discord.alert_error(
                            "🚨 CRITICAL: Old PENDING cleanup - HALT",
                            f"Intent age: {age_seconds:.0f}s (threshold: 60s)\n"
                            f"Market: {market_id}\n"
                            f"Token: {token_id}\n"
                            f"Intent hash: {intent_hash_value}\n\n"
                            f"🛑 TRADING HALTED - This is dangerous recovery path!\n"
                            f"Manual reconciliation REQUIRED before restart.",
                            "See FINAL_CHECKLIST.md Exception Response Procedure"
                        )
                    except Exception as discord_err:
                        print("⚠️  DISCORD ALERT FAILED - You may not have been notified!")
                        print(f"   Discord error: {discord_err}")
                        print("   Check Discord manually to confirm alert was sent")

                    # Persist INCIDENT marker in DB (durable forensic trace)
                    try:
                        cursor.execute("""
                            UPDATE trade_intents
                            SET status = 'INCIDENT'
                            WHERE intent_hash = ?
                        """, (intent_hash_value,))
                        self.learner.db.conn.commit()
                        print("📝 Intent marked as INCIDENT in database for forensics")
                    except Exception as db_err:
                        print(f"⚠️  Failed to mark INCIDENT in DB: {db_err}")
                        # Continue anyway - raising is more important than DB update

                    # FAIL-CLOSED: Raise exception to halt trading
                    raise CriticalIncident(
                        f"CRITICAL INCIDENT: Old PENDING cleanup triggered\n"
                        f"Intent age: {age_seconds:.0f}s (threshold: 60s)\n"
                        f"Market: {market_id}, Token: {token_id}\n"
                        f"Intent hash: {intent_hash_value}\n\n"
                        f"Manual reconciliation required. See FINAL_CHECKLIST.md Exception Response Procedure.\n"
                        f"Do NOT restart until exchange state verified."
                    )

            # Record PENDING intent
            cursor.execute("""
                INSERT OR REPLACE INTO trade_intents (intent_hash, intent_key, status, timestamp, market_id, token_id)
                VALUES (?, ?, 'PENDING', ?, ?, ?)
            """, (intent_hash_value, intent_key, now, market_id, token_id))
            self.learner.db.conn.commit()

        # In-memory dedupe (original logic)
        if key in self.trade_attempts:
            last_attempt = self.trade_attempts[key]
            time_since = now - last_attempt['timestamp']

            # Within dedupe window?
            if time_since < self.dedupe_window_seconds:
                attempts = last_attempt['attempts']
                return (True, f"In-memory dedupe: Attempted {attempts}x in last {time_since:.0f}s (window: {self.dedupe_window_seconds}s)", intent_hash_value)

        # Not a duplicate - record this attempt
        self.trade_attempts[key] = {
            'timestamp': now,
            'attempts': self.trade_attempts.get(key, {}).get('attempts', 0) + 1
        }

        # Clean old entries (garbage collection)
        keys_to_remove = [
            k for k, v in self.trade_attempts.items()
            if now - v['timestamp'] > self.dedupe_window_seconds
        ]
        for k in keys_to_remove:
            del self.trade_attempts[k]

        return (False, "OK", intent_hash_value)

    def confirm_trade_intent(self, intent_hash: str):
        """Update persisted intent to CONFIRMED after successful trade"""
        if PERSIST_IDEMPOTENCY and intent_hash:
            cursor = self.learner.db.conn.cursor()
            cursor.execute("""
                UPDATE trade_intents
                SET status = 'CONFIRMED'
                WHERE intent_hash = ?
            """, (intent_hash,))
            self.learner.db.conn.commit()

    def fail_trade_intent(self, intent_hash: str):
        """Delete persisted intent after failed trade (allow retry)"""
        if PERSIST_IDEMPOTENCY and intent_hash:
            cursor = self.learner.db.conn.cursor()
            cursor.execute("""
                DELETE FROM trade_intents WHERE intent_hash = ?
            """, (intent_hash,))
            self.learner.db.conn.commit()

    def _extract_market_features(self, market: Dict) -> Dict:
        """
        Extract features from market data for learning

        SECURITY: Uses ast.literal_eval instead of eval() for safe parsing
        """
        try:
            # Parse market prices safely
            if isinstance(market.get('prices'), str):
                prices = ast.literal_eval(market['prices'])
            else:
                prices = market.get('prices', {})

            features = {
                'prices': prices,
                'social_sentiment': 0.5,  # Would come from sentiment analysis
                'social_volume': market.get('volume', 1000),
                'time_to_close_hours': self._calculate_time_to_close(market),
            }

            return features

        except Exception as e:
            print(f"⚠️ Feature extraction error: {e}")
            return {
                'prices': {'Yes': 0.5, 'No': 0.5},
                'social_sentiment': 0.5,
                'social_volume': 1000,
                'time_to_close_hours': 24.0
            }

    def _calculate_time_to_close(self, market: Dict) -> float:
        """Calculate hours until market closes"""
        try:
            end_date = market.get('end_date_iso')
            if end_date:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                now = datetime.now(end_dt.tzinfo)
                delta = end_dt - now
                return max(1.0, delta.total_seconds() / 3600)
        except:
            pass

        return 24.0  # Default to 24 hours

    def _classify_market_type(self, market: Dict) -> str:
        """
        Classify market type for edge detection

        Categories: politics, crypto, sports, business, other

        IMPROVED: Better sports detection (catches cricket, rugby, etc.)
        """
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        text = f"{question} {description}"

        # Politics keywords
        if any(word in text for word in ['election', 'president', 'congress', 'senate', 'vote', 'poll', 'trump', 'biden']):
            return 'politics'

        # Sports keywords (EXPANDED - catches cricket, soccer, etc.)
        sports_keywords = [
            # Major US leagues
            'nfl', 'nba', 'mlb', 'nhl', 'mls',
            # International sports
            'cricket', 'sa20', 'ipl', 't20', 'rugby', 'premier league', 'la liga', 'bundesliga',
            'champions league', 'uefa', 'fifa', 'world cup',
            # Generic sports terms
            'vs.', ' vs ', 'game', 'match', 'championship', 'playoff', 'final',
            # Bet types (strong indicator)
            'o/u', 'over', 'under', 'spread', 'handicap', 'moneyline',
            # Player props
            'points', 'rebounds', 'assists', 'yards', 'touchdowns', 'goals',
            # Teams/leagues patterns
            'eagles', 'warriors', 'lakers', 'celtics', 'yankees', 'dodgers',
            'fc', 'united', 'city', 'athletics'
        ]
        if any(word in text for word in sports_keywords):
            return 'sports'

        # Crypto keywords
        crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'blockchain',
                          'solana', 'sol', 'xrp', 'ripple', 'doge', 'cardano', 'ada']
        if any(word in text for word in crypto_keywords):
            return 'crypto'

        # Business keywords
        if any(word in text for word in ['stock', 'company', 'earnings', 'revenue', 'ceo', 'ipo', 'market cap']):
            return 'business'

        return 'other'

    def _is_coin_flip_market(self, question: str) -> bool:
        """
        Detect "Up or Down" coin-flip markets that have no edge.

        These short-term price direction markets are essentially random walks.
        """
        question_lower = question.lower()
        coin_flip_patterns = [
            'up or down',
            'higher or lower',
            'above or below',
            'rise or fall'
        ]
        return any(pattern in question_lower for pattern in coin_flip_patterns)

    def analyze_market(self, market: Dict) -> Tuple[bool, str, Optional[Dict]]:
        """
        Comprehensive market analysis with learning

        Returns:
            (should_trade, reason, trade_plan)
        """
        # DISCRIMINATING PATCH (E2 root cause fix):
        # Prefer stable identifiers; NEVER allow sentinel "unknown" to flow into API calls
        condition_id = market.get("condition_id")
        gamma_id     = market.get("id")          # Gamma often uses "id"
        market_id_f  = market.get("market_id")   # Existing fallback

        market_id = condition_id or gamma_id or market_id_f

        if not market_id:
            # Discrimination logging: what keys do we even have?
            keys = list(market.keys()) if isinstance(market, dict) else []
            q = (market.get("question") or market.get("title") or "")[:120] if isinstance(market, dict) else ""

            # Dedupe: only log unique key combinations
            key_signature = frozenset(keys)
            if key_signature not in self._invalid_market_keys:
                self._invalid_market_keys.add(key_signature)
                print("🚨 DATA_INVALID: Missing ALL market identifiers. Skipping.")
                print(f"   present_keys={keys[:40]}")
                print(f"   condition_id={condition_id} id={gamma_id} market_id={market_id_f}")
                print(f"   question/title={q}")

            self.markets_skipped += 1
            return False, "Missing market identifiers", None

        question = market['question']

        print(f"\n{'='*80}")
        print(f"ANALYZING MARKET")
        print(f"{'='*80}")
        print(f"Question: {question}")
        print()

        # Check if we've already traded this market
        if market_id in self.traded_market_ids:
            print(f"⏭️  SKIP: Already traded this market")
            self.markets_skipped += 1
            return False, "Already traded", None

        # Detect micro-markets (have time ranges in title)
        import re
        is_micro_market = bool(re.search(r'\d{1,2}:\d{2}[AP]M-\d{1,2}:\d{2}[AP]M', question))

        if is_micro_market:
            print("⚡ FAST MODE: Micro-market detected")
            return self._analyze_micro_market_fast(market, market_id, question)

        # Extract features
        features = self._extract_market_features(market)
        market_type = self._classify_market_type(market)

        print(f"Market Type: {market_type}")
        print(f"Time to Close: {features['time_to_close_hours']:.1f} hours")
        print()

        # STEP 0: Coin-flip market filter (skip "Up or Down" markets without edge)
        if self._is_coin_flip_market(question):
            print("⚠️  COIN-FLIP MARKET DETECTED")
            print("-" * 80)

            # For coin-flip markets, we REQUIRE multi-signal edge from CryptoEdgeDetector
            if self.crypto_edge and market_type == 'crypto':
                token = self.crypto_edge.detect_token_from_question(question)
                if token:
                    # Get market price for edge check
                    yes_price = features.get('prices', {}).get('Yes', 0.5)
                    edge_result = self.crypto_edge.get_combined_edge(token, yes_price)

                    if edge_result['should_trade']:
                        print(f"✅ CRYPTO EDGE FOUND: {edge_result['combined_signal']} @ {edge_result['combined_confidence']:.1%}")
                        # Store edge info for later use in prediction
                        features['crypto_edge'] = edge_result
                    else:
                        reason = f"Coin-flip market, no multi-signal edge: {edge_result.get('skip_reason', 'insufficient signals')}"
                        print(f"❌ SKIP: {reason}")
                        self.markets_skipped += 1
                        return False, reason, None
                else:
                    reason = "Coin-flip market, token not recognized for edge detection"
                    print(f"❌ SKIP: {reason}")
                    self.markets_skipped += 1
                    return False, reason, None
            else:
                reason = "Coin-flip market without edge detection capability"
                print(f"❌ SKIP: {reason}")
                self.markets_skipped += 1
                return False, reason, None

        # STEP 1: Edge Detection Check (historical P&L based)
        print("STEP 1: Edge Detection")
        print("-" * 80)

        # For crypto markets, also check for multi-signal edge even if not coin-flip
        if market_type == 'crypto' and self.crypto_edge and 'crypto_edge' not in features:
            token = self.crypto_edge.detect_token_from_question(question)
            if token:
                yes_price = features.get('prices', {}).get('Yes', 0.5)
                edge_result = self.crypto_edge.get_combined_edge(token, yes_price)
                features['crypto_edge'] = edge_result

                # Log the edge analysis
                if edge_result['combined_signal']:
                    print(f"  Crypto Edge: {edge_result['combined_signal']} @ {edge_result['combined_confidence']:.1%}")
                    for r in edge_result.get('reasoning', [])[:3]:
                        print(f"    • {r}")

        should_trade, reason, analysis = self.learner.should_trade_market(
            features,
            market_type,
            MIN_CONFIDENCE
        )

        if not should_trade:
            print(f"❌ SKIP: {reason}")
            self.markets_skipped += 1
            self.discord.alert_skipped_market(question, reason)
            return False, reason, None

        print(f"✅ PASS: {reason}")
        print()

        # STEP 2: Multi-Agent Prediction
        print("STEP 2: Multi-Agent Prediction")
        print("-" * 80)

        try:
            result = self.multi_agent.full_reasoning_pipeline(
                question=question,
                description=market.get('description', ''),
                market_data=features
            )

            # Check verification
            if not result['verification']['passed']:
                print(f"❌ Verification failed: {result['verification']['message']}")
                return False, result['verification']['message'], None

            decision = result['decision']
            prediction = result['prediction']

            print(f"Prediction: {decision.outcome_to_buy}")
            print(f"Raw Confidence: {decision.confidence:.1%}")
            print(f"Reasoning: {decision.reasoning[:200]}...")
            print()

        except Exception as e:
            print(f"❌ Multi-agent prediction failed: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Prediction error: {e}", None

        # STEP 3: Calibrate Confidence
        print("STEP 3: Calibrate Confidence")
        print("-" * 80)

        calibrated_confidence, method = self.learner.adjust_confidence(
            decision.confidence,
            market_type
        )

        print(f"Raw: {decision.confidence:.1%}")
        print(f"Calibrated: {calibrated_confidence:.1%} ({method})")
        print()

        # Check minimum confidence
        if calibrated_confidence < MIN_CONFIDENCE:
            reason = f"Confidence {calibrated_confidence:.1%} below minimum {MIN_CONFIDENCE:.1%}"
            print(f"❌ SKIP: {reason}")
            self.markets_skipped += 1
            return False, reason, None

        # STEP 4: Calculate Position Size
        print("STEP 4: Position Sizing")
        print("-" * 80)

        outcome = decision.outcome_to_buy
        market_price = features['prices'].get(outcome, 0.5)

        # Get dynamic position size (auto-scales based on performance)
        max_position = self._get_dynamic_position_size()

        position_size, sizing_explanation = self.learner.calculate_position_size(
            probability=calibrated_confidence,
            market_price=market_price,
            bankroll=BANKROLL,
            max_position=max_position,
            kelly_fraction=0.25
        )

        # Check total exposure cap
        total_cost, exposure_pct, remaining = self.get_current_exposure()

        if remaining <= 0:
            reason = f"Exposure cap reached: {exposure_pct:.1%} of bankroll deployed (${total_cost:.2f})"
            print(f"⚠️  EXPOSURE CAP REACHED: {exposure_pct:.1%} of bankroll in use")
            print(f"   Open positions: ${total_cost:.2f} / Max: ${BANKROLL * MAX_OPEN_EXPOSURE_PCT:.2f}")
            print(f"   SKIP TRADE until positions close")
            self.markets_skipped += 1
            return False, reason, None

        # Cap size by remaining capacity
        if position_size > remaining:
            print(f"⚠️  EXPOSURE CAP: Size reduced ${position_size:.2f} → ${remaining:.2f}")
            print(f"   Remaining capacity: ${remaining:.2f}")
            position_size = remaining

        # Verify we're not going over (safety check)
        if position_size + total_cost > BANKROLL * MAX_OPEN_EXPOSURE_PCT:
            reason = f"Trade would exceed exposure limit: ${position_size + total_cost:.2f} > ${BANKROLL * MAX_OPEN_EXPOSURE_PCT:.2f}"
            print(f"⚠️  EXPOSURE CAP: {reason}")
            self.markets_skipped += 1
            return False, reason, None

        print(f"Market Price: ${market_price:.4f}")
        print(f"Position Size: ${position_size:.2f}")
        print(f"Explanation: {sizing_explanation}")
        print(f"📊 Exposure: ${total_cost:.2f} → ${total_cost + position_size:.2f} ({(total_cost + position_size)/BANKROLL:.1%} of bankroll)")
        print()

        if position_size < 5.0:
            reason = f"Position size ${position_size:.2f} below Polymarket minimum ($5)"
            print(f"❌ SKIP: {reason}")
            self.markets_skipped += 1
            return False, reason, None

        # STEP 5: Final Verification (Already done in Step 2)
        print("STEP 5: Final Verification")
        print("-" * 80)
        print(f"✅ Already verified in multi-agent pipeline")
        print()

        # Build trade plan
        trade_plan = {
            'market_id': market_id,
            'market': market,  # Full market object needed for execute_market_order
            'question': question,
            'market_type': market_type,
            'outcome': outcome,
            'raw_confidence': decision.confidence,
            'calibrated_confidence': calibrated_confidence,
            'calibration_method': method,
            'market_price': market_price,
            'position_size': position_size,
            'reasoning': decision.reasoning,
            'features': features,
            'analysis': analysis
        }

        print("=" * 80)
        print(f"✅ TRADE APPROVED")
        print(f"Action: BUY {outcome} at ${market_price:.4f}")
        print(f"Size: ${position_size:.2f}")
        print(f"Confidence: {calibrated_confidence:.1%}")
        print("=" * 80)
        print()

        return True, "Trade approved", trade_plan

    def _analyze_micro_market_fast(self, market: Dict, market_id: str, question: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Fast analysis path for micro-markets using single LLM call with gpt-3.5-turbo
        Targets < 5 second analysis time

        UPDATED: Now applies crypto edge detection to filter coin-flip markets
        """
        import random
        from openai import OpenAI

        # Extract basic info
        market_price = float(market.get('price', '0.5'))

        # CRITICAL: Check for coin-flip markets and require multi-signal edge
        if self._is_coin_flip_market(question) and self.crypto_edge:
            token = self.crypto_edge.detect_token_from_question(question)
            if token:
                print(f"  🔍 Checking crypto edge for {token}...")
                edge_result = self.crypto_edge.get_combined_edge(token, market_price)

                if not edge_result['should_trade']:
                    reason = f"Micro-market coin-flip, no edge: {edge_result.get('skip_reason', 'insufficient signals')}"
                    print(f"  ❌ SKIP: {reason}")
                    self.markets_skipped += 1
                    return False, reason, None

                # Use edge signal to inform prediction
                if edge_result['combined_signal']:
                    print(f"  ✅ EDGE FOUND: {edge_result['combined_signal']} @ {edge_result['combined_confidence']:.1%}")
            else:
                print(f"  ❌ SKIP: Coin-flip market, token not recognized")
                self.markets_skipped += 1
                return False, "Coin-flip market, token not recognized", None

        # Simple fast prediction using XAI (Grok-4.1-Fast-Reasoning)
        client = OpenAI(
            api_key=os.getenv("XAI_API_KEY"),
            base_url="https://api.x.ai/v1"
        )
        prompt = f"""Predict: {question}

Quick analysis - respond in 10 words or less:
PREDICTION: YES or NO
CONFIDENCE: 0.5-0.8 (as decimal)

Keep it simple and fast."""

        try:
            response = client.chat.completions.create(
                model="grok-4-1-fast-reasoning",  # XAI's fast reasoning model
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=50
            )

            content = response.choices[0].message.content

            # Parse response
            outcome = "YES" if "YES" in content.upper() else "NO"

            # Extract confidence or default to random 55-65%
            try:
                import re
                conf_match = re.search(r'0\.\d+', content)
                confidence = float(conf_match.group()) if conf_match else random.uniform(0.55, 0.65)
            except:
                confidence = random.uniform(0.55, 0.65)

        except Exception as e:
            print(f"⚡ Fast prediction failed: {e}, using random")
            outcome = random.choice(["YES", "NO"])
            confidence = random.uniform(0.55, 0.65)

        # Minimal calibration (reduce by 10%)
        calibrated_confidence = confidence * 0.9

        # Check threshold
        if calibrated_confidence < MIN_CONFIDENCE:
            print(f"❌ SKIP: Confidence {calibrated_confidence:.1%} below {MIN_CONFIDENCE:.0%}")
            self.markets_skipped += 1
            return False, "Confidence too low", None

        # Dynamic position sizing (auto-scales based on performance)
        position_size = self._get_dynamic_position_size()

        print(f"⚡ Fast Decision: {outcome} at {calibrated_confidence:.1%} confidence")
        print(f"💰 Position: ${position_size:.2f}")

        # Build trade plan
        trade_plan = {
            'market_id': market_id,
            'market': market,
            'question': question,
            'market_type': 'crypto',  # Fast path only handles crypto micro-markets
            'outcome': outcome,
            'calibrated_confidence': calibrated_confidence,  # FIX: was 'confidence'
            'market_price': market_price,
            'position_size': position_size,
            'reasoning': f"Fast micro-market prediction: {outcome}",
            'features': {},
            'analysis': {}
        }

        return True, "Fast trade approved", trade_plan

    def execute_trade(self, trade_plan: Dict) -> bool:
        """
        Execute trade and record for learning

        Returns:
            True if successful, False otherwise
        """
        try:
            market_id = trade_plan['market_id']
            outcome = trade_plan['outcome']
            size = trade_plan['position_size']
            price = trade_plan['market_price']

            # Record prediction BEFORE execution (for learning)
            # CRITICAL: Set trade_executed=False initially, update to True only on success
            pred_id = self.learner.record_prediction_and_learn(
                market_id=market_id,
                question=trade_plan['question'],
                predicted_outcome=outcome,
                predicted_probability=trade_plan['calibrated_confidence'],
                confidence=trade_plan['calibrated_confidence'],
                reasoning=trade_plan['reasoning'],
                market_type=trade_plan['market_type'],
                market_data=trade_plan['features'],
                trade_executed=False,  # FIXED: Don't lie before execution
                trade_size=size,
                trade_price=price
            )

            print(f"📊 Prediction recorded (ID: {pred_id})")

            # Execute trade
            trade_success = False
            if self.dry_run:
                print(f"🧪 DRY RUN: Would buy {size:.2f} USDC of {outcome} at ${price:.4f}")
                result = "DRY_RUN_SUCCESS"
                trade_success = True
            else:
                # LIVE EXECUTION - ENABLED BY USER REQUEST
                print(f"💰 LIVE TRADE: Buying {size:.2f} USDC of {outcome} at ${price:.4f}")
                try:
                    # Execute LIMIT order with proper decimal precision
                    import ast
                    from py_clob_client.order_builder.constants import BUY
                    from py_clob_client.clob_types import OrderArgs, OrderType
                    from decimal import Decimal, ROUND_DOWN

                    # Extract token ID from market data
                    market_data = trade_plan['market']

                    # Extract token IDs (clobTokenIds is a string like "['token1', 'token2']")
                    if 'clobTokenIds' in market_data:
                        token_ids_str = market_data['clobTokenIds']
                        if isinstance(token_ids_str, str):
                            token_ids = ast.literal_eval(token_ids_str)
                        else:
                            token_ids = token_ids_str
                    else:
                        raise Exception(f"Cannot find clobTokenIds in market data. Available keys: {list(market_data.keys())}")

                    # CRITICAL FIX: token_ids[0] = YES, token_ids[1] = NO (confirmed via actual trade)
                    token_id = token_ids[0] if outcome == "YES" else token_ids[1]

                    print(f"Token ID: {token_id}")

                    # Check for duplicate trade attempt (H3b protection)
                    # Pass price and size for optional persisted idempotency
                    is_duplicate, dedupe_reason, intent_hash = self.is_duplicate_trade_attempt(
                        market_id, token_id, price=price, size=size
                    )

                    if is_duplicate:
                        print(f"⚠️  DUPLICATE TRADE BLOCKED: {dedupe_reason}")
                        print(f"   Market: {trade_plan['question'][:60]}")
                        print(f"   Token: {token_id}")

                        # Alert on Discord (potential bug indicator)
                        try:
                            self.discord.alert_error(
                                "Duplicate trade blocked",
                                f"Market: {trade_plan['question'][:100]}\n"
                                f"Reason: {dedupe_reason}\n"
                                f"This may indicate retry logic gone wrong",
                                "Check for infinite loops or error handling issues"
                            )
                        except:
                            pass  # Discord alert optional

                        return False  # Block the duplicate trade

                    # ================================================================
                    # TRADE ATTEMPT LOG (for incident response / copy-paste recovery)
                    # ================================================================
                    # Only log when actually proceeding to place order
                    intent_key = f"{market_id}:{token_id}:BUY:{price:.4f}:{size:.2f}" if intent_hash else "N/A"
                    print("=" * 80)
                    print("TRADE ATTEMPT LOG (for incident response)")
                    print(f"  status: PROCEEDING_TO_PLACE_ORDER")
                    print(f"  intent_hash: {intent_hash or 'N/A'}")
                    print(f"  intent_key: {intent_key}")
                    print(f"  market_id: {market_id}")
                    print(f"  token_id: {token_id}")
                    print(f"  side: BUY")
                    print(f"  price: ${price:.4f}")
                    print(f"  size: ${size:.2f}")
                    print(f"  timestamp_utc: {datetime.now(timezone.utc).isoformat()}")
                    print("=" * 80)

                    # Get best price from orderbook (use best ask for buying)
                    best_ask = market_data.get('bestAsk', price)
                    if best_ask:
                        limit_price = float(best_ask)
                    else:
                        limit_price = price

                    # Add 1% to price to ensure fill (market taking)
                    limit_price = min(limit_price * 1.01, 0.99)  # Cap at $0.99

                    # Round price to proper precision (max 4 decimals for price)
                    limit_price = float(Decimal(str(limit_price)).quantize(Decimal('0.0001'), rounding=ROUND_DOWN))

                    # Calculate shares: shares = amount / price
                    # Round to 2 decimals (taker amount constraint)
                    shares = size / limit_price
                    shares = float(Decimal(str(shares)).quantize(Decimal('0.01'), rounding=ROUND_DOWN))

                    print(f"Limit order: {shares:.2f} shares at ${limit_price:.4f}")

                    # Create limit order with GTC
                    order_args = OrderArgs(
                        token_id=token_id,
                        price=limit_price,
                        size=shares,
                        side=BUY,
                    )

                    signed_order = self.polymarket.client.create_order(order_args)
                    print(f"Signed order: {signed_order}")

                    # Post GTC limit order
                    resp = self.polymarket.client.post_order(signed_order, orderType=OrderType.GTC)
                    print(f"✅ Limit order placed (GTC): {resp}")
                    result = str(resp)

                    # Record position opening for sell tracking
                    self.learner.db.record_position_open(
                        market_id=market_id,
                        token_id=token_id,
                        entry_price=limit_price,
                        size=size
                    )
                    print(f"📍 Position tracked: {token_id}")

                    # Confirm persisted intent (two-phase commit)
                    self.confirm_trade_intent(intent_hash)

                    # Mark as successful execution
                    trade_success = True

                except CriticalIncident:
                    # DO NOT delete intent on CriticalIncident
                    # DO NOT retry, DO NOT continue
                    # Preserving PENDING state is critical for manual reconciliation
                    raise

                except Exception as e:
                    print(f"❌ Trade execution failed: {e}")
                    import traceback
                    traceback.print_exc()
                    result = f"FAILED: {e}"

                    # Delete persisted intent on failure (allow retry)
                    # Only for normal exceptions, NOT CriticalIncident
                    self.fail_trade_intent(intent_hash)

                    # Mark as failed execution
                    trade_success = False

            # CRITICAL: Only update database and send alerts if trade actually succeeded
            if trade_success:
                # Update prediction to mark as executed
                self.learner.db.update_prediction_execution(
                    prediction_id=pred_id,
                    trade_executed=True,
                    execution_result="EXECUTED"
                )

                # Discord alert (only on success)
                self.discord.alert_trade_executed(
                    market=trade_plan['question'],
                    outcome=outcome,
                    size=size,
                    price=price,
                    dry_run=self.dry_run
                )

                # Track trade time for safety limits
                if not self.dry_run:
                    self.trade_times.append(datetime.now())

                # Mark this market as traded to prevent duplicates
                self.traded_market_ids.add(market_id)

                self.trades_executed += 1

                # Print learning progress every 10 trades
                if self.trades_executed % 10 == 0:
                    self._send_learning_progress_alert()

                return True
            else:
                # Trade failed - update database with failure
                self.learner.db.update_prediction_execution(
                    prediction_id=pred_id,
                    trade_executed=False,
                    execution_result=f"FAILED: {result if 'result' in locals() else 'Unknown error'}"
                )
                return False

        except Exception as e:
            print(f"❌ Trade execution failed: {e}")
            return False

    def _send_learning_progress_alert(self):
        """Send Discord alert with learning progress"""
        summary = self.learner.get_learning_summary()
        perf = summary.get('performance', {})

        total_trades = perf.get('total_predictions', 0)
        win_rate = perf.get('win_rate', 0.0)
        total_pnl = perf.get('total_pnl', 0.0)
        brier_score = perf.get('brier_score')

        self.discord.alert_learning_update(
            total_trades=total_trades,
            win_rate=win_rate,
            total_pnl=total_pnl,
            brier_score=brier_score
        )

    def _check_safety_limits(self) -> Tuple[bool, str]:
        """
        Check if we've hit any safety limits

        Returns:
            (safe_to_trade, reason)
        """
        from datetime import datetime, timedelta

        if self.dry_run:
            return True, "Dry run mode (no limits)"

        now = datetime.now()

        # Check trades per hour
        one_hour_ago = now - timedelta(hours=1)
        recent_trades = [t for t in self.trade_times if t > one_hour_ago]

        if len(recent_trades) >= MAX_TRADES_PER_HOUR:
            return False, f"Hit hourly limit ({MAX_TRADES_PER_HOUR} trades/hour)"

        # Check daily loss limit
        if abs(self.daily_pnl) > MAX_DAILY_LOSS:
            return False, f"Hit daily loss limit (${abs(self.daily_pnl):.2f} > ${MAX_DAILY_LOSS})"

        # Check emergency stop loss
        if abs(self.total_loss) > EMERGENCY_STOP_LOSS:
            return False, f"🚨 EMERGENCY STOP: Total loss ${abs(self.total_loss):.2f} > ${EMERGENCY_STOP_LOSS}"

        return True, "All safety checks passed"

    def check_and_manage_positions(self):
        """
        Check open positions and sell if stop-loss or take-profit conditions met

        Implements Hypothesis 1 (Stop-Loss) and Hypothesis 2 (Take-Profit)
        """
        print("\n" + "=" * 80)
        print("POSITION MANAGEMENT")
        print("=" * 80)

        open_positions = self.learner.db.get_open_positions()

        if not open_positions:
            print("No open positions")
            return

        print(f"Found {len(open_positions)} open position(s)\n")

        for pos in open_positions:
            market_id = pos['market_id']
            token_id = pos['token_id']
            question = pos['question']
            entry_price = pos['entry_price']
            size = pos['size']
            outcome = pos['predicted_outcome']

            # Validate position data before processing
            if entry_price is None or size is None:
                print(f"Position: {question[:60]}...")
                print(f"  ⚠️  Incomplete position data (entry_price={entry_price}, size={size}), skipping")
                continue

            print(f"Position: {question[:60]}...")
            print(f"  Entry: ${entry_price:.4f} | Size: ${size:.2f} | Outcome: {outcome}")

            # Get current market price
            try:
                market_data = self.gamma.get_market(market_id)

                # Get token IDs (defensive check for list length)
                token_ids = market_data.get('clobTokenIds') or []
                if len(token_ids) < 2:
                    print(f"  ⚠️  Invalid clobTokenIds (expected 2, got {len(token_ids)})")
                    print(f"      market_id={market_id}")
                    print(f"      market_data keys={list(market_data.keys())[:20] if isinstance(market_data, dict) else 'NOT_DICT'}")
                    continue

                # Get token ID for our outcome (YES=0, NO=1)
                token_id_to_check = token_ids[0] if outcome == "YES" else token_ids[1]

                if not token_id_to_check:
                    print(f"  ⚠️  Missing token ID for {outcome}, skipping")
                    continue

                # Fetch current orderbook price for this token
                try:
                    orderbook = self.polymarket.client.get_order_book(token_id_to_check)
                    bids = orderbook.get('bids', [])
                    if bids:
                        current_price = float(bids[0]['price'])
                    else:
                        print(f"  ⚠️  No bids available, skipping")
                        continue
                except Exception as ob_err:
                    print(f"  ⚠️  Could not fetch orderbook: {ob_err}, skipping")
                    continue

                # Calculate P&L %
                if current_price is None or entry_price in (None, 0):
                    print(f"  ⚠️  Invalid price data (current={current_price}, entry={entry_price}), skipping")
                    continue

                pnl_pct = (current_price - entry_price) / entry_price
                print(f"  Current: ${current_price:.4f} | P&L: {pnl_pct:+.1%}")

                # Check stop-loss conditions (Hypothesis 1)
                if pnl_pct <= -0.50:
                    print(f"  🛑 STOP-LOSS: Down >50%, closing position")
                    self._execute_sell(market_id, token_id, size, current_price, "stop_loss_50pct")
                    continue

                if pnl_pct <= -0.25:
                    # Check time to close
                    time_to_close = pos.get('time_to_close_hours', 999)
                    if time_to_close < 6:
                        print(f"  🛑 STOP-LOSS: Down 25-50% with <6h to close")
                        self._execute_sell(market_id, token_id, size, current_price, "stop_loss_25pct_time")
                        continue

                # Check take-profit conditions (Hypothesis 2)
                if pnl_pct >= 0.30:
                    print(f"  ✅ TAKE-PROFIT: Up >30%, locking gains")
                    self._execute_sell(market_id, token_id, size, current_price, "take_profit_30pct")
                    continue

                if pnl_pct >= 0.15:
                    time_to_close = pos.get('time_to_close_hours', 999)
                    if time_to_close < 12:
                        print(f"  ✅ TAKE-PROFIT: Up >15% with <12h to close")
                        self._execute_sell(market_id, token_id, size, current_price, "take_profit_15pct_time")
                        continue

                print(f"  ✓ HOLD: Within acceptable range")

            except Exception as e:
                print(f"  ❌ Error checking position: {e}")
                import traceback
                traceback.print_exc()

        print("=" * 80)

    def _execute_sell(
        self,
        market_id: str,
        token_id: str,
        size: float,
        current_price: float,
        reason: str
    ):
        """
        Execute a sell order to close a position

        Uses GTC limit order at current bid price
        """
        from decimal import Decimal, ROUND_DOWN
        from py_clob_client.order_builder.constants import SELL
        from py_clob_client.clob_types import OrderArgs, OrderType

        print(f"\n  Executing SELL order...")
        print(f"  Token: {token_id}")
        print(f"  Size: ${size:.2f}")
        print(f"  Price: ${current_price:.4f}")
        print(f"  Reason: {reason}")

        if self.dry_run:
            print(f"  🧪 DRY RUN: Would sell position")
            pnl = size * (current_price - self.learner.db.get_open_positions()[0]['entry_price']) / self.learner.db.get_open_positions()[0]['entry_price']
            self.learner.db.close_position(market_id, current_price, reason)
            print(f"  💰 Simulated P&L: ${pnl:+.2f}")
            return

        try:
            # Round to proper decimal precision
            limit_price = float(Decimal(str(current_price)).quantize(
                Decimal('0.0001'), rounding=ROUND_DOWN
            ))

            shares = float(Decimal(str(size / current_price)).quantize(
                Decimal('0.01'), rounding=ROUND_DOWN
            ))

            # Create sell order
            order_args = OrderArgs(
                token_id=token_id,
                price=limit_price,
                size=shares,
                side=SELL,
            )

            signed_order = self.polymarket.client.create_order(order_args)
            resp = self.polymarket.client.post_order(signed_order, orderType=OrderType.GTC)

            print(f"  ✅ SELL ORDER PLACED")
            print(f"  Order ID: {resp.get('orderID', 'N/A')}")

            # Close position in database
            pnl = self.learner.db.close_position(market_id, current_price, reason)

            if pnl:
                print(f"  💰 Realized P&L: ${pnl:+.2f}")

                # Discord alert
                self.discord.alert_position_closed(
                    market=market_id[:30],
                    reason=reason,
                    pnl=pnl,
                    exit_price=current_price
                )

        except Exception as e:
            print(f"  ❌ SELL FAILED: {e}")
            import traceback
            traceback.print_exc()

    def _get_active_events(self) -> List[Dict]:
        """Get active, unclosed events from Polymarket"""
        try:
            # Use Gamma API directly with closed=false to get ONLY active markets
            raw_events = self.gamma.get_events(querystring_params={
                "closed": "false",
                "limit": 50  # Get more events to choose from
            })

            print(f"  Active events from API: {len(raw_events)}")

            # Convert to SimpleEvent format
            from agents.utils.objects import SimpleEvent
            usable_events = []
            for event_data in raw_events:
                try:
                    mapped = self.polymarket.map_api_to_event(event_data)
                    usable_events.append(SimpleEvent(**mapped))
                except Exception as e:
                    pass  # Skip events that can't be mapped

            print(f"  Usable events: {len(usable_events)}")
            return usable_events

        except Exception as e:
            print(f"❌ Error getting events: {e}")
            return []

    def scan_and_trade(self, max_trades: int = 1):
        """
        Scan markets and execute trades

        Args:
            max_trades: Maximum trades per scan (default 1)
        """
        print(f"\n{'='*80}")
        print(f"MARKET SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print()

        # Check safety limits first
        safe_to_trade, safety_reason = self._check_safety_limits()
        if not safe_to_trade:
            print(f"⛔ SAFETY LIMIT HIT: {safety_reason}")
            print("Trading paused until limits reset")
            return

        print(f"✅ Safety check: {safety_reason}")
        print()

        # Check and manage existing positions FIRST
        self.check_and_manage_positions()

        # Clear traded markets set at start of each scan (allows trading new time windows)
        self.traded_market_ids.clear()

        try:
            # Get NEW markets only (sorted by creation date, most recent first)
            markets = self.gamma.get_markets(querystring_params={
                "closed": "false",
                "order": "startDate",  # Sort by creation date (newest first)
                "ascending": "false",
                "limit": 50
            })

            # Filter out markets with past end dates (prevent trading expired markets)
            now = datetime.now(timezone.utc)
            valid_markets = []
            expired_count = 0
            for m in markets:
                end_date_str = m.get("endDate") or m.get("end_date_iso")
                if end_date_str:
                    try:
                        end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                        if end_date > now:
                            valid_markets.append(m)
                        else:
                            expired_count += 1
                    except (ValueError, TypeError):
                        valid_markets.append(m)  # Keep if can't parse date
                else:
                    valid_markets.append(m)  # Keep if no end date specified

            markets = valid_markets

            print(f"Found {len(markets)} active markets from API (filtered {expired_count} expired)")
            print()

            trades_made = 0

            for market in markets:
                if trades_made >= max_trades:
                    break

                # Analyze market
                should_trade, reason, trade_plan = self.analyze_market(market)

                if should_trade and trade_plan:
                    # Execute
                    success = self.execute_trade(trade_plan)
                    if success:
                        trades_made += 1

            print(f"\n{'='*80}")
            print(f"SCAN COMPLETE")
            print(f"{'='*80}")
            print(f"Trades Executed: {trades_made}")
            print(f"Markets Skipped: {self.markets_skipped}")
            print(f"Backwards Trades Prevented: {self.backwards_trades_prevented}")
            print(f"{'='*80}\n")

        except CriticalIncident:
            # DO NOT swallow CriticalIncident - must halt trading
            raise

        except Exception as e:
            print(f"❌ Scan error: {e}")
            import traceback
            traceback.print_exc()

    def run_continuous(self, scan_interval: int = 300):
        """
        Run continuous trading loop

        Args:
            scan_interval: Seconds between scans (default 300 = 5 minutes)
        """
        print(f"\n{'='*80}")
        print("STARTING CONTINUOUS LEARNING TRADER")
        print(f"{'='*80}")
        print(f"Scan Interval: {scan_interval}s ({scan_interval/60:.1f} minutes)")
        print(f"Press Ctrl+C to stop")
        print(f"{'='*80}\n")

        try:
            while True:
                # Sync resolved outcomes before trading decisions
                # CRITICAL: This ensures edge detection uses current P&L data
                self._sync_resolved_outcomes()

                self.scan_and_trade(max_trades=10)  # Higher for micro-markets

                print(f"⏸️ Waiting {scan_interval}s until next scan...")
                time.sleep(scan_interval)

        except CriticalIncident as e:
            print("\n" + "=" * 80)
            print("🛑 TRADING HALTED - CriticalIncident")
            print("=" * 80)
            print(str(e))
            print("=" * 80)
            print()
            print("⚠️  CRITICAL: This is a fail-closed incident requiring manual intervention")
            print("   DO NOT restart the bot until you've verified exchange state")
            print("   See FINAL_CHECKLIST.md Exception Response Procedure")
            print()
            print("   Exit code: 42 (prevents systemd auto-restart)")
            print("=" * 80)
            self._print_final_stats()
            # Exit with code 42 (distinct from normal errors)
            # Configure systemd with RestartPreventExitStatus=42 to prevent restart loop
            sys.exit(42)

        except KeyboardInterrupt:
            print("\n🛑 Stopping continuous trader")
            self._print_final_stats()

    def _print_final_stats(self):
        """Print final statistics"""
        print(f"\n{'='*80}")
        print("FINAL STATISTICS")
        print(f"{'='*80}")
        print(f"Total Trades: {self.trades_executed}")
        print(f"Markets Skipped: {self.markets_skipped}")
        print(f"Backwards Trades Prevented: {self.backwards_trades_prevented}")
        print()

        summary = self.learner.get_learning_summary()
        perf = summary.get('performance', {})

        if perf:
            print(f"Win Rate: {perf.get('win_rate', 0):.1%}")
            print(f"Total P&L: ${perf.get('total_pnl', 0):+.2f}")
            print(f"Brier Score: {perf.get('brier_score', 0):.4f}")

        print(f"{'='*80}\n")

        self.learner.close()


def main():
    """Run learning autonomous trader"""
    import argparse

    parser = argparse.ArgumentParser(description="Learning Autonomous Trader")
    parser.add_argument('--live', action='store_true', help='Enable live trading (default: dry run)')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=300, help='Scan interval in seconds (default: 300)')
    parser.add_argument('--max-trades', type=int, default=1, help='Max trades per scan (default: 1)')

    args = parser.parse_args()

    trader = LearningAutonomousTrader(dry_run=not args.live)

    if args.continuous:
        trader.run_continuous(scan_interval=args.interval)
    else:
        trader.scan_and_trade(max_trades=args.max_trades)


if __name__ == "__main__":
    try:
        main()
    except CriticalIncident as e:
        # Ensure ALL CriticalIncidents (including startup-block) exit with code 42
        # This prevents systemd restart loops (RestartPreventExitStatus=42)
        print("\n" + "=" * 80)
        print("🛑 CRITICAL INCIDENT - Process Halted")
        print("=" * 80)
        print(str(e))
        print("=" * 80)
        print("\nExiting with code 42 (systemd will NOT auto-restart)")
        print("See FINAL_CHECKLIST.md for incident response procedure")
        print("=" * 80)
        sys.exit(42)
