"""
Circuit Detector
Detects Upper Circuit (UC) and Lower Circuit (LC) events based on the defined rules
"""
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, date
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import UC_TOLERANCE, LC_TOLERANCE
from database.db_manager import DatabaseManager


class CircuitDetector:
    def __init__(self):
        self.db = DatabaseManager()

    def is_upper_circuit(self, close, high):
        """
        Check if a day is Upper Circuit
        Rule: Close price equals High price within 1% tolerance

        UC if: abs(close - high) / high <= tolerance
        """
        if high == 0 or pd.isna(close) or pd.isna(high):
            return False, 0

        diff_pct = abs(close - high) / high
        is_uc = diff_pct <= UC_TOLERANCE

        return is_uc, diff_pct * 100

    def is_lower_circuit(self, close, low):
        """
        Check if a day is Lower Circuit
        Rule: Close price equals Low price within 1% tolerance

        LC if: abs(close - low) / low <= tolerance
        """
        if low == 0 or pd.isna(close) or pd.isna(low):
            return False, 0

        diff_pct = abs(close - low) / low
        is_lc = diff_pct <= LC_TOLERANCE

        return is_lc, diff_pct * 100

    def detect_circuits_in_dataframe(self, df):
        """
        Detect UC and LC events in an OHLCV DataFrame

        Returns DataFrame with is_uc and is_lc columns added
        """
        result = df.copy()

        result['is_uc'] = False
        result['is_lc'] = False
        result['uc_tolerance_pct'] = 0.0
        result['lc_tolerance_pct'] = 0.0

        for idx, row in result.iterrows():
            # Check Upper Circuit
            is_uc, uc_pct = self.is_upper_circuit(row['close'], row['high'])
            result.at[idx, 'is_uc'] = is_uc
            result.at[idx, 'uc_tolerance_pct'] = uc_pct

            # Check Lower Circuit
            is_lc, lc_pct = self.is_lower_circuit(row['close'], row['low'])
            result.at[idx, 'is_lc'] = is_lc
            result.at[idx, 'lc_tolerance_pct'] = lc_pct

        return result

    def detect_and_save_for_stock(self, stock_id):
        """Detect and save circuit events for a stock"""
        # Get OHLCV data
        df = self.db.get_ohlcv_data(stock_id)

        if df.empty:
            return {'status': 'no_data', 'uc_count': 0, 'lc_count': 0}

        try:
            # Detect circuits
            df = self.detect_circuits_in_dataframe(df)

            uc_count = 0
            lc_count = 0

            # Save UC events
            uc_events = df[df['is_uc'] == True]
            for _, row in uc_events.iterrows():
                self.db.add_circuit_event(
                    stock_id=stock_id,
                    date=row['date'],
                    event_type='UC',
                    close_price=row['close'],
                    high_price=row['high'],
                    low_price=row['low'],
                    tolerance_pct=row['uc_tolerance_pct']
                )
                uc_count += 1

            # Save LC events
            lc_events = df[df['is_lc'] == True]
            for _, row in lc_events.iterrows():
                self.db.add_circuit_event(
                    stock_id=stock_id,
                    date=row['date'],
                    event_type='LC',
                    close_price=row['close'],
                    high_price=row['high'],
                    low_price=row['low'],
                    tolerance_pct=row['lc_tolerance_pct']
                )
                lc_count += 1

            # Track UC to LC durations
            self._track_uc_to_lc(stock_id, df)

            return {'status': 'success', 'uc_count': uc_count, 'lc_count': lc_count}

        except Exception as e:
            return {'status': 'error', 'error': str(e), 'uc_count': 0, 'lc_count': 0}

    def _track_uc_to_lc(self, stock_id, df):
        """Track how many days from UC to LC"""
        df = df.sort_values('date').reset_index(drop=True)

        i = 0
        while i < len(df):
            row = df.iloc[i]

            # If we hit a UC
            if row['is_uc']:
                uc_date = row['date']
                days_to_lc = 0

                # Look for the next LC
                for j in range(i + 1, len(df)):
                    next_row = df.iloc[j]
                    days_to_lc += 1

                    if next_row['is_lc']:
                        # Found LC, record the duration
                        try:
                            self.db.add_uc_tracking(stock_id, uc_date)
                            self.db.complete_uc_tracking(
                                stock_id,
                                uc_date,
                                next_row['date'],
                                days_to_lc
                            )
                        except:
                            pass  # May already exist
                        i = j  # Continue from LC
                        break
                else:
                    # No LC found, add uncompleted tracking
                    try:
                        self.db.add_uc_tracking(stock_id, uc_date)
                    except:
                        pass

            i += 1

    def detect_for_all_stocks(self, exchange=None):
        """Detect circuits for all stocks"""
        stocks = self.db.get_all_stocks(exchange=exchange)
        total = len(stocks)

        results = {
            'total': total,
            'success': 0,
            'errors': 0,
            'total_uc': 0,
            'total_lc': 0
        }

        print(f"Detecting circuits for {total} stocks...")

        for stock in tqdm(stocks, desc="Detecting"):
            result = self.detect_and_save_for_stock(stock['id'])

            if result['status'] == 'success':
                results['success'] += 1
                results['total_uc'] += result['uc_count']
                results['total_lc'] += result['lc_count']
            else:
                results['errors'] += 1

        return results

    def get_current_status(self, stock_id):
        """
        Get current UC/LC status for a stock

        Returns dict with:
        - is_uc: bool
        - is_lc: bool
        - last_close: float
        - last_high: float
        - last_low: float
        """
        df = self.db.get_ohlcv_data(stock_id)

        if df.empty:
            return None

        # Get latest row
        latest = df.iloc[-1]

        is_uc, uc_pct = self.is_upper_circuit(latest['close'], latest['high'])
        is_lc, lc_pct = self.is_lower_circuit(latest['close'], latest['low'])

        return {
            'date': latest['date'],
            'is_uc': is_uc,
            'is_lc': is_lc,
            'close': latest['close'],
            'high': latest['high'],
            'low': latest['low'],
            'uc_tolerance_pct': uc_pct,
            'lc_tolerance_pct': lc_pct
        }

    def get_stocks_at_circuit(self, event_type='UC'):
        """Get all stocks currently at circuit"""
        stocks = self.db.get_all_stocks()
        at_circuit = []

        for stock in stocks:
            status = self.get_current_status(stock['id'])
            if status:
                if event_type == 'UC' and status['is_uc']:
                    at_circuit.append({**stock, **status})
                elif event_type == 'LC' and status['is_lc']:
                    at_circuit.append({**stock, **status})

        return at_circuit

    def get_circuit_statistics(self, stock_id=None):
        """Get circuit statistics"""
        if stock_id:
            uc_events = self.db.get_circuit_events(event_type='UC', stock_id=stock_id)
            lc_events = self.db.get_circuit_events(event_type='LC', stock_id=stock_id)
        else:
            uc_events = self.db.get_circuit_events(event_type='UC')
            lc_events = self.db.get_circuit_events(event_type='LC')

        # Get UC to LC duration history
        uc_to_lc = self.db.get_uc_to_lc_history(stock_id=stock_id)

        avg_days_to_lc = uc_to_lc['days_to_lc'].mean() if not uc_to_lc.empty else 0

        return {
            'total_uc': len(uc_events),
            'total_lc': len(lc_events),
            'avg_days_uc_to_lc': round(avg_days_to_lc, 1),
            'uc_to_lc_samples': len(uc_to_lc)
        }


if __name__ == '__main__':
    detector = CircuitDetector()
    results = detector.detect_for_all_stocks()
    print(f"\nDetection Results:")
    print(f"  Total stocks: {results['total']}")
    print(f"  Success: {results['success']}")
    print(f"  Total UC events: {results['total_uc']}")
    print(f"  Total LC events: {results['total_lc']}")
