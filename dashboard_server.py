#!/usr/bin/env python3
"""
Trading Dashboard Backend Server
Serves real-time data from learning_trader.db via REST API
"""

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)

DB_PATH = "/tmp/learning_trader.db"

def get_db_connection():
    """Create database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Serve dashboard HTML"""
    return send_from_directory('.', 'dashboard.html')

@app.route('/api/status')
def get_status():
    """Get current bot status and stats"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get total stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN outcome_profit_usdc > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome_profit_usdc < 0 THEN 1 ELSE 0 END) as losses,
                SUM(outcome_profit_usdc) as total_pnl,
                AVG(confidence) as avg_confidence,
                COUNT(CASE WHEN outcome IS NULL THEN 1 END) as open_positions
            FROM predictions
            WHERE outcome IS NOT NULL OR outcome IS NULL
        """)

        stats = cursor.fetchone()

        # Calculate win rate
        total = stats['total_trades'] - (stats['open_positions'] or 0)
        win_rate = (stats['wins'] / total * 100) if total > 0 else 0

        # Get current exposure
        cursor.execute("""
            SELECT SUM(trade_size_usdc) as total_exposure
            FROM predictions
            WHERE outcome IS NULL
        """)
        exposure = cursor.fetchone()

        # Get recent activity timestamp
        cursor.execute("""
            SELECT MAX(timestamp) as last_activity
            FROM predictions
        """)
        activity = cursor.fetchone()

        conn.close()

        return jsonify({
            'status': 'active',
            'total_trades': stats['total_trades'],
            'wins': stats['wins'] or 0,
            'losses': stats['losses'] or 0,
            'open_positions': stats['open_positions'] or 0,
            'win_rate': round(win_rate, 1),
            'total_pnl': round(stats['total_pnl'] or 0, 2),
            'avg_confidence': round((stats['avg_confidence'] or 0) * 100, 1),
            'current_exposure': round(exposure['total_exposure'] or 0, 2),
            'last_activity': activity['last_activity']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent_trades')
def get_recent_trades():
    """Get last 20 trades"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                question,
                prediction,
                confidence,
                outcome,
                outcome_profit_usdc as pnl,
                trade_size_usdc as size,
                timestamp
            FROM predictions
            ORDER BY timestamp DESC
            LIMIT 20
        """)

        trades = []
        for row in cursor.fetchall():
            trades.append({
                'question': row['question'][:60] + '...' if len(row['question']) > 60 else row['question'],
                'prediction': row['prediction'],
                'confidence': round(row['confidence'] * 100, 1) if row['confidence'] else 0,
                'outcome': row['outcome'] or 'OPEN',
                'pnl': round(row['pnl'], 2) if row['pnl'] else 0,
                'size': round(row['size'], 2) if row['size'] else 0,
                'timestamp': row['timestamp']
            })

        conn.close()
        return jsonify(trades)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pnl_history')
def get_pnl_history():
    """Get P&L over time for chart"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                timestamp,
                outcome_profit_usdc as pnl
            FROM predictions
            WHERE outcome IS NOT NULL
            ORDER BY timestamp ASC
        """)

        cumulative_pnl = 0
        data = []

        for row in cursor.fetchall():
            cumulative_pnl += (row['pnl'] or 0)
            data.append({
                'timestamp': row['timestamp'],
                'cumulative_pnl': round(cumulative_pnl, 2)
            })

        conn.close()
        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/win_rate_history')
def get_win_rate_history():
    """Get win rate over time (rolling 10-trade window)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                timestamp,
                CASE WHEN outcome_profit_usdc > 0 THEN 1 ELSE 0 END as is_win
            FROM predictions
            WHERE outcome IS NOT NULL
            ORDER BY timestamp ASC
        """)

        rows = cursor.fetchall()
        data = []

        for i in range(len(rows)):
            if i >= 9:  # Need at least 10 trades
                window = rows[i-9:i+1]
                wins = sum(r['is_win'] for r in window)
                win_rate = (wins / 10) * 100
                data.append({
                    'timestamp': rows[i]['timestamp'],
                    'win_rate': round(win_rate, 1)
                })

        conn.close()
        return jsonify(data)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/safety_limits')
def get_safety_limits():
    """Get current safety limit status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get exposure
        cursor.execute("""
            SELECT SUM(trade_size_usdc) as exposure
            FROM predictions
            WHERE outcome IS NULL
        """)
        exposure_row = cursor.fetchone()
        current_exposure = exposure_row['exposure'] or 0

        # Get trades in last hour
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM predictions
            WHERE timestamp > datetime('now', '-1 hour')
        """)
        hourly = cursor.fetchone()

        # Get P&L today
        cursor.execute("""
            SELECT SUM(outcome_profit_usdc) as daily_pnl
            FROM predictions
            WHERE DATE(timestamp) = DATE('now')
            AND outcome IS NOT NULL
        """)
        daily = cursor.fetchone()

        conn.close()

        # Hardcoded limits (match learning_autonomous_trader.py)
        BANKROLL = 100.0
        MAX_EXPOSURE_PCT = 0.50

        return jsonify({
            'exposure': {
                'current': round(current_exposure, 2),
                'limit': BANKROLL * MAX_EXPOSURE_PCT,
                'percentage': round((current_exposure / BANKROLL) * 100, 1)
            },
            'trades_per_hour': {
                'current': hourly['count'],
                'limit': 20  # Example limit
            },
            'daily_loss_limit': {
                'current_pnl': round(daily['daily_pnl'] or 0, 2),
                'limit': -10.0  # Example limit
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print(f"⚠️  Database not found: {DB_PATH}")
        print("Run the bot first to create the database.")
        exit(1)

    print("=" * 80)
    print("TRADING DASHBOARD SERVER")
    print("=" * 80)
    print(f"Database: {DB_PATH}")
    print("Server: http://localhost:5555")
    print("Dashboard: http://localhost:5555")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 80)

    app.run(host='0.0.0.0', port=5555, debug=False)
