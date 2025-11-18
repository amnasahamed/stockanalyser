"""
Technical Indicator Calculator
Calculates all required technical indicators for stocks
"""
import pandas as pd
import numpy as np
import os
import sys
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
                    ATR_PERIOD, MA_SHORT, MA_MEDIUM, MA_LONG,
                    VOLUME_MA_PERIOD, SUPPORT_RESISTANCE_PERIOD)
from database.db_manager import DatabaseManager


class IndicatorCalculator:
    def __init__(self):
        self.db = DatabaseManager()

    def calculate_rsi(self, prices, period=RSI_PERIOD):
        """Calculate RSI (Relative Strength Index)"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_macd(self, prices, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL):
        """Calculate MACD (Moving Average Convergence Divergence)"""
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def calculate_atr(self, high, low, close, period=ATR_PERIOD):
        """Calculate ATR (Average True Range)"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    def calculate_all_indicators(self, df):
        """Calculate all technical indicators for a DataFrame"""
        if df.empty or len(df) < MA_LONG:
            return df

        # Create a copy to avoid modifying original
        result = df.copy()

        # Ensure we have the required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in result.columns for col in required):
            return result

        # Price changes
        result['price_change_1d'] = result['close'].pct_change() * 100
        result['price_change_5d'] = result['close'].pct_change(periods=5) * 100

        # Moving averages
        result['ma_5'] = result['close'].rolling(window=MA_SHORT).mean()
        result['ma_20'] = result['close'].rolling(window=MA_MEDIUM).mean()
        result['ma_50'] = result['close'].rolling(window=MA_LONG).mean()

        # RSI
        result['rsi_14'] = self.calculate_rsi(result['close'], RSI_PERIOD)

        # MACD
        macd, signal, hist = self.calculate_macd(result['close'])
        result['macd'] = macd
        result['macd_signal'] = signal
        result['macd_histogram'] = hist

        # Volume ratio (today's volume / 20-day average)
        volume_ma = result['volume'].rolling(window=VOLUME_MA_PERIOD).mean()
        result['volume_ratio_20'] = result['volume'] / volume_ma

        # ATR
        result['atr_14'] = self.calculate_atr(result['high'], result['low'], result['close'])

        # Support and Resistance (20-day)
        result['support_20'] = result['low'].rolling(window=SUPPORT_RESISTANCE_PERIOD).min()
        result['resistance_20'] = result['high'].rolling(window=SUPPORT_RESISTANCE_PERIOD).max()

        return result

    def calculate_and_save_for_stock(self, stock_id):
        """Calculate and save indicators for a stock"""
        # Get OHLCV data
        df = self.db.get_ohlcv_data(stock_id)

        if df.empty:
            return {'status': 'no_data', 'rows': 0}

        try:
            # Calculate indicators
            df = self.calculate_all_indicators(df)

            # Prepare for saving
            indicator_cols = [
                'date', 'price_change_1d', 'price_change_5d', 'ma_5', 'ma_20', 'ma_50',
                'rsi_14', 'macd', 'macd_signal', 'macd_histogram', 'volume_ratio_20',
                'atr_14', 'support_20', 'resistance_20'
            ]

            indicators_df = df[indicator_cols].dropna()

            if indicators_df.empty:
                return {'status': 'insufficient_data', 'rows': 0}

            # Save to database
            self.db.add_indicators(stock_id, indicators_df)

            return {'status': 'success', 'rows': len(indicators_df)}

        except Exception as e:
            return {'status': 'error', 'error': str(e), 'rows': 0}

    def calculate_for_all_stocks(self, exchange=None):
        """Calculate indicators for all stocks"""
        stocks = self.db.get_all_stocks(exchange=exchange)
        total = len(stocks)

        results = {
            'total': total,
            'success': 0,
            'errors': 0,
            'no_data': 0
        }

        print(f"Calculating indicators for {total} stocks...")

        for stock in tqdm(stocks, desc="Calculating"):
            result = self.calculate_and_save_for_stock(stock['id'])

            if result['status'] == 'success':
                results['success'] += 1
            elif result['status'] == 'error':
                results['errors'] += 1
            else:
                results['no_data'] += 1

        return results

    def get_latest_indicators(self, stock_id):
        """Get the most recent indicators for a stock"""
        df = self.db.get_indicators(stock_id)
        if df.empty:
            return None

        return df.iloc[-1].to_dict()


if __name__ == '__main__':
    calculator = IndicatorCalculator()
    results = calculator.calculate_for_all_stocks()
    print(f"\nCalculation Results:")
    print(f"  Total: {results['total']}")
    print(f"  Success: {results['success']}")
    print(f"  Errors: {results['errors']}")
    print(f"  No data: {results['no_data']}")
