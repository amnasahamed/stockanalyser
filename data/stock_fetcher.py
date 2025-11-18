"""
Stock List Fetcher for NSE and BSE
Downloads complete equity lists from both exchanges
"""
import requests
import pandas as pd
import os
import sys
import json
import io
from datetime import datetime
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR
from database.db_manager import DatabaseManager


class StockFetcher:
    def __init__(self):
        self.db = DatabaseManager()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def fetch_nse_stocks(self):
        """Fetch all NSE equity stocks (~2000+ stocks)"""
        print("Fetching NSE stock list...")
        stocks = []

        # Method 1: NSE India - Complete equity list CSV
        try:
            # First get cookies from main site
            self.session.get("https://www.nseindia.com", timeout=10)
            time.sleep(1)

            # Get all equity stocks
            url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET"
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    for item in data['data']:
                        symbol = item.get('symbol', '')
                        if symbol:
                            stocks.append({
                                'symbol': symbol,
                                'name': item.get('companyName', symbol),
                                'exchange': 'NSE',
                                'sector': item.get('industry', ''),
                                'industry': item.get('industry', '')
                            })
            print(f"Method 1 (Total Market): {len(stocks)} stocks")
        except Exception as e:
            print(f"NSE Total Market failed: {e}")

        # Method 2: Try multiple index endpoints to get more stocks
        if len(stocks) < 500:
            try:
                indices = [
                    "NIFTY%20500",
                    "NIFTY%20MIDCAP%20150",
                    "NIFTY%20SMALLCAP%20250",
                    "NIFTY%20MICROCAP%20250"
                ]

                existing_symbols = {s['symbol'] for s in stocks}

                for index in indices:
                    url = f"https://www.nseindia.com/api/equity-stockIndices?index={index}"
                    try:
                        response = self.session.get(url, timeout=30)
                        if response.status_code == 200:
                            data = response.json()
                            if 'data' in data:
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
                        time.sleep(0.5)
                    except:
                        continue

                print(f"Method 2 (Multiple indices): {len(stocks)} stocks")
            except Exception as e:
                print(f"NSE indices method failed: {e}")

        # Method 3: Download from NSE archives - complete list
        if len(stocks) < 1000:
            try:
                # NSE equity list from archives
                url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
                response = self.session.get(url, timeout=30)

                if response.status_code == 200:
                    df = pd.read_csv(io.StringIO(response.text))
                    existing_symbols = {s['symbol'] for s in stocks}

                    for _, row in df.iterrows():
                        symbol = str(row.get('SYMBOL', '')).strip()
                        if symbol and symbol not in existing_symbols:
                            stocks.append({
                                'symbol': symbol,
                                'name': str(row.get('NAME OF COMPANY', symbol)).strip(),
                                'exchange': 'NSE',
                                'sector': '',
                                'industry': ''
                            })
                            existing_symbols.add(symbol)

                print(f"Method 3 (Archives): {len(stocks)} stocks")
            except Exception as e:
                print(f"NSE archives method failed: {e}")

        # Method 4: Alternative NSE source
        if len(stocks) < 1500:
            try:
                url = "https://www.nseindia.com/api/market-data-pre-open?key=ALL"
                response = self.session.get(url, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    existing_symbols = {s['symbol'] for s in stocks}

                    if 'data' in data:
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

                print(f"Method 4 (Pre-open): {len(stocks)} stocks")
            except Exception as e:
                print(f"NSE pre-open method failed: {e}")

        print(f"Total NSE stocks found: {len(stocks)}")
        return stocks

    def fetch_bse_stocks(self):
        """Fetch all BSE equity stocks (~5000+ stocks)"""
        print("Fetching BSE stock list...")
        stocks = []

        # Method 1: BSE API - All active scripts
        try:
            url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
            params = {'Group': '', 'Atea': '', 'Status': 'Active'}

            response = self.session.get(url, params=params, timeout=60)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    for item in data:
                        scrip_cd = str(item.get('scrip_cd', '')).strip()
                        if scrip_cd:
                            stocks.append({
                                'symbol': scrip_cd,
                                'name': str(item.get('scrip_nm', scrip_cd)).strip(),
                                'exchange': 'BSE',
                                'sector': str(item.get('group', '')).strip(),
                                'industry': ''
                            })

            print(f"Method 1 (BSE API): {len(stocks)} stocks")
        except Exception as e:
            print(f"BSE API method failed: {e}")

        # Method 2: BSE Bhav copy approach - get from equity list
        if len(stocks) < 3000:
            try:
                url = "https://api.bseindia.com/BseIndiaAPI/api/GetScripHeaderData/w"
                params = {'Atea': '', 'Group': '', 'index': '', 'status': 'Active', 'industry': ''}

                response = self.session.get(url, params=params, timeout=60)

                if response.status_code == 200:
                    data = response.json()
                    existing_symbols = {s['symbol'] for s in stocks}

                    if isinstance(data, dict) and 'Table' in data:
                        for item in data['Table']:
                            scrip_cd = str(item.get('SCRIP_CD', '')).strip()
                            if scrip_cd and scrip_cd not in existing_symbols:
                                stocks.append({
                                    'symbol': scrip_cd,
                                    'name': str(item.get('scrip_nm', scrip_cd)).strip(),
                                    'exchange': 'BSE',
                                    'sector': '',
                                    'industry': ''
                                })
                                existing_symbols.add(scrip_cd)

                print(f"Method 2: {len(stocks)} stocks")
            except Exception as e:
                print(f"BSE header data method failed: {e}")

        # Method 3: BSE listing data
        if len(stocks) < 4000:
            try:
                # Get stocks by different groups
                groups = ['A', 'B', 'T', 'S', 'M', 'MT', 'TS', 'P', 'Z', 'X', 'XT']
                existing_symbols = {s['symbol'] for s in stocks}

                for group in groups:
                    url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
                    params = {'Group': group, 'Atea': '', 'Status': 'Active'}

                    try:
                        response = self.session.get(url, params=params, timeout=30)
                        if response.status_code == 200:
                            data = response.json()
                            if isinstance(data, list):
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
                        time.sleep(0.3)
                    except:
                        continue

                print(f"Method 3 (Groups): {len(stocks)} stocks")
            except Exception as e:
                print(f"BSE groups method failed: {e}")

        print(f"Total BSE stocks found: {len(stocks)}")
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
            except Exception as e:
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
        print(f"Saved {results['nse']} NSE stocks")

        # Fetch BSE stocks
        bse_stocks = self.fetch_bse_stocks()
        results['bse'] = self.save_stocks_to_db(bse_stocks)
        print(f"Saved {results['bse']} BSE stocks")

        results['total'] = results['nse'] + results['bse']

        print(f"\n{'='*50}")
        print(f"Total stocks saved: {results['total']}")
        print(f"  NSE: {results['nse']}")
        print(f"  BSE: {results['bse']}")
        print(f"{'='*50}")

        return results


if __name__ == '__main__':
    fetcher = StockFetcher()
    results = fetcher.fetch_and_save_all()
