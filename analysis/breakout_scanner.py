"""
High-Probability Breakout Scanner for Stock Circuit Predictor
Identifies breakout opportunities based on various technical patterns
"""
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db_manager import DatabaseManager


class BreakoutScanner:
    """Scanner for identifying high-probability breakout opportunities"""

    def __init__(self):
        self.db = DatabaseManager()

    def scan_resistance_breakout(self, stock_id, lookback_days=20):
        """Detect resistance breakout pattern"""
        ohlcv = self.db.get_ohlcv_data(stock_id)
        if len(ohlcv) < lookback_days + 5:
            return None

        df = ohlcv.tail(lookback_days + 5)
        latest = df.iloc[-1]

        # Calculate resistance (highest high in lookback period excluding last day)
        resistance = df['high'].iloc[:-1].max()
        resistance_date = df.loc[df['high'].iloc[:-1].idxmax(), 'date']

        # Check if current close breaks resistance with volume
        if latest['close'] > resistance:
            avg_volume = df['volume'].iloc[:-1].mean()
            volume_surge = latest['volume'] > avg_volume * 1.5

            # Calculate strength based on % above resistance and volume
            breakout_pct = (latest['close'] - resistance) / resistance * 100
            strength = min(100, breakout_pct * 10 + (20 if volume_surge else 0))

            # Entry and targets
            entry = latest['close']
            stop_loss = resistance * 0.98  # 2% below resistance
            target_1 = entry + (entry - stop_loss) * 2  # 2:1 risk-reward
            target_2 = entry + (entry - stop_loss) * 3  # 3:1 risk-reward
            risk_reward = (target_1 - entry) / (entry - stop_loss)

            return {
                'signal_type': 'RESISTANCE_BREAKOUT',
                'signal_strength': strength,
                'entry_price': entry,
                'stop_loss': stop_loss,
                'target_1': target_1,
                'target_2': target_2,
                'risk_reward_ratio': risk_reward,
                'volume_confirmation': volume_surge,
                'notes': f"Broke {lookback_days}D resistance at {resistance:.2f}"
            }

        return None

    def scan_52w_high_breakout(self, stock_id):
        """Detect 52-week high breakout"""
        ohlcv = self.db.get_ohlcv_data(stock_id)
        if len(ohlcv) < 252:
            return None

        df = ohlcv.tail(252)
        latest = df.iloc[-1]

        # Calculate 52-week high excluding today
        week_52_high = df['high'].iloc[:-1].max()

        # Check if making new 52-week high
        if latest['high'] > week_52_high:
            avg_volume = df['volume'].mean()
            volume_surge = latest['volume'] > avg_volume * 1.3

            # Higher strength for 52W breakouts
            breakout_pct = (latest['close'] - week_52_high) / week_52_high * 100
            strength = min(100, 60 + breakout_pct * 5 + (15 if volume_surge else 0))

            entry = latest['close']
            stop_loss = week_52_high * 0.97
            target_1 = entry * 1.08  # 8% target
            target_2 = entry * 1.15  # 15% target
            risk_reward = (target_1 - entry) / (entry - stop_loss)

            return {
                'signal_type': '52W_HIGH_BREAKOUT',
                'signal_strength': strength,
                'entry_price': entry,
                'stop_loss': stop_loss,
                'target_1': target_1,
                'target_2': target_2,
                'risk_reward_ratio': risk_reward,
                'volume_confirmation': volume_surge,
                'notes': f"New 52W high, previous: {week_52_high:.2f}"
            }

        return None

    def scan_volume_breakout(self, stock_id, volume_multiple=3):
        """Detect volume breakout (unusual volume with price movement)"""
        ohlcv = self.db.get_ohlcv_data(stock_id)
        if len(ohlcv) < 30:
            return None

        df = ohlcv.tail(30)
        latest = df.iloc[-1]

        avg_volume = df['volume'].iloc[:-1].mean()

        # Check for volume surge
        if latest['volume'] > avg_volume * volume_multiple:
            # Check price movement direction
            price_change = (latest['close'] - latest['open']) / latest['open'] * 100

            if price_change > 2:  # Bullish
                strength = min(100, 50 + price_change * 5 + (latest['volume'] / avg_volume) * 3)

                entry = latest['close']
                stop_loss = latest['low'] * 0.98
                target_1 = entry * 1.05
                target_2 = entry * 1.10
                risk_reward = (target_1 - entry) / (entry - stop_loss)

                return {
                    'signal_type': 'VOLUME_BREAKOUT',
                    'signal_strength': strength,
                    'entry_price': entry,
                    'stop_loss': stop_loss,
                    'target_1': target_1,
                    'target_2': target_2,
                    'risk_reward_ratio': risk_reward,
                    'volume_confirmation': True,
                    'notes': f"Volume {latest['volume']/avg_volume:.1f}x avg, +{price_change:.1f}%"
                }

        return None

    def scan_bollinger_squeeze(self, stock_id):
        """Detect Bollinger Band squeeze breakout"""
        ohlcv = self.db.get_ohlcv_data(stock_id)
        extended = self.db.get_extended_indicators(stock_id)

        if len(ohlcv) < 30 or extended.empty:
            return None

        df = ohlcv.merge(extended, on='date', how='left').tail(30)
        if 'bollinger_upper' not in df.columns:
            return None

        latest = df.iloc[-1]

        # Calculate band width
        if pd.isna(latest.get('bollinger_upper')) or pd.isna(latest.get('bollinger_lower')):
            return None

        band_width = (latest['bollinger_upper'] - latest['bollinger_lower']) / latest['bollinger_middle']

        # Check for squeeze (narrow bands) followed by expansion
        avg_band_width = df.apply(
            lambda r: (r['bollinger_upper'] - r['bollinger_lower']) / r['bollinger_middle']
            if pd.notna(r.get('bollinger_upper')) else None, axis=1
        ).mean()

        # Recent contraction followed by expansion
        if band_width > avg_band_width * 1.2 and latest['close'] > latest['bollinger_upper']:
            strength = min(100, 60 + (band_width / avg_band_width - 1) * 50)

            entry = latest['close']
            stop_loss = latest['bollinger_middle']
            target_1 = entry + (entry - stop_loss)
            target_2 = entry + (entry - stop_loss) * 1.5
            risk_reward = (target_1 - entry) / (entry - stop_loss)

            return {
                'signal_type': 'BOLLINGER_BREAKOUT',
                'signal_strength': strength,
                'entry_price': entry,
                'stop_loss': stop_loss,
                'target_1': target_1,
                'target_2': target_2,
                'risk_reward_ratio': risk_reward,
                'volume_confirmation': False,
                'notes': f"Bollinger squeeze breakout"
            }

        return None

    def scan_ema_crossover(self, stock_id):
        """Detect EMA crossover (9 EMA crosses above 21 EMA)"""
        extended = self.db.get_extended_indicators(stock_id)
        if len(extended) < 5:
            return None

        df = extended.tail(5)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Check for bullish EMA crossover
        if (pd.notna(latest.get('ema_9')) and pd.notna(latest.get('ema_21')) and
            pd.notna(prev.get('ema_9')) and pd.notna(prev.get('ema_21'))):

            # 9 EMA crossed above 21 EMA
            if prev['ema_9'] <= prev['ema_21'] and latest['ema_9'] > latest['ema_21']:
                # Check if price is above both EMAs
                ohlcv = self.db.get_ohlcv_data(stock_id)
                if not ohlcv.empty:
                    close = ohlcv.iloc[-1]['close']
                    if close > latest['ema_9'] > latest['ema_21']:
                        strength = min(100, 65)

                        entry = close
                        stop_loss = latest['ema_21'] * 0.98
                        target_1 = entry * 1.05
                        target_2 = entry * 1.10
                        risk_reward = (target_1 - entry) / (entry - stop_loss) if entry > stop_loss else 0

                        return {
                            'signal_type': 'EMA_CROSSOVER',
                            'signal_strength': strength,
                            'entry_price': entry,
                            'stop_loss': stop_loss,
                            'target_1': target_1,
                            'target_2': target_2,
                            'risk_reward_ratio': risk_reward,
                            'volume_confirmation': False,
                            'trend_confirmation': True,
                            'notes': "9 EMA crossed above 21 EMA"
                        }

        return None

    def scan_macd_crossover(self, stock_id):
        """Detect MACD bullish crossover"""
        indicators = self.db.get_indicators(stock_id)
        if len(indicators) < 5:
            return None

        df = indicators.tail(5)
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Check for MACD crossover (MACD crosses above signal line)
        if (pd.notna(latest.get('macd')) and pd.notna(latest.get('macd_signal')) and
            pd.notna(prev.get('macd')) and pd.notna(prev.get('macd_signal'))):

            if prev['macd'] <= prev['macd_signal'] and latest['macd'] > latest['macd_signal']:
                # Get current price
                ohlcv = self.db.get_ohlcv_data(stock_id)
                if not ohlcv.empty:
                    close = ohlcv.iloc[-1]['close']

                    strength = min(100, 55 + (latest['macd_histogram'] * 10 if latest.get('macd_histogram', 0) > 0 else 0))

                    entry = close
                    stop_loss = close * 0.97
                    target_1 = entry * 1.04
                    target_2 = entry * 1.08
                    risk_reward = (target_1 - entry) / (entry - stop_loss)

                    return {
                        'signal_type': 'MACD_CROSSOVER',
                        'signal_strength': strength,
                        'entry_price': entry,
                        'stop_loss': stop_loss,
                        'target_1': target_1,
                        'target_2': target_2,
                        'risk_reward_ratio': risk_reward,
                        'volume_confirmation': False,
                        'notes': f"MACD: {latest['macd']:.2f}, Signal: {latest['macd_signal']:.2f}"
                    }

        return None

    def scan_rsi_oversold_reversal(self, stock_id):
        """Detect RSI reversal from oversold"""
        indicators = self.db.get_indicators(stock_id)
        if len(indicators) < 10:
            return None

        df = indicators.tail(10)

        # Check if RSI was below 30 recently and now recovering
        recent_rsi = df['rsi_14'].tail(5)
        if recent_rsi.min() < 30 and recent_rsi.iloc[-1] > 35:
            # Get price data
            ohlcv = self.db.get_ohlcv_data(stock_id)
            if ohlcv.empty:
                return None

            close = ohlcv.iloc[-1]['close']

            # Check for price confirmation (higher low)
            if len(ohlcv) >= 5:
                recent_lows = ohlcv['low'].tail(5)
                if recent_lows.iloc[-1] > recent_lows.min():
                    strength = min(100, 50 + (recent_rsi.iloc[-1] - recent_rsi.min()) * 2)

                    entry = close
                    stop_loss = recent_lows.min() * 0.98
                    target_1 = entry * 1.06
                    target_2 = entry * 1.12
                    risk_reward = (target_1 - entry) / (entry - stop_loss)

                    return {
                        'signal_type': 'RSI_REVERSAL',
                        'signal_strength': strength,
                        'entry_price': entry,
                        'stop_loss': stop_loss,
                        'target_1': target_1,
                        'target_2': target_2,
                        'risk_reward_ratio': risk_reward,
                        'volume_confirmation': False,
                        'notes': f"RSI bounced from {recent_rsi.min():.1f} to {recent_rsi.iloc[-1]:.1f}"
                    }

        return None

    def scan_consolidation_breakout(self, stock_id, consolidation_days=10, range_pct=5):
        """Detect breakout from consolidation/tight range"""
        ohlcv = self.db.get_ohlcv_data(stock_id)
        if len(ohlcv) < consolidation_days + 5:
            return None

        df = ohlcv.tail(consolidation_days + 5)

        # Check if price was consolidating
        consol_range = df.iloc[:-1]
        high_range = consol_range['high'].max()
        low_range = consol_range['low'].min()
        range_width = (high_range - low_range) / low_range * 100

        # Tight consolidation
        if range_width < range_pct:
            latest = df.iloc[-1]

            # Breakout above consolidation
            if latest['close'] > high_range:
                avg_volume = df['volume'].iloc[:-1].mean()
                volume_surge = latest['volume'] > avg_volume * 1.5

                strength = min(100, 70 - range_width * 5 + (15 if volume_surge else 0))

                entry = latest['close']
                stop_loss = low_range * 0.98
                target_1 = entry + (entry - stop_loss) * 2
                target_2 = entry + (entry - stop_loss) * 3
                risk_reward = (target_1 - entry) / (entry - stop_loss)

                return {
                    'signal_type': 'CONSOLIDATION_BREAKOUT',
                    'signal_strength': strength,
                    'entry_price': entry,
                    'stop_loss': stop_loss,
                    'target_1': target_1,
                    'target_2': target_2,
                    'risk_reward_ratio': risk_reward,
                    'volume_confirmation': volume_surge,
                    'notes': f"Broke {consolidation_days}D consolidation ({range_width:.1f}% range)"
                }

        return None

    def scan_all_patterns(self, stock_id):
        """Scan all breakout patterns for a stock"""
        signals = []

        patterns = [
            self.scan_52w_high_breakout,
            self.scan_resistance_breakout,
            self.scan_volume_breakout,
            self.scan_bollinger_squeeze,
            self.scan_ema_crossover,
            self.scan_macd_crossover,
            self.scan_rsi_oversold_reversal,
            self.scan_consolidation_breakout,
        ]

        for pattern_func in patterns:
            try:
                signal = pattern_func(stock_id)
                if signal:
                    signals.append(signal)
            except Exception:
                continue

        return signals

    def scan_all_stocks(self, exchange=None, min_strength=50, progress_callback=None):
        """Scan all stocks for breakout signals"""
        stocks = self.db.get_all_stocks(exchange)
        total = len(stocks)

        if progress_callback:
            progress_callback(f"Scanning {total} stocks for breakout patterns...")

        all_signals = []
        today = date.today().isoformat()

        for i, stock in enumerate(stocks):
            try:
                signals = self.scan_all_patterns(stock['id'])

                for signal in signals:
                    if signal['signal_strength'] >= min_strength:
                        # Save to database
                        self.db.add_breakout_signal(
                            stock['id'],
                            today,
                            signal['signal_type'],
                            signal['signal_strength'],
                            signal['entry_price'],
                            signal['stop_loss'],
                            signal['target_1'],
                            signal['target_2'],
                            signal['risk_reward_ratio'],
                            signal.get('volume_confirmation', False),
                            signal.get('trend_confirmation', False),
                            signal.get('notes')
                        )

                        signal['symbol'] = stock['symbol']
                        signal['name'] = stock['name']
                        signal['exchange'] = stock['exchange']
                        all_signals.append(signal)

                if progress_callback and (i + 1) % 100 == 0:
                    progress_callback(f"Progress: {i + 1}/{total}")

            except Exception:
                continue

        # Sort by signal strength
        all_signals.sort(key=lambda x: x['signal_strength'], reverse=True)

        if progress_callback:
            progress_callback(f"Found {len(all_signals)} breakout signals")

        return all_signals

    def get_high_probability_breakouts(self, min_strength=70, limit=50):
        """Get high-probability breakout signals from database"""
        today = date.today().isoformat()
        return self.db.get_breakout_signals(min_strength=min_strength, date=today).head(limit)


if __name__ == '__main__':
    scanner = BreakoutScanner()

    print("Testing Breakout Scanner...")

    # Test scan
    stocks = scanner.db.get_all_stocks('NSE')
    if stocks:
        test_stock = stocks[0]
        signals = scanner.scan_all_patterns(test_stock['id'])
        print(f"Signals for {test_stock['symbol']}: {len(signals)}")
        for signal in signals:
            print(f"  - {signal['signal_type']}: {signal['signal_strength']:.0f}%")

    print("Breakout Scanner initialized successfully!")
