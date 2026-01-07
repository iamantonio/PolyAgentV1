"""
Trade History Database - Foundation of the Learning System

Stores all predictions, trades, and outcomes for:
- Performance tracking
- Calibration analysis
- Pattern recognition
- Meta-learning about strategy performance
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from decimal import Decimal


class TradeHistoryDB:
    """Persistent database of all trading activity and predictions"""

    def __init__(self, db_path: str = "/tmp/trade_learning.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Return rows as dicts
        self._init_schema()

    def _init_schema(self):
        """Create database schema if it doesn't exist"""
        cursor = self.conn.cursor()

        # Main predictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                market_id TEXT NOT NULL,
                question TEXT NOT NULL,
                market_type TEXT,

                -- Prediction details
                predicted_outcome TEXT NOT NULL,
                predicted_probability REAL NOT NULL,
                confidence REAL NOT NULL,
                reasoning TEXT,

                -- Market context at prediction time
                market_price_yes REAL,
                market_price_no REAL,
                time_to_close_hours REAL,
                social_sentiment REAL,
                social_volume INTEGER,

                -- Strategy used
                strategy TEXT NOT NULL,
                agent_version TEXT,

                -- Trade execution
                trade_executed BOOLEAN DEFAULT 0,
                trade_size_usdc REAL,
                trade_price REAL,
                execution_result TEXT,

                -- Position tracking (NEW)
                token_id TEXT,
                position_open BOOLEAN DEFAULT 0,
                entry_timestamp TEXT,
                exit_timestamp TEXT,
                exit_price REAL,
                exit_reason TEXT,

                -- Outcome (filled when market resolves)
                actual_outcome TEXT,
                resolution_date TEXT,
                was_correct BOOLEAN,
                profit_loss_usdc REAL,

                -- Features for pattern learning (JSON)
                features TEXT,

                -- Metadata
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Index for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_id
            ON predictions(market_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_type
            ON predictions(market_type)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy
            ON predictions(strategy)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON predictions(timestamp)
        """)

        # Performance metrics cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                context TEXT,
                calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(metric_name, context)
            )
        """)

        # Calibration tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calibration_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                confidence_bucket REAL NOT NULL,
                total_predictions INTEGER DEFAULT 0,
                correct_predictions INTEGER DEFAULT 0,
                accuracy REAL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(confidence_bucket)
            )
        """)

        self.conn.commit()

    def store_prediction(
        self,
        market_id: str,
        question: str,
        predicted_outcome: str,
        predicted_probability: float,
        confidence: float,
        reasoning: str,
        strategy: str,
        market_type: Optional[str] = None,
        market_prices: Optional[Dict[str, float]] = None,
        time_to_close_hours: Optional[float] = None,
        social_data: Optional[Dict] = None,
        features: Optional[Dict] = None,
    ) -> int:
        """
        Store a new prediction in the database

        Returns:
            prediction_id for later updates
        """
        cursor = self.conn.cursor()

        timestamp = datetime.utcnow().isoformat()

        # Extract market prices
        market_price_yes = market_prices.get("Yes", None) if market_prices else None
        market_price_no = market_prices.get("No", None) if market_prices else None

        # Extract social data
        social_sentiment = social_data.get("sentiment", None) if social_data else None
        social_volume = social_data.get("volume", None) if social_data else None

        # Store features as JSON
        features_json = json.dumps(features) if features else None

        cursor.execute("""
            INSERT INTO predictions (
                timestamp, market_id, question, market_type,
                predicted_outcome, predicted_probability, confidence, reasoning,
                market_price_yes, market_price_no, time_to_close_hours,
                social_sentiment, social_volume,
                strategy, features
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, market_id, question, market_type,
            predicted_outcome, predicted_probability, confidence, reasoning,
            market_price_yes, market_price_no, time_to_close_hours,
            social_sentiment, social_volume,
            strategy, features_json
        ))

        self.conn.commit()
        return cursor.lastrowid

    def record_trade_execution(
        self,
        prediction_id: int,
        trade_size_usdc: float,
        trade_price: float,
        execution_result: str
    ):
        """Record that a trade was executed for this prediction"""
        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE predictions
            SET trade_executed = 1,
                trade_size_usdc = ?,
                trade_price = ?,
                execution_result = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (trade_size_usdc, trade_price, execution_result, prediction_id))

        self.conn.commit()

    def update_prediction_execution(
        self,
        prediction_id: int,
        trade_executed: bool,
        execution_result: str
    ):
        """Update execution status for a prediction (success or failure)"""
        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE predictions
            SET trade_executed = ?,
                execution_result = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (1 if trade_executed else 0, execution_result, prediction_id))

        self.conn.commit()

    def record_outcome(
        self,
        market_id: str,
        actual_outcome: str,
        resolution_date: Optional[str] = None
    ):
        """
        Record the actual outcome when a market resolves
        Updates all predictions for this market
        """
        cursor = self.conn.cursor()

        if resolution_date is None:
            resolution_date = datetime.utcnow().isoformat()

        # Update all predictions for this market
        cursor.execute("""
            UPDATE predictions
            SET actual_outcome = ?,
                resolution_date = ?,
                was_correct = (predicted_outcome = ?),
                updated_at = CURRENT_TIMESTAMP
            WHERE market_id = ? AND actual_outcome IS NULL
        """, (actual_outcome, resolution_date, actual_outcome, market_id))

        # Calculate P&L for executed trades
        cursor.execute("""
            UPDATE predictions
            SET profit_loss_usdc = CASE
                WHEN was_correct = 1 THEN trade_size_usdc * (1.0 - trade_price) / trade_price
                ELSE -trade_size_usdc
            END
            WHERE market_id = ? AND trade_executed = 1
        """, (market_id,))

        self.conn.commit()

        # Update calibration data
        self._update_calibration_data()

    def _update_calibration_data(self):
        """Update calibration buckets with latest data"""
        cursor = self.conn.cursor()

        # Define confidence buckets (0-10%, 10-20%, ..., 90-100%)
        buckets = [(i/10, (i+1)/10) for i in range(10)]

        for lower, upper in buckets:
            bucket_center = (lower + upper) / 2

            # Get predictions in this bucket that have resolved
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct
                FROM predictions
                WHERE confidence >= ? AND confidence < ?
                AND actual_outcome IS NOT NULL
            """, (lower, upper))

            row = cursor.fetchone()
            total = row['total']
            correct = row['correct'] if row['correct'] else 0
            accuracy = correct / total if total > 0 else None

            # Insert or update
            cursor.execute("""
                INSERT OR REPLACE INTO calibration_data
                (confidence_bucket, total_predictions, correct_predictions, accuracy, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (bucket_center, total, correct, accuracy))

        self.conn.commit()

    def get_calibration_curve(self) -> List[Tuple[float, float, int]]:
        """
        Get calibration curve data

        Returns:
            List of (predicted_confidence, actual_accuracy, sample_size)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT confidence_bucket, accuracy, total_predictions
            FROM calibration_data
            WHERE total_predictions > 0
            ORDER BY confidence_bucket
        """)

        return [(row['confidence_bucket'], row['accuracy'], row['total_predictions'])
                for row in cursor.fetchall()]

    def calculate_brier_score(
        self,
        market_type: Optional[str] = None,
        strategy: Optional[str] = None,
        time_range_days: Optional[int] = None
    ) -> Optional[float]:
        """
        Calculate Brier score for resolved predictions

        Brier score = mean((predicted_prob - actual_outcome)^2)
        Lower is better (0 = perfect, 1 = worst possible)
        """
        cursor = self.conn.cursor()

        query = """
            SELECT predicted_probability, was_correct
            FROM predictions
            WHERE actual_outcome IS NOT NULL
        """
        params = []

        if market_type:
            query += " AND market_type = ?"
            params.append(market_type)

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        if time_range_days:
            cutoff = (datetime.utcnow() - timedelta(days=time_range_days)).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        if not rows:
            return None

        brier_scores = []
        for row in rows:
            predicted_prob = row['predicted_probability']
            actual = 1.0 if row['was_correct'] else 0.0
            brier_scores.append((predicted_prob - actual) ** 2)

        return sum(brier_scores) / len(brier_scores)

    def get_performance_summary(
        self,
        market_type: Optional[str] = None,
        strategy: Optional[str] = None,
        days: int = 30
    ) -> Dict:
        """Get comprehensive performance summary"""
        cursor = self.conn.cursor()

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        query = """
            SELECT
                COUNT(*) as total_predictions,
                SUM(CASE WHEN trade_executed = 1 THEN 1 ELSE 0 END) as trades_executed,
                SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct_predictions,
                SUM(CASE WHEN was_correct = 0 THEN 1 ELSE 0 END) as incorrect_predictions,
                SUM(profit_loss_usdc) as total_pnl,
                AVG(confidence) as avg_confidence,
                COUNT(CASE WHEN actual_outcome IS NOT NULL THEN 1 END) as resolved_markets
            FROM predictions
            WHERE timestamp >= ?
        """
        params = [cutoff]

        if market_type:
            query += " AND market_type = ?"
            params.append(market_type)

        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        cursor.execute(query, params)
        row = cursor.fetchone()

        total = row['total_predictions']
        resolved = row['resolved_markets']
        correct = row['correct_predictions'] if row['correct_predictions'] else 0

        return {
            "total_predictions": total,
            "trades_executed": row['trades_executed'],
            "resolved_markets": resolved,
            "pending_markets": total - resolved,
            "win_rate": correct / resolved if resolved > 0 else None,
            "total_pnl_usdc": row['total_pnl'],
            "avg_confidence": row['avg_confidence'],
            "brier_score": self.calculate_brier_score(market_type, strategy, days)
        }

    def find_similar_markets(
        self,
        question: str,
        market_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Find similar past markets (basic text matching for now)
        TODO: Integrate with ChromaDB for semantic similarity
        """
        cursor = self.conn.cursor()

        # Simple keyword matching for now
        keywords = question.lower().split()[:5]  # First 5 words

        query = """
            SELECT *
            FROM predictions
            WHERE actual_outcome IS NOT NULL
        """
        params = []

        if market_type:
            query += " AND market_type = ?"
            params.append(market_type)

        # Add basic text matching
        for keyword in keywords:
            query += f" AND LOWER(question) LIKE ?"
            params.append(f"%{keyword}%")

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_edge_by_market_type(self) -> Dict[str, Dict]:
        """Calculate expected edge by market type"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                market_type,
                COUNT(*) as total_trades,
                SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as wins,
                SUM(profit_loss_usdc) as total_pnl,
                AVG(profit_loss_usdc) as avg_pnl_per_trade
            FROM predictions
            WHERE trade_executed = 1 AND actual_outcome IS NOT NULL
            GROUP BY market_type
        """)

        results = {}
        for row in cursor.fetchall():
            market_type = row['market_type'] or 'unknown'
            total = row['total_trades']
            wins = row['wins'] if row['wins'] else 0

            results[market_type] = {
                "total_trades": total,
                "win_rate": wins / total if total > 0 else 0,
                "total_pnl": row['total_pnl'],
                "avg_pnl_per_trade": row['avg_pnl_per_trade'],
                "has_edge": row['avg_pnl_per_trade'] > 0 if row['avg_pnl_per_trade'] else False
            }

        return results

    def record_position_open(
        self,
        market_id: str,
        token_id: str,
        entry_price: float,
        size: float
    ):
        """
        Record when a position is opened

        Updates the most recent prediction for this market
        """
        from datetime import datetime
        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE predictions
            SET position_open = 1,
                token_id = ?,
                entry_timestamp = ?,
                trade_size_usdc = ?
            WHERE market_id = ?
            AND trade_executed = 1
            AND position_open = 0
            ORDER BY timestamp DESC
            LIMIT 1
        """, (token_id, datetime.utcnow().isoformat(), size, market_id))

        self.conn.commit()

    def get_open_positions(self) -> List[Dict]:
        """
        Get all currently open positions

        Returns:
            List of position dicts with market_id, token_id, entry_price, size, etc.
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                market_id,
                token_id,
                question,
                predicted_outcome,
                trade_price as entry_price,
                trade_size_usdc as size,
                predicted_probability,
                confidence,
                entry_timestamp,
                market_type,
                time_to_close_hours
            FROM predictions
            WHERE position_open = 1
            AND trade_executed = 1
            ORDER BY entry_timestamp DESC
        """)

        return [dict(row) for row in cursor.fetchall()]

    def close_position(
        self,
        market_id: str,
        exit_price: float,
        exit_reason: str
    ) -> Optional[float]:
        """
        Close a position and calculate realized P&L

        Returns:
            Realized P&L in USDC
        """
        from datetime import datetime
        cursor = self.conn.cursor()

        # Get position details
        cursor.execute("""
            SELECT
                trade_price as entry_price,
                trade_size_usdc as size,
                predicted_outcome
            FROM predictions
            WHERE market_id = ?
            AND position_open = 1
            LIMIT 1
        """, (market_id,))

        row = cursor.fetchone()
        if not row:
            return None

        entry_price = row['entry_price']
        size = row['size']

        # Calculate P&L
        # If we bought YES at entry_price and sell at exit_price:
        # P&L = size * (exit_price - entry_price) / entry_price
        pnl = size * (exit_price - entry_price) / entry_price

        # Update position
        cursor.execute("""
            UPDATE predictions
            SET position_open = 0,
                exit_timestamp = ?,
                exit_price = ?,
                exit_reason = ?,
                profit_loss_usdc = ?
            WHERE market_id = ?
            AND position_open = 1
        """, (datetime.utcnow().isoformat(), exit_price, exit_reason, pnl, market_id))

        self.conn.commit()

        return pnl

    def close(self):
        """Close database connection"""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
