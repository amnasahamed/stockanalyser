"""
Database Manager for Stock Circuit Predictor
Handles all SQLite database operations
"""
import sqlite3
import pandas as pd
from datetime import datetime, date
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_PATH


class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or DATABASE_PATH
        self.init_database()

    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Stocks master table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                name TEXT,
                exchange TEXT NOT NULL,
                sector TEXT,
                industry TEXT,
                is_active INTEGER DEFAULT 1,
                last_updated TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # OHLCV data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                date DATE NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                FOREIGN KEY (stock_id) REFERENCES stocks(id),
                UNIQUE(stock_id, date)
            )
        ''')

        # Technical indicators table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                date DATE NOT NULL,
                price_change_1d REAL,
                price_change_5d REAL,
                ma_5 REAL,
                ma_20 REAL,
                ma_50 REAL,
                rsi_14 REAL,
                macd REAL,
                macd_signal REAL,
                macd_histogram REAL,
                volume_ratio_20 REAL,
                atr_14 REAL,
                support_20 REAL,
                resistance_20 REAL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id),
                UNIQUE(stock_id, date)
            )
        ''')

        # UC/LC events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS circuit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                date DATE NOT NULL,
                event_type TEXT NOT NULL,
                close_price REAL,
                high_price REAL,
                low_price REAL,
                tolerance_pct REAL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id),
                UNIQUE(stock_id, date, event_type)
            )
        ''')

        # UC to LC duration tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS uc_to_lc_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                uc_date DATE NOT NULL,
                lc_date DATE,
                days_to_lc INTEGER,
                is_completed INTEGER DEFAULT 0,
                FOREIGN KEY (stock_id) REFERENCES stocks(id)
            )
        ''')

        # Download progress tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS download_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                last_download_date DATE,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                FOREIGN KEY (stock_id) REFERENCES stocks(id),
                UNIQUE(stock_id)
            )
        ''')

        # Predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                prediction_date DATE NOT NULL,
                target_date DATE NOT NULL,
                uc_probability REAL,
                predicted_uc_to_lc_days REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stock_id) REFERENCES stocks(id)
            )
        ''')

        # Extended stock fundamentals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_fundamentals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                market_cap REAL,
                market_cap_category TEXT,
                week_52_high REAL,
                week_52_low REAL,
                avg_delivery_pct REAL,
                is_fno INTEGER DEFAULT 0,
                lot_size INTEGER,
                is_asm INTEGER DEFAULT 0,
                is_gsm INTEGER DEFAULT 0,
                is_esm INTEGER DEFAULT 0,
                is_penny_stock INTEGER DEFAULT 0,
                face_value REAL,
                book_value REAL,
                pe_ratio REAL,
                pb_ratio REAL,
                dividend_yield REAL,
                last_updated TIMESTAMP,
                FOREIGN KEY (stock_id) REFERENCES stocks(id),
                UNIQUE(stock_id)
            )
        ''')

        # Extended indicators table with EMA, momentum, etc.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extended_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                date DATE NOT NULL,
                ema_9 REAL,
                ema_21 REAL,
                ema_50 REAL,
                ema_200 REAL,
                sma_200 REAL,
                bollinger_upper REAL,
                bollinger_middle REAL,
                bollinger_lower REAL,
                stochastic_k REAL,
                stochastic_d REAL,
                adx_14 REAL,
                obv REAL,
                vwap REAL,
                momentum_score REAL,
                momentum_rank INTEGER,
                distance_from_52w_high REAL,
                distance_from_52w_low REAL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id),
                UNIQUE(stock_id, date)
            )
        ''')

        # Bulk/Block deals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bulk_block_deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                date DATE NOT NULL,
                deal_type TEXT NOT NULL,
                client_name TEXT,
                buy_sell TEXT,
                quantity INTEGER,
                price REAL,
                total_value REAL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id)
            )
        ''')

        # Breakout signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS breakout_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                date DATE NOT NULL,
                signal_type TEXT NOT NULL,
                signal_strength REAL,
                entry_price REAL,
                stop_loss REAL,
                target_1 REAL,
                target_2 REAL,
                risk_reward_ratio REAL,
                volume_confirmation INTEGER DEFAULT 0,
                trend_confirmation INTEGER DEFAULT 0,
                notes TEXT,
                FOREIGN KEY (stock_id) REFERENCES stocks(id),
                UNIQUE(stock_id, date, signal_type)
            )
        ''')

        # Daily delivery data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS delivery_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                date DATE NOT NULL,
                traded_qty INTEGER,
                deliverable_qty INTEGER,
                delivery_pct REAL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id),
                UNIQUE(stock_id, date)
            )
        ''')

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ohlcv_stock_date ON ohlcv_data(stock_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_indicators_stock_date ON indicators(stock_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_circuit_events_date ON circuit_events(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_circuit_events_type ON circuit_events(event_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_stocks_exchange ON stocks(exchange)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_extended_indicators_stock_date ON extended_indicators(stock_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bulk_block_deals_date ON bulk_block_deals(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_breakout_signals_date ON breakout_signals(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_delivery_data_stock_date ON delivery_data(stock_id, date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fundamentals_market_cap ON stock_fundamentals(market_cap)')

        conn.commit()
        conn.close()

    # Stock operations
    def add_stock(self, symbol, name, exchange, sector=None, industry=None):
        """Add a stock to the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO stocks (symbol, name, exchange, sector, industry, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (symbol, name, exchange, sector, industry, datetime.now()))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_stock_by_symbol(self, symbol):
        """Get stock by symbol"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM stocks WHERE symbol = ?', (symbol,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None

    def get_all_stocks(self, exchange=None):
        """Get all stocks, optionally filtered by exchange"""
        conn = self.get_connection()
        cursor = conn.cursor()
        if exchange:
            cursor.execute('SELECT * FROM stocks WHERE exchange = ? AND is_active = 1', (exchange,))
        else:
            cursor.execute('SELECT * FROM stocks WHERE is_active = 1')
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]

    def get_stock_count(self, exchange=None):
        """Get count of stocks"""
        conn = self.get_connection()
        cursor = conn.cursor()
        if exchange:
            cursor.execute('SELECT COUNT(*) FROM stocks WHERE exchange = ? AND is_active = 1', (exchange,))
        else:
            cursor.execute('SELECT COUNT(*) FROM stocks WHERE is_active = 1')
        result = cursor.fetchone()[0]
        conn.close()
        return result

    # OHLCV operations
    def add_ohlcv_data(self, stock_id, df):
        """Add OHLCV data for a stock from a DataFrame"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO ohlcv_data (stock_id, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (stock_id, row['date'], row['open'], row['high'], row['low'], row['close'], row['volume']))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_ohlcv_data(self, stock_id, start_date=None, end_date=None):
        """Get OHLCV data for a stock"""
        conn = self.get_connection()
        query = 'SELECT * FROM ohlcv_data WHERE stock_id = ?'
        params = [stock_id]

        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)

        query += ' ORDER BY date'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def get_latest_ohlcv_date(self, stock_id):
        """Get the latest OHLCV date for a stock"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(date) FROM ohlcv_data WHERE stock_id = ?', (stock_id,))
        result = cursor.fetchone()[0]
        conn.close()
        return result

    # Indicators operations
    def add_indicators(self, stock_id, df):
        """Add technical indicators for a stock from a DataFrame"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO indicators
                    (stock_id, date, price_change_1d, price_change_5d, ma_5, ma_20, ma_50,
                     rsi_14, macd, macd_signal, macd_histogram, volume_ratio_20, atr_14,
                     support_20, resistance_20)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (stock_id, row['date'], row.get('price_change_1d'), row.get('price_change_5d'),
                      row.get('ma_5'), row.get('ma_20'), row.get('ma_50'), row.get('rsi_14'),
                      row.get('macd'), row.get('macd_signal'), row.get('macd_histogram'),
                      row.get('volume_ratio_20'), row.get('atr_14'), row.get('support_20'),
                      row.get('resistance_20')))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_indicators(self, stock_id, start_date=None, end_date=None):
        """Get indicators for a stock"""
        conn = self.get_connection()
        query = 'SELECT * FROM indicators WHERE stock_id = ?'
        params = [stock_id]

        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)

        query += ' ORDER BY date'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    # Circuit events operations
    def add_circuit_event(self, stock_id, date, event_type, close_price, high_price, low_price, tolerance_pct):
        """Add a circuit event (UC or LC)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO circuit_events
                (stock_id, date, event_type, close_price, high_price, low_price, tolerance_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (stock_id, date, event_type, close_price, high_price, low_price, tolerance_pct))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_circuit_events(self, event_type=None, start_date=None, end_date=None, stock_id=None):
        """Get circuit events with optional filters"""
        conn = self.get_connection()
        query = '''
            SELECT ce.*, s.symbol, s.name, s.exchange
            FROM circuit_events ce
            JOIN stocks s ON ce.stock_id = s.id
            WHERE 1=1
        '''
        params = []

        if event_type:
            query += ' AND ce.event_type = ?'
            params.append(event_type)
        if start_date:
            query += ' AND ce.date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND ce.date <= ?'
            params.append(end_date)
        if stock_id:
            query += ' AND ce.stock_id = ?'
            params.append(stock_id)

        query += ' ORDER BY ce.date DESC'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def get_today_circuits(self, event_type=None):
        """Get today's circuit events"""
        today = date.today().isoformat()
        return self.get_circuit_events(event_type=event_type, start_date=today, end_date=today)

    # UC to LC tracking
    def add_uc_tracking(self, stock_id, uc_date):
        """Start tracking UC to LC duration"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO uc_to_lc_tracking (stock_id, uc_date)
                VALUES (?, ?)
            ''', (stock_id, uc_date))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def complete_uc_tracking(self, stock_id, uc_date, lc_date, days_to_lc):
        """Complete UC to LC tracking when LC is hit"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE uc_to_lc_tracking
                SET lc_date = ?, days_to_lc = ?, is_completed = 1
                WHERE stock_id = ? AND uc_date = ? AND is_completed = 0
            ''', (lc_date, days_to_lc, stock_id, uc_date))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_uc_to_lc_history(self, stock_id=None):
        """Get UC to LC duration history"""
        conn = self.get_connection()
        query = '''
            SELECT t.*, s.symbol, s.name
            FROM uc_to_lc_tracking t
            JOIN stocks s ON t.stock_id = s.id
            WHERE t.is_completed = 1
        '''
        params = []

        if stock_id:
            query += ' AND t.stock_id = ?'
            params.append(stock_id)

        query += ' ORDER BY t.uc_date DESC'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    # Download progress
    def update_download_progress(self, stock_id, status, error_message=None):
        """Update download progress for a stock"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO download_progress (stock_id, last_download_date, status, error_message)
                VALUES (?, ?, ?, ?)
            ''', (stock_id, date.today().isoformat(), status, error_message))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_pending_downloads(self):
        """Get stocks that need to be downloaded"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.* FROM stocks s
            LEFT JOIN download_progress dp ON s.id = dp.stock_id
            WHERE s.is_active = 1 AND (dp.status IS NULL OR dp.status = 'pending' OR dp.status = 'error')
            ORDER BY s.id
        ''')
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]

    def get_download_stats(self):
        """Get download statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN dp.status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN dp.status = 'error' THEN 1 ELSE 0 END) as errors,
                SUM(CASE WHEN dp.status IS NULL OR dp.status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM stocks s
            LEFT JOIN download_progress dp ON s.id = dp.stock_id
            WHERE s.is_active = 1
        ''')
        result = cursor.fetchone()
        conn.close()
        return dict(result)

    # Predictions
    def save_prediction(self, stock_id, prediction_date, target_date, uc_probability, predicted_uc_to_lc_days):
        """Save a prediction for a stock"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO predictions (stock_id, prediction_date, target_date, uc_probability, predicted_uc_to_lc_days)
                VALUES (?, ?, ?, ?, ?)
            ''', (stock_id, prediction_date, target_date, uc_probability, predicted_uc_to_lc_days))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_latest_predictions(self, limit=100):
        """Get latest predictions"""
        conn = self.get_connection()
        query = '''
            SELECT p.*, s.symbol, s.name, s.exchange
            FROM predictions p
            JOIN stocks s ON p.stock_id = s.id
            ORDER BY p.uc_probability DESC, p.created_at DESC
            LIMIT ?
        '''
        df = pd.read_sql_query(query, conn, params=[limit])
        conn.close()
        return df

    # Utility methods
    def get_stock_with_latest_data(self, symbol):
        """Get stock with its latest OHLCV and indicators"""
        stock = self.get_stock_by_symbol(symbol)
        if not stock:
            return None

        conn = self.get_connection()

        # Get latest OHLCV
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM ohlcv_data WHERE stock_id = ? ORDER BY date DESC LIMIT 1
        ''', (stock['id'],))
        ohlcv = cursor.fetchone()

        # Get latest indicators
        cursor.execute('''
            SELECT * FROM indicators WHERE stock_id = ? ORDER BY date DESC LIMIT 1
        ''', (stock['id'],))
        indicators = cursor.fetchone()

        conn.close()

        return {
            'stock': stock,
            'ohlcv': dict(ohlcv) if ohlcv else None,
            'indicators': dict(indicators) if indicators else None
        }

    def search_stocks(self, query):
        """Search stocks by symbol or name"""
        conn = self.get_connection()
        cursor = conn.cursor()
        search_term = f'%{query}%'
        cursor.execute('''
            SELECT * FROM stocks
            WHERE (symbol LIKE ? OR name LIKE ?) AND is_active = 1
            ORDER BY symbol
            LIMIT 50
        ''', (search_term, search_term))
        results = cursor.fetchall()
        conn.close()
        return [dict(row) for row in results]

    # Stock fundamentals operations
    def update_stock_fundamentals(self, stock_id, data):
        """Update stock fundamentals data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO stock_fundamentals
                (stock_id, market_cap, market_cap_category, week_52_high, week_52_low,
                 avg_delivery_pct, is_fno, lot_size, is_asm, is_gsm, is_esm, is_penny_stock,
                 face_value, book_value, pe_ratio, pb_ratio, dividend_yield, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (stock_id, data.get('market_cap'), data.get('market_cap_category'),
                  data.get('week_52_high'), data.get('week_52_low'), data.get('avg_delivery_pct'),
                  data.get('is_fno', 0), data.get('lot_size'), data.get('is_asm', 0),
                  data.get('is_gsm', 0), data.get('is_esm', 0), data.get('is_penny_stock', 0),
                  data.get('face_value'), data.get('book_value'), data.get('pe_ratio'),
                  data.get('pb_ratio'), data.get('dividend_yield'), datetime.now()))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_stock_fundamentals(self, stock_id):
        """Get stock fundamentals"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM stock_fundamentals WHERE stock_id = ?', (stock_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None

    def get_penny_stocks(self):
        """Get all penny stocks"""
        conn = self.get_connection()
        query = '''
            SELECT s.*, sf.market_cap, sf.week_52_high, sf.week_52_low
            FROM stocks s
            JOIN stock_fundamentals sf ON s.id = sf.stock_id
            WHERE sf.is_penny_stock = 1 AND s.is_active = 1
            ORDER BY sf.market_cap
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def get_fno_stocks(self):
        """Get all F&O stocks with lot sizes"""
        conn = self.get_connection()
        query = '''
            SELECT s.*, sf.lot_size, sf.market_cap
            FROM stocks s
            JOIN stock_fundamentals sf ON s.id = sf.stock_id
            WHERE sf.is_fno = 1 AND s.is_active = 1
            ORDER BY s.symbol
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    # Extended indicators operations
    def add_extended_indicators(self, stock_id, df):
        """Add extended indicators for a stock"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT OR REPLACE INTO extended_indicators
                    (stock_id, date, ema_9, ema_21, ema_50, ema_200, sma_200,
                     bollinger_upper, bollinger_middle, bollinger_lower,
                     stochastic_k, stochastic_d, adx_14, obv, vwap,
                     momentum_score, momentum_rank, distance_from_52w_high, distance_from_52w_low)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (stock_id, row['date'], row.get('ema_9'), row.get('ema_21'),
                      row.get('ema_50'), row.get('ema_200'), row.get('sma_200'),
                      row.get('bollinger_upper'), row.get('bollinger_middle'), row.get('bollinger_lower'),
                      row.get('stochastic_k'), row.get('stochastic_d'), row.get('adx_14'),
                      row.get('obv'), row.get('vwap'), row.get('momentum_score'),
                      row.get('momentum_rank'), row.get('distance_from_52w_high'),
                      row.get('distance_from_52w_low')))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_extended_indicators(self, stock_id, start_date=None, end_date=None):
        """Get extended indicators for a stock"""
        conn = self.get_connection()
        query = 'SELECT * FROM extended_indicators WHERE stock_id = ?'
        params = [stock_id]
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)
        query += ' ORDER BY date'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def get_top_momentum_stocks(self, limit=50, exchange=None):
        """Get top stocks by momentum rank"""
        conn = self.get_connection()
        query = '''
            SELECT s.symbol, s.name, s.exchange, ei.momentum_score, ei.momentum_rank, ei.date
            FROM extended_indicators ei
            JOIN stocks s ON ei.stock_id = s.id
            WHERE ei.date = (SELECT MAX(date) FROM extended_indicators WHERE stock_id = ei.stock_id)
        '''
        params = []
        if exchange:
            query += ' AND s.exchange = ?'
            params.append(exchange)
        query += ' ORDER BY ei.momentum_rank ASC LIMIT ?'
        params.append(limit)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    # Bulk/Block deals operations
    def add_bulk_block_deal(self, stock_id, date, deal_type, client_name, buy_sell, quantity, price):
        """Add a bulk or block deal"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            total_value = quantity * price if quantity and price else None
            cursor.execute('''
                INSERT INTO bulk_block_deals
                (stock_id, date, deal_type, client_name, buy_sell, quantity, price, total_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (stock_id, date, deal_type, client_name, buy_sell, quantity, price, total_value))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_bulk_block_deals(self, stock_id=None, start_date=None, end_date=None, deal_type=None):
        """Get bulk/block deals"""
        conn = self.get_connection()
        query = '''
            SELECT bb.*, s.symbol, s.name
            FROM bulk_block_deals bb
            JOIN stocks s ON bb.stock_id = s.id
            WHERE 1=1
        '''
        params = []
        if stock_id:
            query += ' AND bb.stock_id = ?'
            params.append(stock_id)
        if start_date:
            query += ' AND bb.date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND bb.date <= ?'
            params.append(end_date)
        if deal_type:
            query += ' AND bb.deal_type = ?'
            params.append(deal_type)
        query += ' ORDER BY bb.date DESC, bb.total_value DESC'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    # Breakout signals operations
    def add_breakout_signal(self, stock_id, date, signal_type, signal_strength, entry_price,
                           stop_loss, target_1, target_2, risk_reward_ratio,
                           volume_confirmation=False, trend_confirmation=False, notes=None):
        """Add a breakout signal"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO breakout_signals
                (stock_id, date, signal_type, signal_strength, entry_price, stop_loss,
                 target_1, target_2, risk_reward_ratio, volume_confirmation, trend_confirmation, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (stock_id, date, signal_type, signal_strength, entry_price, stop_loss,
                  target_1, target_2, risk_reward_ratio, int(volume_confirmation),
                  int(trend_confirmation), notes))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_breakout_signals(self, min_strength=0, date=None, signal_type=None):
        """Get breakout signals"""
        conn = self.get_connection()
        query = '''
            SELECT bs.*, s.symbol, s.name, s.exchange
            FROM breakout_signals bs
            JOIN stocks s ON bs.stock_id = s.id
            WHERE bs.signal_strength >= ?
        '''
        params = [min_strength]
        if date:
            query += ' AND bs.date = ?'
            params.append(date)
        if signal_type:
            query += ' AND bs.signal_type = ?'
            params.append(signal_type)
        query += ' ORDER BY bs.signal_strength DESC, bs.risk_reward_ratio DESC'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    # Delivery data operations
    def add_delivery_data(self, stock_id, date, traded_qty, deliverable_qty, delivery_pct):
        """Add delivery data for a stock"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO delivery_data
                (stock_id, date, traded_qty, deliverable_qty, delivery_pct)
                VALUES (?, ?, ?, ?, ?)
            ''', (stock_id, date, traded_qty, deliverable_qty, delivery_pct))
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_delivery_data(self, stock_id, start_date=None, end_date=None):
        """Get delivery data for a stock"""
        conn = self.get_connection()
        query = 'SELECT * FROM delivery_data WHERE stock_id = ?'
        params = [stock_id]
        if start_date:
            query += ' AND date >= ?'
            params.append(start_date)
        if end_date:
            query += ' AND date <= ?'
            params.append(end_date)
        query += ' ORDER BY date'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def get_high_delivery_stocks(self, min_delivery_pct=50, date=None):
        """Get stocks with high delivery percentage"""
        conn = self.get_connection()
        query = '''
            SELECT s.symbol, s.name, s.exchange, dd.delivery_pct, dd.traded_qty, dd.date
            FROM delivery_data dd
            JOIN stocks s ON dd.stock_id = s.id
            WHERE dd.delivery_pct >= ?
        '''
        params = [min_delivery_pct]
        if date:
            query += ' AND dd.date = ?'
            params.append(date)
        else:
            query += ' AND dd.date = (SELECT MAX(date) FROM delivery_data WHERE stock_id = dd.stock_id)'
        query += ' ORDER BY dd.delivery_pct DESC'
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    def get_comprehensive_stock_data(self, symbol):
        """Get comprehensive stock data including all metrics"""
        stock = self.get_stock_by_symbol(symbol)
        if not stock:
            return None

        conn = self.get_connection()
        stock_id = stock['id']

        # Get fundamentals
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM stock_fundamentals WHERE stock_id = ?', (stock_id,))
        fundamentals = cursor.fetchone()

        # Get latest OHLCV
        cursor.execute('SELECT * FROM ohlcv_data WHERE stock_id = ? ORDER BY date DESC LIMIT 1', (stock_id,))
        ohlcv = cursor.fetchone()

        # Get latest indicators
        cursor.execute('SELECT * FROM indicators WHERE stock_id = ? ORDER BY date DESC LIMIT 1', (stock_id,))
        indicators = cursor.fetchone()

        # Get latest extended indicators
        cursor.execute('SELECT * FROM extended_indicators WHERE stock_id = ? ORDER BY date DESC LIMIT 1', (stock_id,))
        extended = cursor.fetchone()

        # Get latest delivery data
        cursor.execute('SELECT * FROM delivery_data WHERE stock_id = ? ORDER BY date DESC LIMIT 1', (stock_id,))
        delivery = cursor.fetchone()

        # Get recent breakout signals
        cursor.execute('''
            SELECT * FROM breakout_signals WHERE stock_id = ?
            ORDER BY date DESC LIMIT 5
        ''', (stock_id,))
        signals = cursor.fetchall()

        # Get recent bulk/block deals
        cursor.execute('''
            SELECT * FROM bulk_block_deals WHERE stock_id = ?
            ORDER BY date DESC LIMIT 10
        ''', (stock_id,))
        deals = cursor.fetchall()

        conn.close()

        return {
            'stock': stock,
            'fundamentals': dict(fundamentals) if fundamentals else None,
            'ohlcv': dict(ohlcv) if ohlcv else None,
            'indicators': dict(indicators) if indicators else None,
            'extended_indicators': dict(extended) if extended else None,
            'delivery': dict(delivery) if delivery else None,
            'breakout_signals': [dict(s) for s in signals],
            'bulk_block_deals': [dict(d) for d in deals]
        }


# Create __init__.py
if __name__ == '__main__':
    db = DatabaseManager()
    print("Database initialized successfully!")
