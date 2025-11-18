"""
Stock Circuit Predictor
ML models to predict:
1. Upper Circuit probability for tomorrow
2. Days from UC to LC
"""
import pandas as pd
import numpy as np
import os
import sys
import joblib
from datetime import datetime, date, timedelta
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MODELS_DIR, UC_TOLERANCE, LC_TOLERANCE
from database.db_manager import DatabaseManager
from analysis.indicators import IndicatorCalculator
from analysis.circuit_detector import CircuitDetector


class CircuitPredictor:
    def __init__(self):
        self.db = DatabaseManager()
        self.indicator_calc = IndicatorCalculator()
        self.circuit_detector = CircuitDetector()

        # Models
        self.uc_model = None
        self.uc_scaler = None
        self.duration_model = None
        self.duration_scaler = None

        # Model paths
        self.uc_model_path = os.path.join(MODELS_DIR, 'uc_predictor.joblib')
        self.uc_scaler_path = os.path.join(MODELS_DIR, 'uc_scaler.joblib')
        self.duration_model_path = os.path.join(MODELS_DIR, 'duration_predictor.joblib')
        self.duration_scaler_path = os.path.join(MODELS_DIR, 'duration_scaler.joblib')

        # Load existing models if available
        self._load_models()

    def _load_models(self):
        """Load existing models from disk"""
        try:
            if os.path.exists(self.uc_model_path):
                self.uc_model = joblib.load(self.uc_model_path)
                self.uc_scaler = joblib.load(self.uc_scaler_path)
        except Exception as e:
            print(f"Could not load UC model: {e}")

        try:
            if os.path.exists(self.duration_model_path):
                self.duration_model = joblib.load(self.duration_model_path)
                self.duration_scaler = joblib.load(self.duration_scaler_path)
        except Exception as e:
            print(f"Could not load duration model: {e}")

    def _save_models(self):
        """Save models to disk"""
        if self.uc_model:
            joblib.dump(self.uc_model, self.uc_model_path)
            joblib.dump(self.uc_scaler, self.uc_scaler_path)

        if self.duration_model:
            joblib.dump(self.duration_model, self.duration_model_path)
            joblib.dump(self.duration_scaler, self.duration_scaler_path)

    def _prepare_features(self, row):
        """Prepare feature vector from a data row"""
        features = [
            row.get('price_change_1d', 0) or 0,
            row.get('price_change_5d', 0) or 0,
            row.get('rsi_14', 50) or 50,
            row.get('macd', 0) or 0,
            row.get('macd_signal', 0) or 0,
            row.get('macd_histogram', 0) or 0,
            row.get('volume_ratio_20', 1) or 1,
            row.get('atr_14', 0) or 0,
        ]

        # Price relative to MAs
        close = row.get('close', 0) or 1
        ma_5 = row.get('ma_5', close) or close
        ma_20 = row.get('ma_20', close) or close
        ma_50 = row.get('ma_50', close) or close

        features.extend([
            (close - ma_5) / ma_5 * 100 if ma_5 != 0 else 0,
            (close - ma_20) / ma_20 * 100 if ma_20 != 0 else 0,
            (close - ma_50) / ma_50 * 100 if ma_50 != 0 else 0,
        ])

        # Distance to support/resistance
        support = row.get('support_20', close) or close
        resistance = row.get('resistance_20', close) or close

        features.extend([
            (close - support) / support * 100 if support != 0 else 0,
            (resistance - close) / close * 100 if close != 0 else 0,
        ])

        return features

    def _get_training_data_uc(self):
        """Prepare training data for UC prediction"""
        stocks = self.db.get_all_stocks()
        X = []
        y = []

        print("Preparing UC training data...")

        for stock in tqdm(stocks, desc="Preparing data"):
            # Get OHLCV data
            ohlcv = self.db.get_ohlcv_data(stock['id'])
            if ohlcv.empty or len(ohlcv) < 60:
                continue

            # Get indicators
            indicators = self.db.get_indicators(stock['id'])
            if indicators.empty:
                continue

            # Merge data
            ohlcv['date'] = pd.to_datetime(ohlcv['date'])
            indicators['date'] = pd.to_datetime(indicators['date'])
            df = pd.merge(ohlcv, indicators, on='date', suffixes=('', '_ind'))

            # Detect circuits
            df = self.circuit_detector.detect_circuits_in_dataframe(df)

            # Create training samples
            for i in range(len(df) - 1):
                row = df.iloc[i]
                next_row = df.iloc[i + 1]

                # Skip if we don't have indicators
                if pd.isna(row.get('rsi_14')):
                    continue

                features = self._prepare_features(row)
                is_uc_tomorrow = 1 if next_row['is_uc'] else 0

                X.append(features)
                y.append(is_uc_tomorrow)

        return np.array(X), np.array(y)

    def _get_training_data_duration(self):
        """Prepare training data for UC to LC duration prediction"""
        # Get historical UC to LC durations
        uc_to_lc = self.db.get_uc_to_lc_history()

        if uc_to_lc.empty:
            return None, None

        X = []
        y = []

        print("Preparing duration training data...")

        for _, record in tqdm(uc_to_lc.iterrows(), desc="Preparing data", total=len(uc_to_lc)):
            stock_id = record['stock_id']
            uc_date = record['uc_date']

            # Get data around UC date
            ohlcv = self.db.get_ohlcv_data(stock_id)
            indicators = self.db.get_indicators(stock_id)

            if ohlcv.empty or indicators.empty:
                continue

            # Find the UC date row
            ohlcv['date'] = pd.to_datetime(ohlcv['date']).dt.strftime('%Y-%m-%d')
            indicators['date'] = pd.to_datetime(indicators['date']).dt.strftime('%Y-%m-%d')

            df = pd.merge(ohlcv, indicators, on='date', suffixes=('', '_ind'))

            uc_row = df[df['date'] == uc_date]
            if uc_row.empty:
                continue

            row = uc_row.iloc[0]
            features = self._prepare_features(row)

            X.append(features)
            y.append(record['days_to_lc'])

        if not X:
            return None, None

        return np.array(X), np.array(y)

    def train_uc_model(self):
        """Train the UC prediction model"""
        print("Training UC prediction model...")

        X, y = self._get_training_data_uc()

        if len(X) == 0:
            print("No training data available for UC model")
            return False

        print(f"Training with {len(X)} samples, {sum(y)} UC events")

        # Handle class imbalance
        class_weight = 'balanced'

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y if sum(y) > 10 else None
        )

        # Scale features
        self.uc_scaler = StandardScaler()
        X_train_scaled = self.uc_scaler.fit_transform(X_train)
        X_test_scaled = self.uc_scaler.transform(X_test)

        # Train model
        self.uc_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            class_weight=class_weight,
            random_state=42,
            n_jobs=-1
        )
        self.uc_model.fit(X_train_scaled, y_train)

        # Evaluate
        accuracy = self.uc_model.score(X_test_scaled, y_test)
        print(f"UC Model Accuracy: {accuracy:.2%}")

        # Save models
        self._save_models()

        return True

    def train_duration_model(self):
        """Train the UC to LC duration prediction model"""
        print("Training duration prediction model...")

        X, y = self._get_training_data_duration()

        if X is None or len(X) == 0:
            print("No training data available for duration model")
            return False

        print(f"Training with {len(X)} samples")

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        self.duration_scaler = StandardScaler()
        X_train_scaled = self.duration_scaler.fit_transform(X_train)
        X_test_scaled = self.duration_scaler.transform(X_test)

        # Train model
        self.duration_model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
        self.duration_model.fit(X_train_scaled, y_train)

        # Evaluate
        from sklearn.metrics import mean_absolute_error
        y_pred = self.duration_model.predict(X_test_scaled)
        mae = mean_absolute_error(y_test, y_pred)
        print(f"Duration Model MAE: {mae:.2f} days")

        # Save models
        self._save_models()

        return True

    def train_all_models(self):
        """Train all prediction models"""
        uc_success = self.train_uc_model()
        duration_success = self.train_duration_model()
        return uc_success, duration_success

    def predict_uc_probability(self, stock_id):
        """
        Predict probability of stock hitting UC tomorrow

        Returns: probability 0-100%
        """
        if self.uc_model is None:
            return None

        # Get latest data
        ohlcv = self.db.get_ohlcv_data(stock_id)
        indicators = self.db.get_indicators(stock_id)

        if ohlcv.empty or indicators.empty:
            return None

        # Get latest row with indicators
        ohlcv['date'] = pd.to_datetime(ohlcv['date'])
        indicators['date'] = pd.to_datetime(indicators['date'])
        df = pd.merge(ohlcv, indicators, on='date', suffixes=('', '_ind'))

        if df.empty:
            return None

        latest = df.iloc[-1]
        features = self._prepare_features(latest)

        # Scale and predict
        features_scaled = self.uc_scaler.transform([features])
        probability = self.uc_model.predict_proba(features_scaled)[0][1]

        return round(probability * 100, 1)

    def predict_uc_to_lc_days(self, stock_id):
        """
        Predict how many days until stock hits LC after UC

        Returns: estimated days
        """
        if self.duration_model is None:
            # Return average from historical data
            stats = self.circuit_detector.get_circuit_statistics(stock_id)
            return stats['avg_days_uc_to_lc'] if stats['avg_days_uc_to_lc'] > 0 else None

        # Get latest data
        ohlcv = self.db.get_ohlcv_data(stock_id)
        indicators = self.db.get_indicators(stock_id)

        if ohlcv.empty or indicators.empty:
            return None

        # Get latest row
        ohlcv['date'] = pd.to_datetime(ohlcv['date'])
        indicators['date'] = pd.to_datetime(indicators['date'])
        df = pd.merge(ohlcv, indicators, on='date', suffixes=('', '_ind'))

        if df.empty:
            return None

        latest = df.iloc[-1]
        features = self._prepare_features(latest)

        # Scale and predict
        features_scaled = self.duration_scaler.transform([features])
        days = self.duration_model.predict(features_scaled)[0]

        return max(1, round(days))

    def get_stock_prediction(self, symbol):
        """
        Get complete prediction for a stock

        Returns dict with:
        - uc_probability: 0-100%
        - predicted_uc_to_lc_days: int
        - current_status: UC/LC/Normal
        """
        stock = self.db.get_stock_by_symbol(symbol)
        if not stock:
            return None

        stock_id = stock['id']

        # Get current status
        status = self.circuit_detector.get_current_status(stock_id)
        if not status:
            return None

        current_status = 'Normal'
        if status['is_uc']:
            current_status = 'Upper Circuit'
        elif status['is_lc']:
            current_status = 'Lower Circuit'

        # Get predictions
        uc_prob = self.predict_uc_probability(stock_id)
        uc_to_lc = self.predict_uc_to_lc_days(stock_id)

        return {
            'symbol': symbol,
            'name': stock['name'],
            'exchange': stock['exchange'],
            'current_status': current_status,
            'date': status['date'],
            'close': status['close'],
            'high': status['high'],
            'low': status['low'],
            'uc_probability': uc_prob,
            'predicted_uc_to_lc_days': uc_to_lc,
            'is_uc': status['is_uc'],
            'is_lc': status['is_lc']
        }

    def screen_for_uc(self, min_probability=50):
        """
        Screen all stocks for potential UC tomorrow

        Returns list of stocks with UC probability >= min_probability
        """
        stocks = self.db.get_all_stocks()
        candidates = []

        print(f"Screening {len(stocks)} stocks for UC opportunities...")

        for stock in tqdm(stocks, desc="Screening"):
            prediction = self.get_stock_prediction(stock['symbol'])
            if prediction and prediction['uc_probability']:
                if prediction['uc_probability'] >= min_probability:
                    candidates.append(prediction)

        # Sort by probability
        candidates.sort(key=lambda x: x['uc_probability'], reverse=True)

        return candidates

    def save_predictions(self):
        """Save predictions for all stocks to database"""
        stocks = self.db.get_all_stocks()
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        count = 0
        for stock in tqdm(stocks, desc="Saving predictions"):
            uc_prob = self.predict_uc_probability(stock['id'])
            uc_to_lc = self.predict_uc_to_lc_days(stock['id'])

            if uc_prob is not None:
                self.db.save_prediction(
                    stock_id=stock['id'],
                    prediction_date=today,
                    target_date=tomorrow,
                    uc_probability=uc_prob,
                    predicted_uc_to_lc_days=uc_to_lc or 0
                )
                count += 1

        return count


# Create __init__.py for analysis module
if __name__ == '__main__':
    predictor = CircuitPredictor()

    # Train models
    predictor.train_all_models()

    # Example prediction
    print("\nExample prediction:")
    prediction = predictor.get_stock_prediction('RELIANCE')
    if prediction:
        print(f"Stock: {prediction['symbol']}")
        print(f"Status: {prediction['current_status']}")
        print(f"UC Probability Tomorrow: {prediction['uc_probability']}%")
        print(f"Predicted UC to LC Days: {prediction['predicted_uc_to_lc_days']}")
