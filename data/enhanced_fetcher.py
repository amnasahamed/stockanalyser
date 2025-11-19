"""
Enhanced Data Fetcher for Stock Circuit Predictor
Fetches market cap, sector, 52W data, delivery %, futures lot size, bulk/block deals, etc.
"""
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, date, timedelta
import time
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db_manager import DatabaseManager
from config import DOWNLOAD_DELAY


class EnhancedDataFetcher:
    def __init__(self):
        self.db = DatabaseManager()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def get_yfinance_symbol(self, symbol, exchange):
        """Convert symbol to yfinance format"""
        symbol = symbol.strip().upper()
        if exchange == 'NSE':
            return f"{symbol}.NS"
        elif exchange == 'BSE':
            return f"{symbol}.BO"
        return symbol

    def fetch_stock_fundamentals(self, symbol, exchange, progress_callback=None):
        """Fetch comprehensive fundamentals for a stock using yfinance"""
        yf_symbol = self.get_yfinance_symbol(symbol, exchange)

        try:
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info

            if not info or 'symbol' not in info:
                return None

            # Get market cap and categorize
            market_cap = info.get('marketCap', 0) or 0
            market_cap_cr = market_cap / 10000000  # Convert to Crores

            if market_cap_cr >= 100000:
                category = 'Large Cap'
            elif market_cap_cr >= 20000:
                category = 'Mid Cap'
            elif market_cap_cr >= 5000:
                category = 'Small Cap'
            else:
                category = 'Micro Cap'

            # Get current price for penny stock detection
            current_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            is_penny = 1 if current_price and current_price < 20 else 0

            fundamentals = {
                'market_cap': market_cap,
                'market_cap_category': category,
                'week_52_high': info.get('fiftyTwoWeekHigh'),
                'week_52_low': info.get('fiftyTwoWeekLow'),
                'face_value': info.get('faceValue'),
                'book_value': info.get('bookValue'),
                'pe_ratio': info.get('trailingPE'),
                'pb_ratio': info.get('priceToBook'),
                'dividend_yield': info.get('dividendYield'),
                'is_penny_stock': is_penny,
            }

            return fundamentals

        except Exception as e:
            if progress_callback:
                progress_callback(f"Error fetching fundamentals for {symbol}: {str(e)}")
            return None

    def fetch_nse_fno_stocks(self, progress_callback=None):
        """Fetch list of F&O stocks with lot sizes from NSE"""
        fno_stocks = {}

        try:
            # Try NSE F&O lot size API
            urls = [
                'https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O',
                'https://archives.nseindia.com/content/fo/fo_mktlots.csv',
            ]

            for url in urls:
                try:
                    if 'csv' in url:
                        response = self.session.get(url, timeout=30)
                        if response.status_code == 200:
                            lines = response.text.strip().split('\n')
                            for line in lines[1:]:  # Skip header
                                parts = line.split(',')
                                if len(parts) >= 3:
                                    symbol = parts[1].strip().replace('"', '')
                                    lot_size = int(parts[2].strip().replace('"', ''))
                                    fno_stocks[symbol] = lot_size
                            break
                    else:
                        response = self.session.get(url, timeout=30)
                        if response.status_code == 200:
                            data = response.json()
                            for stock in data.get('data', []):
                                symbol = stock.get('symbol', '').strip()
                                if symbol:
                                    fno_stocks[symbol] = stock.get('lotSize', 0)
                            break
                except Exception:
                    continue

            if progress_callback:
                progress_callback(f"Fetched {len(fno_stocks)} F&O stocks")

        except Exception as e:
            if progress_callback:
                progress_callback(f"Error fetching F&O stocks: {str(e)}")

        return fno_stocks

    def fetch_nse_delivery_data(self, symbol, progress_callback=None):
        """Fetch delivery percentage data from NSE"""
        try:
            # NSE delivery data API
            url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}&section=trade_info"

            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                trade_info = data.get('securityWiseDP', {})

                return {
                    'traded_qty': trade_info.get('quantityTraded'),
                    'deliverable_qty': trade_info.get('deliveryQuantity'),
                    'delivery_pct': trade_info.get('deliveryToTradedQuantity')
                }
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error fetching delivery data for {symbol}: {str(e)}")

        return None

    def fetch_bulk_block_deals(self, days=7, progress_callback=None):
        """Fetch bulk and block deals from NSE"""
        deals = []

        try:
            # Bulk deals
            bulk_url = "https://www.nseindia.com/api/snapshot-capital-market-largedeal"

            response = self.session.get(bulk_url, timeout=30)
            if response.status_code == 200:
                data = response.json()

                for deal in data.get('BULK_DEALS', []):
                    deals.append({
                        'symbol': deal.get('symbol'),
                        'date': deal.get('dealDate'),
                        'deal_type': 'BULK',
                        'client_name': deal.get('clientName'),
                        'buy_sell': deal.get('buySell'),
                        'quantity': deal.get('quantity'),
                        'price': deal.get('price')
                    })

                for deal in data.get('BLOCK_DEALS', []):
                    deals.append({
                        'symbol': deal.get('symbol'),
                        'date': deal.get('dealDate'),
                        'deal_type': 'BLOCK',
                        'client_name': deal.get('clientName'),
                        'buy_sell': deal.get('buySell'),
                        'quantity': deal.get('quantity'),
                        'price': deal.get('price')
                    })

            if progress_callback:
                progress_callback(f"Fetched {len(deals)} bulk/block deals")

        except Exception as e:
            if progress_callback:
                progress_callback(f"Error fetching bulk/block deals: {str(e)}")

        return deals

    def fetch_asm_gsm_list(self, progress_callback=None):
        """Fetch ASM/GSM/ESM stocks list"""
        asm_stocks = set()
        gsm_stocks = set()
        esm_stocks = set()

        try:
            # ASM stocks
            asm_url = "https://www.nseindia.com/api/reportASM"
            response = self.session.get(asm_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('data', []):
                    asm_stocks.add(item.get('symbol', '').strip())
        except Exception:
            pass

        try:
            # GSM stocks
            gsm_url = "https://www.nseindia.com/api/reportGSM"
            response = self.session.get(gsm_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('data', []):
                    gsm_stocks.add(item.get('symbol', '').strip())
        except Exception:
            pass

        try:
            # ESM stocks
            esm_url = "https://www.nseindia.com/api/reportESM"
            response = self.session.get(esm_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                for item in data.get('data', []):
                    esm_stocks.add(item.get('symbol', '').strip())
        except Exception:
            pass

        if progress_callback:
            progress_callback(f"ASM: {len(asm_stocks)}, GSM: {len(gsm_stocks)}, ESM: {len(esm_stocks)}")

        return {
            'asm': asm_stocks,
            'gsm': gsm_stocks,
            'esm': esm_stocks
        }

    def update_all_fundamentals(self, exchange=None, progress_callback=None):
        """Update fundamentals for all stocks"""
        stocks = self.db.get_all_stocks(exchange)
        total = len(stocks)

        if progress_callback:
            progress_callback(f"Updating fundamentals for {total} stocks...")

        # Fetch F&O stocks list
        fno_stocks = self.fetch_nse_fno_stocks(progress_callback)

        # Fetch ASM/GSM/ESM lists
        surveillance = self.fetch_asm_gsm_list(progress_callback)

        updated = 0
        errors = 0

        for i, stock in enumerate(stocks):
            try:
                symbol = stock['symbol']
                stock_exchange = stock['exchange']

                # Fetch fundamentals from yfinance
                fundamentals = self.fetch_stock_fundamentals(symbol, stock_exchange)

                if fundamentals:
                    # Add F&O info
                    if symbol in fno_stocks:
                        fundamentals['is_fno'] = 1
                        fundamentals['lot_size'] = fno_stocks[symbol]
                    else:
                        fundamentals['is_fno'] = 0
                        fundamentals['lot_size'] = None

                    # Add surveillance info
                    fundamentals['is_asm'] = 1 if symbol in surveillance['asm'] else 0
                    fundamentals['is_gsm'] = 1 if symbol in surveillance['gsm'] else 0
                    fundamentals['is_esm'] = 1 if symbol in surveillance['esm'] else 0

                    # Save to database
                    self.db.update_stock_fundamentals(stock['id'], fundamentals)
                    updated += 1
                else:
                    errors += 1

                if progress_callback and (i + 1) % 50 == 0:
                    progress_callback(f"Progress: {i + 1}/{total} ({updated} updated, {errors} errors)")

                time.sleep(DOWNLOAD_DELAY)

            except Exception as e:
                errors += 1
                if progress_callback:
                    progress_callback(f"Error updating {stock['symbol']}: {str(e)}")

        if progress_callback:
            progress_callback(f"Completed: {updated} updated, {errors} errors")

        return {'updated': updated, 'errors': errors, 'total': total}

    def update_delivery_data(self, exchange='NSE', progress_callback=None):
        """Update delivery data for NSE stocks"""
        stocks = self.db.get_all_stocks(exchange)
        total = len(stocks)

        if progress_callback:
            progress_callback(f"Updating delivery data for {total} stocks...")

        updated = 0
        errors = 0
        today = date.today().isoformat()

        for i, stock in enumerate(stocks):
            try:
                delivery = self.fetch_nse_delivery_data(stock['symbol'])

                if delivery and delivery.get('delivery_pct'):
                    self.db.add_delivery_data(
                        stock['id'],
                        today,
                        delivery.get('traded_qty'),
                        delivery.get('deliverable_qty'),
                        delivery.get('delivery_pct')
                    )
                    updated += 1

                if progress_callback and (i + 1) % 100 == 0:
                    progress_callback(f"Progress: {i + 1}/{total}")

                time.sleep(0.2)  # Rate limiting for NSE

            except Exception as e:
                errors += 1

        if progress_callback:
            progress_callback(f"Delivery data updated: {updated}/{total}")

        return {'updated': updated, 'errors': errors}

    def save_bulk_block_deals(self, progress_callback=None):
        """Save bulk and block deals to database"""
        deals = self.fetch_bulk_block_deals(progress_callback=progress_callback)
        saved = 0

        for deal in deals:
            try:
                stock = self.db.get_stock_by_symbol(deal['symbol'])
                if stock:
                    self.db.add_bulk_block_deal(
                        stock['id'],
                        deal['date'],
                        deal['deal_type'],
                        deal['client_name'],
                        deal['buy_sell'],
                        deal['quantity'],
                        deal['price']
                    )
                    saved += 1
            except Exception:
                continue

        if progress_callback:
            progress_callback(f"Saved {saved} deals")

        return {'saved': saved, 'total': len(deals)}


class EnhancedIndicatorCalculator:
    """Calculate extended technical indicators including EMA, Bollinger, Stochastic, ADX, etc."""

    def __init__(self):
        self.db = DatabaseManager()

    def calculate_ema(self, prices, period):
        """Calculate Exponential Moving Average"""
        return prices.ewm(span=period, adjust=False).mean()

    def calculate_bollinger_bands(self, prices, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower

    def calculate_stochastic(self, high, low, close, k_period=14, d_period=3):
        """Calculate Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()

        k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d = k.rolling(window=d_period).mean()

        return k, d

    def calculate_adx(self, high, low, close, period=14):
        """Calculate Average Directional Index"""
        plus_dm = high.diff()
        minus_dm = low.diff()

        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.ewm(span=period).mean() / atr)
        minus_di = abs(100 * (minus_dm.ewm(span=period).mean() / atr))

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    def calculate_obv(self, close, volume):
        """Calculate On-Balance Volume"""
        obv = [0]
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.append(obv[-1] + volume.iloc[i])
            elif close.iloc[i] < close.iloc[i-1]:
                obv.append(obv[-1] - volume.iloc[i])
            else:
                obv.append(obv[-1])
        return pd.Series(obv, index=close.index)

    def calculate_momentum_score(self, df):
        """Calculate a composite momentum score (0-100)"""
        scores = []

        for i in range(len(df)):
            score = 50  # Start neutral

            row = df.iloc[i]

            # RSI contribution (0-25)
            rsi = row.get('rsi_14', 50)
            if rsi > 70:
                score += 20
            elif rsi > 60:
                score += 15
            elif rsi > 50:
                score += 10
            elif rsi < 30:
                score -= 15
            elif rsi < 40:
                score -= 10

            # MACD contribution
            macd_hist = row.get('macd_histogram', 0)
            if macd_hist > 0:
                score += min(10, macd_hist * 5)
            else:
                score += max(-10, macd_hist * 5)

            # Price vs MAs
            close = row.get('close', 0)
            ma_20 = row.get('ma_20', close)
            ma_50 = row.get('ma_50', close)

            if close > ma_20:
                score += 5
            if close > ma_50:
                score += 5
            if ma_20 > ma_50:
                score += 5

            # Volume ratio
            vol_ratio = row.get('volume_ratio_20', 1)
            if vol_ratio > 2:
                score += 5
            elif vol_ratio > 1.5:
                score += 3

            scores.append(max(0, min(100, score)))

        return scores

    def calculate_all_extended_indicators(self, df):
        """Calculate all extended indicators for a DataFrame"""
        result = df.copy()

        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']

        # EMAs
        result['ema_9'] = self.calculate_ema(close, 9)
        result['ema_21'] = self.calculate_ema(close, 21)
        result['ema_50'] = self.calculate_ema(close, 50)
        result['ema_200'] = self.calculate_ema(close, 200)
        result['sma_200'] = close.rolling(window=200).mean()

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(close)
        result['bollinger_upper'] = bb_upper
        result['bollinger_middle'] = bb_middle
        result['bollinger_lower'] = bb_lower

        # Stochastic
        stoch_k, stoch_d = self.calculate_stochastic(high, low, close)
        result['stochastic_k'] = stoch_k
        result['stochastic_d'] = stoch_d

        # ADX
        result['adx_14'] = self.calculate_adx(high, low, close)

        # OBV
        result['obv'] = self.calculate_obv(close, volume)

        # VWAP (simplified - daily)
        result['vwap'] = (volume * (high + low + close) / 3).cumsum() / volume.cumsum()

        # 52-week distances
        week_52_high = close.rolling(window=252).max()
        week_52_low = close.rolling(window=252).min()
        result['distance_from_52w_high'] = ((close - week_52_high) / week_52_high * 100)
        result['distance_from_52w_low'] = ((close - week_52_low) / week_52_low * 100)

        return result

    def calculate_and_save_for_stock(self, stock_id, progress_callback=None):
        """Calculate and save extended indicators for a single stock"""
        # Get OHLCV data
        ohlcv_df = self.db.get_ohlcv_data(stock_id)

        if ohlcv_df.empty or len(ohlcv_df) < 50:
            return False

        # Get basic indicators for momentum score
        indicators_df = self.db.get_indicators(stock_id)

        # Calculate extended indicators
        result = self.calculate_all_extended_indicators(ohlcv_df)

        # Merge with basic indicators for momentum score
        if not indicators_df.empty:
            merged = result.merge(indicators_df[['date', 'rsi_14', 'macd_histogram', 'ma_20', 'ma_50', 'volume_ratio_20']],
                                on='date', how='left', suffixes=('', '_ind'))
            result['momentum_score'] = self.calculate_momentum_score(merged)
        else:
            result['momentum_score'] = 50

        # Remove rows with insufficient data
        result = result.dropna(subset=['ema_200', 'sma_200'])

        if result.empty:
            return False

        # Save to database
        self.db.add_extended_indicators(stock_id, result)

        return True

    def calculate_for_all_stocks(self, exchange=None, progress_callback=None):
        """Calculate extended indicators for all stocks"""
        stocks = self.db.get_all_stocks(exchange)
        total = len(stocks)

        if progress_callback:
            progress_callback(f"Calculating extended indicators for {total} stocks...")

        calculated = 0
        errors = 0

        for i, stock in enumerate(stocks):
            try:
                if self.calculate_and_save_for_stock(stock['id']):
                    calculated += 1
                else:
                    errors += 1

                if progress_callback and (i + 1) % 100 == 0:
                    progress_callback(f"Progress: {i + 1}/{total}")

            except Exception as e:
                errors += 1

        # Calculate momentum ranks
        self._update_momentum_ranks(exchange)

        if progress_callback:
            progress_callback(f"Completed: {calculated} calculated, {errors} errors")

        return {'calculated': calculated, 'errors': errors}

    def _update_momentum_ranks(self, exchange=None):
        """Update momentum ranks for all stocks"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get latest momentum scores
        query = '''
            SELECT ei.id, ei.stock_id, ei.momentum_score
            FROM extended_indicators ei
            WHERE ei.date = (SELECT MAX(date) FROM extended_indicators WHERE stock_id = ei.stock_id)
        '''

        if exchange:
            query = '''
                SELECT ei.id, ei.stock_id, ei.momentum_score
                FROM extended_indicators ei
                JOIN stocks s ON ei.stock_id = s.id
                WHERE ei.date = (SELECT MAX(date) FROM extended_indicators WHERE stock_id = ei.stock_id)
                AND s.exchange = ?
            '''
            cursor.execute(query, (exchange,))
        else:
            cursor.execute(query)

        rows = cursor.fetchall()

        # Sort by momentum score and assign ranks
        sorted_rows = sorted(rows, key=lambda x: x[2] if x[2] else 0, reverse=True)

        for rank, row in enumerate(sorted_rows, 1):
            cursor.execute('''
                UPDATE extended_indicators
                SET momentum_rank = ?
                WHERE id = ?
            ''', (rank, row[0]))

        conn.commit()
        conn.close()


if __name__ == '__main__':
    # Test the enhanced fetcher
    fetcher = EnhancedDataFetcher()

    def print_progress(msg):
        print(msg)

    print("Testing Enhanced Data Fetcher...")

    # Test F&O stocks fetch
    fno = fetcher.fetch_nse_fno_stocks(print_progress)
    print(f"F&O stocks: {len(fno)}")

    # Test ASM/GSM/ESM fetch
    surveillance = fetcher.fetch_asm_gsm_list(print_progress)
    print(f"Surveillance stocks fetched")

    print("Enhanced Data Fetcher initialized successfully!")
