"""
OHLCV Data Downloader
Downloads historical price data for stocks with resume capability
"""
import yfinance as yf
import pandas as pd
import os
import sys
import time
from datetime import datetime, timedelta
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DOWNLOAD_HISTORY_DAYS, DOWNLOAD_BATCH_SIZE, DOWNLOAD_DELAY
from database.db_manager import DatabaseManager


class OHLCVDownloader:
    def __init__(self):
        self.db = DatabaseManager()

    def get_yfinance_symbol(self, symbol, exchange):
        """Convert symbol to yfinance format"""
        if exchange == 'NSE':
            return f"{symbol}.NS"
        elif exchange == 'BSE':
            return f"{symbol}.BO"
        return symbol

    def download_stock_data(self, stock, start_date=None, end_date=None):
        """Download OHLCV data for a single stock"""
        symbol = stock['symbol']
        exchange = stock['exchange']
        stock_id = stock['id']

        # Get yfinance symbol
        yf_symbol = self.get_yfinance_symbol(symbol, exchange)

        # Set date range
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            # Check if we have existing data
            latest_date = self.db.get_latest_ohlcv_date(stock_id)
            if latest_date:
                start_date = datetime.strptime(latest_date, '%Y-%m-%d') + timedelta(days=1)
            else:
                start_date = end_date - timedelta(days=DOWNLOAD_HISTORY_DAYS)

        # Don't download if we're up to date
        if start_date >= end_date:
            return {'status': 'up_to_date', 'rows': 0}

        try:
            # Download data
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(start=start_date, end=end_date)

            if df.empty:
                return {'status': 'no_data', 'rows': 0}

            # Prepare data for database
            df = df.reset_index()
            df.columns = [col.lower() for col in df.columns]

            # Rename columns to match our schema
            df = df.rename(columns={
                'date': 'date',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })

            # Convert date to string format
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')

            # Keep only required columns
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            df = df[[col for col in required_cols if col in df.columns]]

            # Save to database
            self.db.add_ohlcv_data(stock_id, df)

            return {'status': 'success', 'rows': len(df)}

        except Exception as e:
            return {'status': 'error', 'error': str(e), 'rows': 0}

    def download_all_stocks(self, exchange=None, progress_callback=None):
        """Download data for all stocks with resume capability"""
        # Get pending downloads
        if exchange:
            stocks = self.db.get_all_stocks(exchange=exchange)
        else:
            stocks = self.db.get_pending_downloads()

        if not stocks:
            # If no pending, get all stocks
            stocks = self.db.get_all_stocks(exchange=exchange)

        total = len(stocks)
        results = {
            'total': total,
            'success': 0,
            'errors': 0,
            'up_to_date': 0,
            'no_data': 0
        }

        print(f"Downloading data for {total} stocks...")

        # Process stocks with progress bar
        for i, stock in enumerate(tqdm(stocks, desc="Downloading")):
            result = self.download_stock_data(stock)

            # Update progress tracking
            if result['status'] == 'success':
                results['success'] += 1
                self.db.update_download_progress(stock['id'], 'completed')
            elif result['status'] == 'error':
                results['errors'] += 1
                self.db.update_download_progress(stock['id'], 'error', result.get('error', ''))
            elif result['status'] == 'up_to_date':
                results['up_to_date'] += 1
                self.db.update_download_progress(stock['id'], 'completed')
            elif result['status'] == 'no_data':
                results['no_data'] += 1
                self.db.update_download_progress(stock['id'], 'no_data')

            # Call progress callback if provided
            if progress_callback:
                progress_callback({
                    'current': i + 1,
                    'total': total,
                    'symbol': stock['symbol'],
                    'status': result['status']
                })

            # Delay between downloads to avoid rate limiting
            if (i + 1) % DOWNLOAD_BATCH_SIZE == 0:
                time.sleep(DOWNLOAD_DELAY)

        return results

    def update_all_stocks(self):
        """Update data for all stocks (incremental update)"""
        stocks = self.db.get_all_stocks()
        return self.download_all_stocks_list(stocks)

    def download_all_stocks_list(self, stocks):
        """Download data for a list of stocks"""
        total = len(stocks)
        results = {
            'total': total,
            'success': 0,
            'errors': 0,
            'up_to_date': 0,
            'no_data': 0
        }

        for stock in tqdm(stocks, desc="Updating"):
            result = self.download_stock_data(stock)

            if result['status'] == 'success':
                results['success'] += 1
            elif result['status'] == 'error':
                results['errors'] += 1
            elif result['status'] == 'up_to_date':
                results['up_to_date'] += 1
            elif result['status'] == 'no_data':
                results['no_data'] += 1

            time.sleep(0.5)  # Small delay

        return results

    def download_single_stock(self, symbol):
        """Download data for a single stock by symbol"""
        stock = self.db.get_stock_by_symbol(symbol)
        if not stock:
            return {'status': 'error', 'error': f'Stock {symbol} not found'}

        return self.download_stock_data(stock)


# Create __init__.py for data module
if __name__ == '__main__':
    downloader = OHLCVDownloader()

    # Example: Download data for all stocks
    results = downloader.download_all_stocks()
    print(f"\nDownload Results:")
    print(f"  Total: {results['total']}")
    print(f"  Success: {results['success']}")
    print(f"  Errors: {results['errors']}")
    print(f"  Up to date: {results['up_to_date']}")
    print(f"  No data: {results['no_data']}")
