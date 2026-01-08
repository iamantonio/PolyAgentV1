#!/usr/bin/env python3
"""
Dashboard API - Serves real-time trading data
Reads from SQLite database and provides JSON endpoints
"""

from flask import Flask, jsonify, send_file
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

DB_PATH = "/tmp/learning_trader.db"


def get_db():
    """Get database connection"""
    if not os.path.exists(DB_PATH):
        return None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/api/status')
def get_status():
    """Get current trading status"""
    conn = get_db()
    if not conn:
        return jsonify({
            'active': False,
            'message': 'Database not found - bot not started yet'
        })

    cursor = conn.cursor()

    # Get total stats
    cursor.execute("""
        SELECT
            COUNT(*) as total_trades,
            SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as wins,
            SUM(profit_loss_usdc) as total_pnl,
            AVG(predicted_probability) as avg_confidence
        FROM predictions
        WHERE actual_outcome IS NOT NULL
    """)

    stats = cursor.fetchone()

    # Check if trading recently (last 10 minutes)
    cursor.execute("""
        SELECT timestamp
        FROM predictions
        ORDER BY timestamp DESC
        LIMIT 1
    """)

    last_trade = cursor.fetchone()
    active = False

    if last_trade:
        last_time = datetime.fromisoformat(last_trade['timestamp'])
        active = (datetime.now() - last_time).total_seconds() < 600

    conn.close()

    total = stats['total_trades'] or 0
    wins = stats['wins'] or 0

    return jsonify({
        'active': active,
        'total_trades': total,
        'wins': wins,
        'losses': total - wins,
        'win_rate': (wins / total * 100) if total > 0 else 0,
        'total_pnl': stats['total_pnl'] or 0,
        'avg_confidence': (stats['avg_confidence'] or 0) * 100,
        'last_trade': last_trade['timestamp'] if last_trade else None
    })


@app.route('/api/recent_trades')
def get_recent_trades():
    """Get recent trades"""
    conn = get_db()
    if not conn:
        return jsonify([])

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            question,
            predicted_outcome,
            predicted_probability,
            actual_outcome,
            was_correct,
            profit_loss_usdc,
            timestamp,
            market_type
        FROM predictions
        ORDER BY timestamp DESC
        LIMIT 20
    """)

    trades = []
    for row in cursor.fetchall():
        trades.append({
            'question': row['question'],
            'prediction': row['predicted_outcome'],
            'confidence': (row['predicted_probability'] or 0) * 100,
            'outcome': row['actual_outcome'],
            'correct': row['was_correct'],
            'pnl': row['profit_loss_usdc'] or 0,
            'timestamp': row['timestamp'],
            'market_type': row['market_type'] or 'unknown'
        })

    conn.close()
    return jsonify(trades)


@app.route('/api/edge_detection')
def get_edge_detection():
    """Get edge detection stats by market type"""
    conn = get_db()
    if not conn:
        return jsonify({})

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            market_type,
            COUNT(*) as total_trades,
            SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as wins,
            AVG(profit_loss_usdc) as avg_pnl
        FROM predictions
        WHERE actual_outcome IS NOT NULL
        AND market_type IS NOT NULL
        GROUP BY market_type
    """)

    edge_data = {}
    for row in cursor.fetchall():
        total = row['total_trades']
        wins = row['wins'] or 0

        edge_data[row['market_type']] = {
            'total_trades': total,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'avg_pnl': row['avg_pnl'] or 0,
            'has_edge': (wins / total) > 0.55 if total >= 20 else None
        }

    conn.close()
    return jsonify(edge_data)


@app.route('/api/performance_timeline')
def get_performance_timeline():
    """Get performance over time for charting"""
    conn = get_db()
    if not conn:
        return jsonify([])

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            timestamp,
            profit_loss_usdc,
            was_correct,
            predicted_probability
        FROM predictions
        WHERE actual_outcome IS NOT NULL
        ORDER BY timestamp ASC
    """)

    timeline = []
    cumulative_pnl = 0

    for row in cursor.fetchall():
        cumulative_pnl += (row['profit_loss_usdc'] or 0)
        timeline.append({
            'timestamp': row['timestamp'],
            'pnl': row['profit_loss_usdc'] or 0,
            'cumulative_pnl': cumulative_pnl,
            'correct': row['was_correct'],
            'confidence': (row['predicted_probability'] or 0) * 100
        })

    conn.close()
    return jsonify(timeline)


@app.route('/api/safety_status')
def get_safety_status():
    """Get safety limits status"""
    conn = get_db()
    if not conn:
        return jsonify({
            'trades_this_hour': 0,
            'daily_pnl': 0,
            'limits': {
                'max_trades_hour': 3,
                'max_daily_loss': 10,
                'emergency_stop': 20,
                'max_position': 2
            }
        })

    cursor = conn.cursor()

    # Trades in last hour
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM predictions
        WHERE timestamp > ?
    """, (one_hour_ago,))

    trades_hour = cursor.fetchone()['count']

    # Today's P&L
    today = datetime.now().date().isoformat()
    cursor.execute("""
        SELECT SUM(profit_loss_usdc) as daily_pnl
        FROM predictions
        WHERE DATE(timestamp) = ?
        AND actual_outcome IS NOT NULL
    """, (today,))

    daily_pnl = cursor.fetchone()['daily_pnl'] or 0

    conn.close()

    return jsonify({
        'trades_this_hour': trades_hour,
        'daily_pnl': daily_pnl,
        'limits': {
            'max_trades_hour': 3,
            'max_daily_loss': 10.0,
            'emergency_stop': 20.0,
            'max_position': 2.0
        },
        'warnings': {
            'hour_limit': trades_hour >= 3,
            'daily_loss': abs(daily_pnl) >= 10,
            'emergency': abs(daily_pnl) >= 20
        }
    })


@app.route('/')
def serve_dashboard():
    """Serve the dashboard HTML"""
    return send_file('dashboard.html')


if __name__ == '__main__':
    print("=" * 80)
    print("TRADING DASHBOARD API")
    print("=" * 80)
    print()
    print("Starting server on http://localhost:5555")
    print("Open browser to view live dashboard")
    print()
    print("Endpoints:")
    print("  GET /              - Dashboard HTML")
    print("  GET /api/status    - Current trading status")
    print("  GET /api/recent_trades - Recent trades")
    print("  GET /api/edge_detection - Edge by market type")
    print("  GET /api/performance_timeline - P&L over time")
    print("  GET /api/safety_status - Safety limits")
    print()
    print("=" * 80)

    app.run(host='0.0.0.0', port=5555, debug=False)
