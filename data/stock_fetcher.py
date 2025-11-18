"""
Stock List Fetcher for NSE and BSE
Downloads complete equity lists from both exchanges with multiple fallback methods
"""
import requests
import pandas as pd
import os
import sys
import json
import io
import zipfile
from datetime import datetime, timedelta
import time
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR
from database.db_manager import DatabaseManager


class StockFetcher:
    def __init__(self):
        self.db = DatabaseManager()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def _retry_request(self, url, max_retries=3, timeout=30, **kwargs):
        """Make request with retry logic and exponential backoff"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5
                    print(f"  Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise
        return None

    def fetch_nse_stocks(self):
        """Fetch all NSE equity stocks (~2400+ stocks)"""
        print("=" * 50)
        print("Fetching NSE stock list...")
        print("=" * 50)
        stocks = []
        existing_symbols = set()

        # Initialize NSE session with cookies
        try:
            print("Initializing NSE session...")
            self.session.get("https://www.nseindia.com", timeout=10)
            time.sleep(1)
        except Exception as e:
            print(f"Warning: Could not initialize NSE session: {e}")

        # Method 1: NSE EQUITY_L.csv from archives (most complete)
        print("\nMethod 1: NSE Archives EQUITY_L.csv")
        try:
            url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
            response = self._retry_request(url, timeout=30)

            if response and response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))

                for _, row in df.iterrows():
                    symbol = str(row.get('SYMBOL', '')).strip()
                    if symbol and symbol not in existing_symbols:
                        stocks.append({
                            'symbol': symbol,
                            'name': str(row.get('NAME OF COMPANY', symbol)).strip(),
                            'exchange': 'NSE',
                            'sector': str(row.get('SERIES', '')).strip(),
                            'industry': ''
                        })
                        existing_symbols.add(symbol)

                print(f"  -> Found {len(stocks)} stocks")
        except Exception as e:
            print(f"  -> Failed: {e}")

        # Method 2: NSE Total Market Index API
        print("\nMethod 2: NSE Total Market Index API")
        try:
            url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    count = 0
                    for item in data['data']:
                        symbol = item.get('symbol', '')
                        if symbol and symbol not in existing_symbols:
                            stocks.append({
                                'symbol': symbol,
                                'name': item.get('companyName', symbol),
                                'exchange': 'NSE',
                                'sector': item.get('industry', ''),
                                'industry': item.get('industry', '')
                            })
                            existing_symbols.add(symbol)
                            count += 1
                    print(f"  -> Added {count} new stocks")
        except Exception as e:
            print(f"  -> Failed: {e}")

        # Method 3: Multiple Index Endpoints
        print("\nMethod 3: Multiple NSE Indices")
        indices = [
            ("NIFTY%20500", "Nifty 500"),
            ("NIFTY%20MIDCAP%20150", "Midcap 150"),
            ("NIFTY%20SMALLCAP%20250", "Smallcap 250"),
            ("NIFTY%20MICROCAP%20250", "Microcap 250"),
        ]

        for index_code, index_name in indices:
            try:
                url = f"https://www.nseindia.com/api/equity-stockIndices?index={index_code}"
                response = self.session.get(url, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        count = 0
                        for item in data['data']:
                            symbol = item.get('symbol', '')
                            if symbol and symbol not in existing_symbols:
                                stocks.append({
                                    'symbol': symbol,
                                    'name': item.get('companyName', symbol),
                                    'exchange': 'NSE',
                                    'sector': item.get('industry', ''),
                                    'industry': item.get('industry', '')
                                })
                                existing_symbols.add(symbol)
                                count += 1
                        if count > 0:
                            print(f"  -> {index_name}: Added {count} new stocks")
                time.sleep(0.3)
            except:
                continue

        print(f"\n{'='*50}")
        print(f"Total NSE stocks found: {len(stocks)}")
        print(f"{'='*50}")
        return stocks

    def fetch_bse_stocks(self):
        """Fetch all BSE equity stocks (~4000+ stocks)"""
        print("\n" + "=" * 50)
        print("Fetching BSE stock list...")
        print("=" * 50)
        stocks = []
        existing_symbols = set()

        # Method 1: BSE Bhav Copy CSV (most reliable source)
        print("\nMethod 1: BSE Equity Bhav Copy")
        try:
            today = datetime.now()

            # Try last 10 business days to find a valid bhav copy
            for days_back in range(1, 15):
                check_date = today - timedelta(days=days_back)

                # Skip weekends
                if check_date.weekday() >= 5:
                    continue

                date_str = check_date.strftime('%d%m%y')

                url = f"https://www.bseindia.com/download/BhavCopy/Equity/EQ{date_str}_CSV.ZIP"

                try:
                    response = self.session.get(url, timeout=30)
                    if response.status_code == 200 and len(response.content) > 1000:
                        # Extract and parse the CSV from ZIP
                        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                            for filename in z.namelist():
                                if filename.upper().endswith('.CSV'):
                                    with z.open(filename) as f:
                                        df = pd.read_csv(f)

                                        # Find the scrip code column
                                        code_col = None
                                        name_col = None

                                        for col in df.columns:
                                            col_upper = col.upper().strip()
                                            if 'SC_CODE' in col_upper:
                                                code_col = col
                                            elif 'SC_NAME' in col_upper:
                                                name_col = col

                                        if code_col:
                                            for _, row in df.iterrows():
                                                scrip_cd = str(row.get(code_col, '')).strip()
                                                # BSE codes are numeric
                                                if scrip_cd and scrip_cd.replace('.0', '').isdigit():
                                                    scrip_cd = scrip_cd.replace('.0', '')
                                                    if scrip_cd not in existing_symbols:
                                                        name = str(row.get(name_col, scrip_cd)).strip() if name_col else scrip_cd
                                                        stocks.append({
                                                            'symbol': scrip_cd,
                                                            'name': name,
                                                            'exchange': 'BSE',
                                                            'sector': '',
                                                            'industry': ''
                                                        })
                                                        existing_symbols.add(scrip_cd)
                                            break

                        if stocks:
                            print(f"  -> Found {len(stocks)} stocks from {check_date.strftime('%Y-%m-%d')}")
                            break
                except Exception as inner_e:
                    continue

        except Exception as e:
            print(f"  -> Failed: {e}")

        # Method 2: BSE API with browser-like session
        if len(stocks) < 100:
            print("\nMethod 2: BSE API")
            try:
                # Create a new session with browser-like behavior
                bse_session = requests.Session()

                # First visit the main page to get cookies
                bse_session.get("https://www.bseindia.com/", timeout=10)
                time.sleep(1)

                url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
                params = {
                    'Group': '',
                    'Atea': '',
                    'Status': 'Active'
                }

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.bseindia.com/',
                    'Origin': 'https://www.bseindia.com',
                }

                response = bse_session.get(url, params=params, headers=headers, timeout=60)

                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            count = 0
                            for item in data:
                                scrip_cd = str(item.get('scrip_cd', '')).strip()
                                if scrip_cd and scrip_cd not in existing_symbols:
                                    stocks.append({
                                        'symbol': scrip_cd,
                                        'name': str(item.get('scrip_nm', scrip_cd)).strip(),
                                        'exchange': 'BSE',
                                        'sector': str(item.get('group', '')).strip(),
                                        'industry': str(item.get('industry', '')).strip()
                                    })
                                    existing_symbols.add(scrip_cd)
                                    count += 1

                            if count > 0:
                                print(f"  -> Added {count} stocks")
                    except json.JSONDecodeError:
                        print("  -> API returned non-JSON response")
            except Exception as e:
                print(f"  -> Failed: {e}")

        # Method 3: BSE Group-wise fetching
        if len(stocks) < 1000:
            print("\nMethod 3: BSE Group-wise Fetching")
            groups = ['A', 'B', 'T', 'S', 'M', 'Z', 'X', 'XT']

            bse_session = requests.Session()
            bse_session.get("https://www.bseindia.com/", timeout=10)

            for group in groups:
                try:
                    url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
                    params = {
                        'Group': group,
                        'Atea': '',
                        'Status': 'Active'
                    }

                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/json',
                        'Referer': 'https://www.bseindia.com/',
                    }

                    response = bse_session.get(url, params=params, headers=headers, timeout=30)

                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if isinstance(data, list):
                                count = 0
                                for item in data:
                                    scrip_cd = str(item.get('scrip_cd', '')).strip()
                                    if scrip_cd and scrip_cd not in existing_symbols:
                                        stocks.append({
                                            'symbol': scrip_cd,
                                            'name': str(item.get('scrip_nm', scrip_cd)).strip(),
                                            'exchange': 'BSE',
                                            'sector': group,
                                            'industry': ''
                                        })
                                        existing_symbols.add(scrip_cd)
                                        count += 1
                                if count > 0:
                                    print(f"  -> Group {group}: Added {count} stocks")
                        except json.JSONDecodeError:
                            pass
                    time.sleep(0.3)
                except:
                    continue

        print(f"\n{'='*50}")
        print(f"Total BSE stocks found: {len(stocks)}")
        print(f"{'='*50}")
        return stocks

    def save_stocks_to_db(self, stocks):
        """Save stocks to database"""
        saved_count = 0

        for stock in stocks:
            try:
                self.db.add_stock(
                    symbol=stock['symbol'],
                    name=stock['name'],
                    exchange=stock['exchange'],
                    sector=stock.get('sector', ''),
                    industry=stock.get('industry', '')
                )
                saved_count += 1
            except Exception:
                pass  # Ignore duplicates

        return saved_count

    def fetch_and_save_all(self):
        """Fetch and save stocks from both NSE and BSE"""
        results = {
            'nse': 0,
            'bse': 0,
            'total': 0
        }

        # Fetch NSE stocks
        nse_stocks = self.fetch_nse_stocks()
        results['nse'] = self.save_stocks_to_db(nse_stocks)
        print(f"\nSaved {results['nse']} NSE stocks to database")

        # Fetch BSE stocks
        bse_stocks = self.fetch_bse_stocks()
        results['bse'] = self.save_stocks_to_db(bse_stocks)
        print(f"Saved {results['bse']} BSE stocks to database")

        results['total'] = results['nse'] + results['bse']

        print(f"\n{'='*50}")
        print(f"FETCH COMPLETE")
        print(f"{'='*50}")
        print(f"Total stocks saved: {results['total']}")
        print(f"  NSE: {results['nse']}")
        print(f"  BSE: {results['bse']}")
        print(f"{'='*50}\n")

        return results


if __name__ == '__main__':
    fetcher = StockFetcher()
    results = fetcher.fetch_and_save_all()
