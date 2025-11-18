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
                    wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
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
            ("NIFTY%20NEXT%2050", "Next 50"),
            ("NIFTY%20100", "Nifty 100"),
            ("NIFTY%20200", "Nifty 200"),
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
            except Exception as e:
                continue

        # Method 4: Pre-open Market Data
        print("\nMethod 4: NSE Pre-open Market")
        try:
            url = "https://www.nseindia.com/api/market-data-pre-open?key=ALL"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    count = 0
                    for item in data['data']:
                        metadata = item.get('metadata', {})
                        symbol = metadata.get('symbol', '')
                        if symbol and symbol not in existing_symbols:
                            stocks.append({
                                'symbol': symbol,
                                'name': metadata.get('companyName', symbol),
                                'exchange': 'NSE',
                                'sector': metadata.get('industry', ''),
                                'industry': metadata.get('industry', '')
                            })
                            existing_symbols.add(symbol)
                            count += 1
                    print(f"  -> Added {count} new stocks")
        except Exception as e:
            print(f"  -> Failed: {e}")

        # Method 5: Securities available for trading
        print("\nMethod 5: NSE Securities List")
        try:
            url = "https://www.nseindia.com/api/market-data-pre-open?key=FO"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    count = 0
                    for item in data['data']:
                        metadata = item.get('metadata', {})
                        symbol = metadata.get('symbol', '')
                        if symbol and symbol not in existing_symbols:
                            stocks.append({
                                'symbol': symbol,
                                'name': metadata.get('companyName', symbol),
                                'exchange': 'NSE',
                                'sector': metadata.get('industry', ''),
                                'industry': metadata.get('industry', '')
                            })
                            existing_symbols.add(symbol)
                            count += 1
                    print(f"  -> Added {count} new stocks")
        except Exception as e:
            print(f"  -> Failed: {e}")

        print(f"\n{'='*50}")
        print(f"Total NSE stocks found: {len(stocks)}")
        print(f"{'='*50}")
        return stocks

    def fetch_bse_stocks(self):
        """Fetch all BSE equity stocks (~5000+ stocks)"""
        print("\n" + "=" * 50)
        print("Fetching BSE stock list...")
        print("=" * 50)
        stocks = []
        existing_symbols = set()

        # Method 1: BSE Bhav Copy CSV (most reliable)
        print("\nMethod 1: BSE Equity Bhav Copy")
        try:
            # Get yesterday's date for bhav copy
            from datetime import datetime, timedelta
            today = datetime.now()

            # Try last few days to find a valid bhav copy
            for days_back in range(1, 10):
                check_date = today - timedelta(days=days_back)
                date_str = check_date.strftime('%d%m%y')

                url = f"https://www.bseindia.com/download/BhsrAll/Equity/EQ{date_str}_CSV.ZIP"

                try:
                    response = self.session.get(url, timeout=30)
                    if response.status_code == 200 and len(response.content) > 1000:
                        # Extract and parse the CSV from ZIP
                        import zipfile
                        from io import BytesIO

                        with zipfile.ZipFile(BytesIO(response.content)) as z:
                            for filename in z.namelist():
                                if filename.endswith('.CSV') or filename.endswith('.csv'):
                                    with z.open(filename) as f:
                                        df = pd.read_csv(f)

                                        # Common column names in BSE bhav copy
                                        code_col = None
                                        name_col = None

                                        for col in df.columns:
                                            col_upper = col.upper().strip()
                                            if 'SC_CODE' in col_upper or 'SCRIP' in col_upper and 'CODE' in col_upper:
                                                code_col = col
                                            elif 'SC_NAME' in col_upper or 'SCRIP' in col_upper and 'NAME' in col_upper:
                                                name_col = col

                                        if code_col:
                                            for _, row in df.iterrows():
                                                scrip_cd = str(row.get(code_col, '')).strip()
                                                if scrip_cd and scrip_cd.isdigit() and scrip_cd not in existing_symbols:
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

        # Method 2: Try direct equity list from BSE downloads
        if len(stocks) < 100:
            print("\nMethod 2: BSE Equity List Download")
            try:
                url = "https://www.bseindia.com/corporates/List_Scrips.aspx"

                # First get the page to extract form data
                response = self.session.get(url, timeout=30)

                if response.status_code == 200:
                    # Try to download the excel/csv directly
                    download_url = "https://www.bseindia.com/corporates/download/Equity.csv"
                    dl_response = self.session.get(download_url, timeout=60)

                    if dl_response.status_code == 200:
                        try:
                            df = pd.read_csv(io.StringIO(dl_response.text))
                            count = 0

                            for col in df.columns:
                                if 'Security Code' in col or 'Scrip Code' in col:
                                    code_col = col
                                    break
                            else:
                                code_col = df.columns[0] if len(df.columns) > 0 else None

                            if code_col:
                                name_col = df.columns[1] if len(df.columns) > 1 else None

                                for _, row in df.iterrows():
                                    scrip_cd = str(row.get(code_col, '')).strip()
                                    if scrip_cd and scrip_cd not in existing_symbols:
                                        name = str(row.get(name_col, scrip_cd)).strip() if name_col else scrip_cd
                                        stocks.append({
                                            'symbol': scrip_cd,
                                            'name': name,
                                            'exchange': 'BSE',
                                            'sector': '',
                                            'industry': ''
                                        })
                                        existing_symbols.add(scrip_cd)
                                        count += 1

                                if count > 0:
                                    print(f"  -> Added {count} stocks")
                        except:
                            pass
            except Exception as e:
                print(f"  -> Failed: {e}")

        # Method 3: BSE API with browser-like session
        if len(stocks) < 100:
            print("\nMethod 3: BSE API with enhanced headers")
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
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://www.bseindia.com/',
                    'Origin': 'https://www.bseindia.com',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-site',
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
                    except:
                        pass
            except Exception as e:
                print(f"  -> Failed: {e}")

        # Method 2: BSE Group-wise fetching
        print("\nMethod 2: BSE Group-wise Fetching")
        groups = ['A', 'B', 'T', 'S', 'M', 'MT', 'TS', 'P', 'Z', 'X', 'XT', 'XD', 'XC', 'Y', 'IF', 'IP', 'ID', 'IT']

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

                response = self.session.get(url, params=params, headers=headers, timeout=30)

                if response.status_code == 200:
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
                                    'industry': str(item.get('industry', '')).strip()
                                })
                                existing_symbols.add(scrip_cd)
                                count += 1
                        if count > 0:
                            print(f"  -> Group {group}: Added {count} stocks")
                time.sleep(0.2)
            except Exception as e:
                continue

        # Method 3: BSE Corporate List
        print("\nMethod 3: BSE Corporate List API")
        try:
            url = "https://api.bseindia.com/BseIndiaAPI/api/GetScripHeaderData/w"
            params = {
                'Fession': 'Equity',
                'scripcode': '',
                'Status': 'Active'
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Referer': 'https://www.bseindia.com/',
            }

            response = self.session.get(url, params=params, headers=headers, timeout=60)

            if response.status_code == 200:
                data = response.json()
                count = 0

                # Handle different response structures
                if isinstance(data, dict) and 'Table' in data:
                    items = data['Table']
                elif isinstance(data, list):
                    items = data
                else:
                    items = []

                for item in items:
                    scrip_cd = str(item.get('SCRIP_CD', item.get('scrip_cd', ''))).strip()
                    if scrip_cd and scrip_cd not in existing_symbols:
                        stocks.append({
                            'symbol': scrip_cd,
                            'name': str(item.get('scrip_nm', item.get('SCRIP_NM', scrip_cd))).strip(),
                            'exchange': 'BSE',
                            'sector': '',
                            'industry': ''
                        })
                        existing_symbols.add(scrip_cd)
                        count += 1

                if count > 0:
                    print(f"  -> Added {count} new stocks")
        except Exception as e:
            print(f"  -> Failed: {e}")

        # Method 4: BSE Direct equity file
        print("\nMethod 4: BSE Equity Scrip Master")
        try:
            # Try to get BSE equity master file
            today = datetime.now()
            date_str = today.strftime('%d%m%y')

            url = f"https://www.bseindia.com/downloads/Help/file/Equity%20Scrip%20Master.csv"
            response = self.session.get(url, timeout=60)

            if response.status_code == 200:
                try:
                    df = pd.read_csv(io.StringIO(response.text))
                    count = 0

                    # Try different column names
                    symbol_col = None
                    name_col = None

                    for col in df.columns:
                        col_lower = col.lower()
                        if 'scrip' in col_lower and 'code' in col_lower:
                            symbol_col = col
                        elif 'scrip' in col_lower and 'name' in col_lower:
                            name_col = col
                        elif 'security' in col_lower and 'code' in col_lower:
                            symbol_col = col
                        elif 'security' in col_lower and 'name' in col_lower:
                            name_col = col

                    if symbol_col:
                        for _, row in df.iterrows():
                            scrip_cd = str(row.get(symbol_col, '')).strip()
                            if scrip_cd and scrip_cd not in existing_symbols:
                                name = str(row.get(name_col, scrip_cd)).strip() if name_col else scrip_cd
                                stocks.append({
                                    'symbol': scrip_cd,
                                    'name': name,
                                    'exchange': 'BSE',
                                    'sector': '',
                                    'industry': ''
                                })
                                existing_symbols.add(scrip_cd)
                                count += 1

                        if count > 0:
                            print(f"  -> Added {count} new stocks")
                except Exception as parse_error:
                    print(f"  -> Parse failed: {parse_error}")
        except Exception as e:
            print(f"  -> Failed: {e}")

        # Method 5: Alternative BSE endpoint
        print("\nMethod 5: BSE Alternative Endpoint")
        try:
            url = "https://api.bseindia.com/BseIndiaAPI/api/ddlIndustry/w"
            params = {'Group': ''}

            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                industries = data if isinstance(data, list) else []

                # Fetch stocks by industry
                count = 0
                for industry in industries[:50]:  # Limit to avoid too many requests
                    try:
                        ind_name = industry.get('industry', '') if isinstance(industry, dict) else str(industry)
                        if not ind_name:
                            continue

                        url2 = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
                        params2 = {
                            'Group': '',
                            'Atea': ind_name,
                            'Status': 'Active'
                        }

                        response2 = self.session.get(url2, params=params2, timeout=30)

                        if response2.status_code == 200:
                            data2 = response2.json()
                            if isinstance(data2, list):
                                for item in data2:
                                    scrip_cd = str(item.get('scrip_cd', '')).strip()
                                    if scrip_cd and scrip_cd not in existing_symbols:
                                        stocks.append({
                                            'symbol': scrip_cd,
                                            'name': str(item.get('scrip_nm', scrip_cd)).strip(),
                                            'exchange': 'BSE',
                                            'sector': ind_name,
                                            'industry': ind_name
                                        })
                                        existing_symbols.add(scrip_cd)
                                        count += 1
                        time.sleep(0.1)
                    except:
                        continue

                if count > 0:
                    print(f"  -> Added {count} stocks by industry")
        except Exception as e:
            print(f"  -> Failed: {e}")

        print(f"\n{'='*50}")
        print(f"Total BSE stocks found: {len(stocks)}")
        print(f"{'='*50}")
        return stocks

    def save_stocks_to_db(self, stocks):
        """Save stocks to database with batch processing"""
        saved_count = 0
        skipped_count = 0

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
            except Exception as e:
                skipped_count += 1  # Likely duplicate

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
