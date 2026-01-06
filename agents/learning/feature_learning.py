"""
Feature-Based Learning System

Learns which features actually predict market outcomes using machine learning.
This is REAL learning that improves with more data.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import joblib
import json
from pathlib import Path


class FeatureLearner:
    """Learn patterns from historical data using regression models"""

    def __init__(self, trade_history_db, model_dir: str = "/tmp/feature_models"):
        self.db = trade_history_db
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)

        self.models = {}
        self.scalers = {}
        self.feature_importance = {}

        self._load_models()

    def extract_features(self, market_data: Dict) -> np.ndarray:
        """Extract numerical features from market data"""
        features = []

        # Social sentiment (0-1)
        features.append(market_data.get('social_sentiment', 0.5))

        # Log social volume
        volume = market_data.get('social_volume', 1000)
        features.append(np.log(volume + 1))

        # Log time to close
        time_to_close = market_data.get('time_to_close_hours', 24)
        features.append(np.log(time_to_close + 1))

        # Price spread
        prices = market_data.get('prices', {})
        yes_price = prices.get('Yes', 0.5)
        no_price = prices.get('No', 0.5)
        features.append(abs(yes_price - no_price))

        # YES price
        features.append(yes_price)

        return np.array(features)

    def train_model(self, market_type: Optional[str] = None, min_samples: int = 20) -> bool:
        """Train model from historical data"""
        cursor = self.db.conn.cursor()

        query = "SELECT features, predicted_outcome, actual_outcome FROM predictions WHERE actual_outcome IS NOT NULL AND features IS NOT NULL"
        params = []

        if market_type:
            query += " AND market_type = ?"
            params.append(market_type)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        if len(rows) < min_samples:
            return False

        X, y = [], []
        for row in rows:
            try:
                features_dict = json.loads(row['features'])
                X.append(self.extract_features(features_dict))
                y.append(1 if row['predicted_outcome'] == row['actual_outcome'] else 0)
            except:
                continue

        if len(X) < min_samples:
            return False

        X = np.array(X)
        y = np.array(y)

        # Train
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = LogisticRegression(random_state=42, max_iter=1000)
        model.fit(X_scaled, y)

        # Store
        model_key = market_type or "all"
        self.models[model_key] = model
        self.scalers[model_key] = scaler

        feature_names = ["sentiment", "log_volume", "log_time", "spread", "yes_price"]
        self.feature_importance[model_key] = dict(zip(feature_names, model.coef_[0]))

        self._save_models()
        return True

    def predict_correctness_probability(self, market_data: Dict, market_type: Optional[str] = None) -> Optional[float]:
        """Predict probability our prediction will be correct"""
        model_key = market_type or "all"

        if model_key not in self.models:
            if not self.train_model(market_type):
                return None

        model = self.models[model_key]
        scaler = self.scalers[model_key]

        features = self.extract_features(market_data).reshape(1, -1)
        features_scaled = scaler.transform(features)

        return model.predict_proba(features_scaled)[0][1]

    def _save_models(self):
        """Save models using joblib (safer than pickle)"""
        for key, model in self.models.items():
            model_file = self.model_dir / f"model_{key}.joblib"
            scaler_file = self.model_dir / f"scaler_{key}.joblib"

            joblib.dump(model, model_file)
            joblib.dump(self.scalers[key], scaler_file)

        # Save feature importance as JSON
        importance_file = self.model_dir / "feature_importance.json"
        with open(importance_file, 'w') as f:
            json.dump(self.feature_importance, f, indent=2)

    def _load_models(self):
        """Load models from disk"""
        if not self.model_dir.exists():
            return

        # Load feature importance
        importance_file = self.model_dir / "feature_importance.json"
        if importance_file.exists():
            with open(importance_file, 'r') as f:
                self.feature_importance = json.load(f)

        # Load models
        for model_file in self.model_dir.glob("model_*.joblib"):
            key = model_file.stem.replace("model_", "")
            scaler_file = self.model_dir / f"scaler_{key}.joblib"

            try:
                self.models[key] = joblib.load(model_file)
                self.scalers[key] = joblib.load(scaler_file)
            except:
                pass

    def get_learning_stats(self) -> dict:
        """Get statistics about feature learning"""
        cursor = self.db.conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as total
            FROM predictions
            WHERE actual_outcome IS NOT NULL AND features IS NOT NULL
        """)

        row = cursor.fetchone()
        total = row['total'] if row else 0

        return {
            'trained': len(self.models) > 0,
            'total_samples': total,
            'models_trained': list(self.models.keys()),
            'feature_importance': self.feature_importance
        }
