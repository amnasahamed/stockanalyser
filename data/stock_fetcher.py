"""
Stock List Fetcher for NSE and BSE
Downloads complete equity lists from both exchanges
"""
import requests
import pandas as pd
import os
import sys
import json
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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_nse_stocks(self):
        """Fetch all NSE equity stocks"""
        print("Fetching NSE stock list...")

        stocks = []

        # Method 1: Try NSE API
        try:
            # NSE equity list endpoint
            url = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"

            # First visit main page to get cookies
            self.session.get("https://www.nseindia.com", timeout=10)
            time.sleep(1)

            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    for item in data['data']:
                        stocks.append({
                            'symbol': item.get('symbol', ''),
                            'name': item.get('companyName', item.get('symbol', '')),
                            'exchange': 'NSE',
                            'sector': item.get('industry', ''),
                            'industry': item.get('industry', '')
                        })
        except Exception as e:
            print(f"NSE API method failed: {e}")

        # Method 2: Use yfinance to get common NSE stocks
        # This is a fallback with major NSE stocks
        if len(stocks) < 100:
            print("Using fallback NSE stock list...")
            stocks = self._get_fallback_nse_stocks()

        print(f"Found {len(stocks)} NSE stocks")
        return stocks

    def fetch_bse_stocks(self):
        """Fetch all BSE equity stocks"""
        print("Fetching BSE stock list...")

        stocks = []

        # Method 1: Try BSE API
        try:
            url = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
            params = {
                'Group': '',
                'Atea': '',
                'Status': 'Active'
            }
            response = self.session.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    for item in data:
                        stocks.append({
                            'symbol': item.get('scrip_cd', ''),
                            'name': item.get('scrip_nm', ''),
                            'exchange': 'BSE',
                            'sector': item.get('group', ''),
                            'industry': ''
                        })
        except Exception as e:
            print(f"BSE API method failed: {e}")

        # Method 2: Fallback
        if len(stocks) < 100:
            print("Using fallback BSE stock list...")
            stocks = self._get_fallback_bse_stocks()

        print(f"Found {len(stocks)} BSE stocks")
        return stocks

    def _get_fallback_nse_stocks(self):
        """Fallback list of major NSE stocks"""
        # Comprehensive list of NSE stocks with their yfinance symbols
        nse_symbols = [
            # Nifty 50
            ('RELIANCE', 'Reliance Industries'),
            ('TCS', 'Tata Consultancy Services'),
            ('HDFCBANK', 'HDFC Bank'),
            ('INFY', 'Infosys'),
            ('ICICIBANK', 'ICICI Bank'),
            ('HINDUNILVR', 'Hindustan Unilever'),
            ('SBIN', 'State Bank of India'),
            ('BHARTIARTL', 'Bharti Airtel'),
            ('KOTAKBANK', 'Kotak Mahindra Bank'),
            ('ITC', 'ITC Limited'),
            ('LT', 'Larsen & Toubro'),
            ('AXISBANK', 'Axis Bank'),
            ('ASIANPAINT', 'Asian Paints'),
            ('MARUTI', 'Maruti Suzuki'),
            ('HCLTECH', 'HCL Technologies'),
            ('SUNPHARMA', 'Sun Pharmaceutical'),
            ('TITAN', 'Titan Company'),
            ('BAJFINANCE', 'Bajaj Finance'),
            ('WIPRO', 'Wipro'),
            ('ULTRACEMCO', 'UltraTech Cement'),
            ('ONGC', 'Oil and Natural Gas Corporation'),
            ('NTPC', 'NTPC Limited'),
            ('POWERGRID', 'Power Grid Corporation'),
            ('M&M', 'Mahindra & Mahindra'),
            ('JSWSTEEL', 'JSW Steel'),
            ('TATAMOTORS', 'Tata Motors'),
            ('ADANIENT', 'Adani Enterprises'),
            ('TATASTEEL', 'Tata Steel'),
            ('ADANIPORTS', 'Adani Ports'),
            ('COALINDIA', 'Coal India'),
            ('BAJAJFINSV', 'Bajaj Finserv'),
            ('TECHM', 'Tech Mahindra'),
            ('GRASIM', 'Grasim Industries'),
            ('INDUSINDBK', 'IndusInd Bank'),
            ('DRREDDY', 'Dr Reddys Laboratories'),
            ('CIPLA', 'Cipla'),
            ('NESTLEIND', 'Nestle India'),
            ('BRITANNIA', 'Britannia Industries'),
            ('BPCL', 'Bharat Petroleum'),
            ('DIVISLAB', 'Divis Laboratories'),
            ('HEROMOTOCO', 'Hero MotoCorp'),
            ('EICHERMOT', 'Eicher Motors'),
            ('APOLLOHOSP', 'Apollo Hospitals'),
            ('SBILIFE', 'SBI Life Insurance'),
            ('TATACONSUM', 'Tata Consumer Products'),
            ('HINDALCO', 'Hindalco Industries'),
            ('BAJAJ-AUTO', 'Bajaj Auto'),
            ('HDFCLIFE', 'HDFC Life Insurance'),
            ('UPL', 'UPL Limited'),
            ('SHREECEM', 'Shree Cement'),
            # Nifty Next 50 and others
            ('ADANIGREEN', 'Adani Green Energy'),
            ('ADANITRANS', 'Adani Transmission'),
            ('AMBUJACEM', 'Ambuja Cements'),
            ('AUROPHARMA', 'Aurobindo Pharma'),
            ('BANDHANBNK', 'Bandhan Bank'),
            ('BANKBARODA', 'Bank of Baroda'),
            ('BERGEPAINT', 'Berger Paints'),
            ('BIOCON', 'Biocon'),
            ('BOSCHLTD', 'Bosch'),
            ('CADILAHC', 'Cadila Healthcare'),
            ('CHOLAFIN', 'Cholamandalam Investment'),
            ('COLPAL', 'Colgate-Palmolive'),
            ('DABUR', 'Dabur India'),
            ('DLF', 'DLF Limited'),
            ('GAIL', 'GAIL India'),
            ('GODREJCP', 'Godrej Consumer Products'),
            ('HAVELLS', 'Havells India'),
            ('HDFC', 'Housing Development Finance'),
            ('ICICIGI', 'ICICI Lombard General Insurance'),
            ('ICICIPRULI', 'ICICI Prudential Life'),
            ('IDEA', 'Vodafone Idea'),
            ('INDIGO', 'InterGlobe Aviation'),
            ('IOC', 'Indian Oil Corporation'),
            ('IRCTC', 'IRCTC'),
            ('JUBLFOOD', 'Jubilant FoodWorks'),
            ('LICI', 'Life Insurance Corporation'),
            ('LUPIN', 'Lupin'),
            ('MARICO', 'Marico'),
            ('MCDOWELL-N', 'United Spirits'),
            ('MOTHERSON', 'Motherson Sumi Wiring'),
            ('MUTHOOTFIN', 'Muthoot Finance'),
            ('NAUKRI', 'Info Edge India'),
            ('NMDC', 'NMDC'),
            ('PAYTM', 'One 97 Communications'),
            ('PEL', 'Piramal Enterprises'),
            ('PETRONET', 'Petronet LNG'),
            ('PFC', 'Power Finance Corporation'),
            ('PIDILITIND', 'Pidilite Industries'),
            ('PNB', 'Punjab National Bank'),
            ('RECLTD', 'REC Limited'),
            ('SAIL', 'Steel Authority of India'),
            ('SIEMENS', 'Siemens'),
            ('SRF', 'SRF Limited'),
            ('TATAELXSI', 'Tata Elxsi'),
            ('TATAPOWER', 'Tata Power'),
            ('TORNTPHARM', 'Torrent Pharmaceuticals'),
            ('TRENT', 'Trent'),
            ('VEDL', 'Vedanta'),
            ('ZOMATO', 'Zomato'),
            ('ZYDUSLIFE', 'Zydus Lifesciences'),
            # Additional mid-caps
            ('AARTIIND', 'Aarti Industries'),
            ('ABCAPITAL', 'Aditya Birla Capital'),
            ('ABFRL', 'Aditya Birla Fashion'),
            ('ACC', 'ACC Limited'),
            ('ALKEM', 'Alkem Laboratories'),
            ('ASHOKLEY', 'Ashok Leyland'),
            ('ASTRAL', 'Astral'),
            ('ATUL', 'Atul'),
            ('BALKRISIND', 'Balkrishna Industries'),
            ('BEL', 'Bharat Electronics'),
            ('BHARATFORG', 'Bharat Forge'),
            ('BHEL', 'Bharat Heavy Electricals'),
            ('CANFINHOME', 'Can Fin Homes'),
            ('CANBK', 'Canara Bank'),
            ('CONCOR', 'Container Corporation'),
            ('COROMANDEL', 'Coromandel International'),
            ('CROMPTON', 'Crompton Greaves'),
            ('CUB', 'City Union Bank'),
            ('CUMMINSIND', 'Cummins India'),
            ('DEEPAKNTR', 'Deepak Nitrite'),
            ('DELHIVERY', 'Delhivery'),
            ('DIXON', 'Dixon Technologies'),
            ('ESCORTS', 'Escorts Kubota'),
            ('EXIDEIND', 'Exide Industries'),
            ('FEDERALBNK', 'Federal Bank'),
            ('FSL', 'Firstsource Solutions'),
            ('GLENMARK', 'Glenmark Pharmaceuticals'),
            ('GMRINFRA', 'GMR Airports'),
            ('GNFC', 'GNFC'),
            ('GODREJPROP', 'Godrej Properties'),
            ('GRANULES', 'Granules India'),
            ('GSPL', 'Gujarat State Petronet'),
            ('GUJGASLTD', 'Gujarat Gas'),
            ('HAL', 'Hindustan Aeronautics'),
            ('HDFCAMC', 'HDFC Asset Management'),
            ('HINDPETRO', 'Hindustan Petroleum'),
            ('IDFCFIRSTB', 'IDFC First Bank'),
            ('IEX', 'Indian Energy Exchange'),
            ('INDIANB', 'Indian Bank'),
            ('INDUSTOWER', 'Indus Towers'),
            ('IPCA', 'IPCA Laboratories'),
            ('IRFC', 'Indian Railway Finance'),
            ('JINDALSTEL', 'Jindal Steel & Power'),
            ('JKCEMENT', 'JK Cement'),
            ('JSWENERGY', 'JSW Energy'),
            ('KAJARIACER', 'Kajaria Ceramics'),
            ('KEI', 'KEI Industries'),
            ('LICHSGFIN', 'LIC Housing Finance'),
            ('LTF', 'L&T Finance'),
            ('LTIM', 'LTIMindtree'),
            ('LTTS', 'L&T Technology Services'),
            ('M&MFIN', 'Mahindra & Mahindra Financial'),
            ('MANAPPURAM', 'Manappuram Finance'),
            ('MAXHEALTH', 'Max Healthcare'),
            ('METROPOLIS', 'Metropolis Healthcare'),
            ('MFSL', 'Max Financial Services'),
            ('MGL', 'Mahanagar Gas'),
            ('MINDTREE', 'Mindtree'),
            ('MPHASIS', 'Mphasis'),
            ('MRF', 'MRF'),
            ('NAM-INDIA', 'Nippon Life India'),
            ('NATIONALUM', 'National Aluminium'),
            ('NAUKRI', 'Info Edge'),
            ('NAVINFLUOR', 'Navin Fluorine'),
            ('NBCC', 'NBCC India'),
            ('NCC', 'NCC Limited'),
            ('OBEROIRLTY', 'Oberoi Realty'),
            ('OFSS', 'Oracle Financial Services'),
            ('OIL', 'Oil India'),
            ('PAGEIND', 'Page Industries'),
            ('PERSISTENT', 'Persistent Systems'),
            ('PIIND', 'PI Industries'),
            ('POLYCAB', 'Polycab India'),
            ('POONAWALLA', 'Poonawalla Fincorp'),
            ('PRESTIGE', 'Prestige Estates'),
            ('PVRINOX', 'PVR INOX'),
            ('RAJESHEXPO', 'Rajesh Exports'),
            ('RAMCOCEM', 'Ramco Cements'),
            ('RBLBANK', 'RBL Bank'),
            ('RELIANCE', 'Reliance Industries'),
            ('SBICARD', 'SBI Cards'),
            ('SCHAEFFLER', 'Schaeffler India'),
            ('SHRIRAMFIN', 'Shriram Finance'),
            ('SOLARINDS', 'Solar Industries'),
            ('SONACOMS', 'Sona BLW Precision'),
            ('STAR', 'Star Health Insurance'),
            ('SUNPHARMA', 'Sun Pharmaceutical'),
            ('SUPREMEIND', 'Supreme Industries'),
            ('SYNGENE', 'Syngene International'),
            ('TATACHEM', 'Tata Chemicals'),
            ('TATACOMM', 'Tata Communications'),
            ('TIINDIA', 'Tube Investments'),
            ('TORNTPOWER', 'Torrent Power'),
            ('TVSMOTOR', 'TVS Motor'),
            ('UBL', 'United Breweries'),
            ('UNIONBANK', 'Union Bank of India'),
            ('VOLTAS', 'Voltas'),
            ('WHIRLPOOL', 'Whirlpool of India'),
            ('YESBANK', 'Yes Bank'),
        ]

        return [
            {
                'symbol': symbol,
                'name': name,
                'exchange': 'NSE',
                'sector': '',
                'industry': ''
            }
            for symbol, name in nse_symbols
        ]

    def _get_fallback_bse_stocks(self):
        """Fallback list of major BSE stocks"""
        # BSE stocks with their codes
        bse_stocks = [
            ('500325', 'Reliance Industries'),
            ('532540', 'TCS'),
            ('500180', 'HDFC Bank'),
            ('500209', 'Infosys'),
            ('532174', 'ICICI Bank'),
            ('500696', 'Hindustan Unilever'),
            ('500112', 'State Bank of India'),
            ('532454', 'Bharti Airtel'),
            ('500247', 'Kotak Mahindra Bank'),
            ('500875', 'ITC'),
            ('500510', 'Larsen & Toubro'),
            ('532215', 'Axis Bank'),
            ('500820', 'Asian Paints'),
            ('532500', 'Maruti Suzuki'),
            ('532281', 'HCL Technologies'),
            ('524715', 'Sun Pharmaceutical'),
            ('500114', 'Titan Company'),
            ('500034', 'Bajaj Finance'),
            ('507685', 'Wipro'),
            ('532538', 'UltraTech Cement'),
            ('500312', 'ONGC'),
            ('532555', 'NTPC'),
            ('532898', 'Power Grid'),
            ('500520', 'Mahindra & Mahindra'),
            ('500228', 'JSW Steel'),
            ('500570', 'Tata Motors'),
            ('512599', 'Adani Enterprises'),
            ('500470', 'Tata Steel'),
            ('532921', 'Adani Ports'),
            ('533278', 'Coal India'),
            ('532978', 'Bajaj Finserv'),
            ('532755', 'Tech Mahindra'),
            ('500300', 'Grasim Industries'),
            ('532187', 'IndusInd Bank'),
            ('500124', 'Dr Reddys'),
            ('500087', 'Cipla'),
            ('500790', 'Nestle India'),
            ('500825', 'Britannia'),
            ('500547', 'BPCL'),
            ('532488', 'Divis Laboratories'),
            ('500182', 'Hero MotoCorp'),
            ('505200', 'Eicher Motors'),
            ('508869', 'Apollo Hospitals'),
            ('540719', 'SBI Life Insurance'),
            ('500800', 'Tata Consumer'),
            ('500440', 'Hindalco'),
            ('532977', 'Bajaj Auto'),
            ('540777', 'HDFC Life'),
            ('512070', 'UPL'),
            ('500387', 'Shree Cement'),
        ]

        return [
            {
                'symbol': code,
                'name': name,
                'exchange': 'BSE',
                'sector': '',
                'industry': ''
            }
            for code, name in bse_stocks
        ]

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
                print(f"Error saving {stock['symbol']}: {e}")
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
        return results


if __name__ == '__main__':
    fetcher = StockFetcher()
    results = fetcher.fetch_and_save_all()
    print(f"\nTotal stocks saved: {results['total']}")
