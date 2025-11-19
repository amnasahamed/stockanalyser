"""
Data Exporter for Stock Circuit Predictor
Export stock data to Excel, CSV formats
"""
import pandas as pd
from datetime import datetime, date, timedelta
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db_manager import DatabaseManager


class DataExporter:
    """Export stock analysis data to various formats"""

    def __init__(self):
        self.db = DatabaseManager()
        self.export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'exports')
        os.makedirs(self.export_dir, exist_ok=True)

    def export_stock_list(self, exchange=None, filename=None, format='excel'):
        """Export complete stock list with fundamentals"""
        conn = self.db.get_connection()

        query = '''
            SELECT
                s.symbol, s.name, s.exchange, s.sector, s.industry,
                sf.market_cap, sf.market_cap_category, sf.week_52_high, sf.week_52_low,
                sf.avg_delivery_pct, sf.is_fno, sf.lot_size, sf.is_asm, sf.is_gsm, sf.is_esm,
                sf.is_penny_stock, sf.face_value, sf.book_value, sf.pe_ratio, sf.pb_ratio,
                sf.dividend_yield, sf.last_updated
            FROM stocks s
            LEFT JOIN stock_fundamentals sf ON s.id = sf.stock_id
            WHERE s.is_active = 1
        '''

        if exchange:
            query += f" AND s.exchange = '{exchange}'"

        query += " ORDER BY s.symbol"

        df = pd.read_sql_query(query, conn)
        conn.close()

        # Format market cap in Crores
        df['market_cap_cr'] = df['market_cap'].apply(lambda x: x / 10000000 if x else None)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            exchange_str = f"_{exchange}" if exchange else ""
            filename = f"stock_list{exchange_str}_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def export_momentum_ranking(self, exchange=None, limit=500, filename=None, format='excel'):
        """Export stocks ranked by momentum score"""
        df = self.db.get_top_momentum_stocks(limit=limit, exchange=exchange)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"momentum_ranking_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def export_breakout_signals(self, min_strength=50, filename=None, format='excel'):
        """Export current breakout signals"""
        today = date.today().isoformat()
        df = self.db.get_breakout_signals(min_strength=min_strength, date=today)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"breakout_signals_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def export_high_delivery_stocks(self, min_delivery_pct=50, filename=None, format='excel'):
        """Export stocks with high delivery percentage"""
        df = self.db.get_high_delivery_stocks(min_delivery_pct=min_delivery_pct)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"high_delivery_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def export_penny_stocks(self, filename=None, format='excel'):
        """Export penny stocks list"""
        df = self.db.get_penny_stocks()

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"penny_stocks_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def export_fno_stocks(self, filename=None, format='excel'):
        """Export F&O stocks with lot sizes"""
        df = self.db.get_fno_stocks()

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"fno_stocks_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def export_bulk_block_deals(self, days=7, filename=None, format='excel'):
        """Export recent bulk/block deals"""
        start_date = (date.today() - timedelta(days=days)).isoformat()
        df = self.db.get_bulk_block_deals(start_date=start_date)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"bulk_block_deals_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def export_circuit_events(self, event_type=None, days=30, filename=None, format='excel'):
        """Export circuit events history"""
        start_date = (date.today() - timedelta(days=days)).isoformat()
        df = self.db.get_circuit_events(event_type=event_type, start_date=start_date)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            event_str = f"_{event_type}" if event_type else ""
            filename = f"circuit_events{event_str}_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def export_stock_analysis(self, symbol, filename=None, format='excel'):
        """Export comprehensive analysis for a single stock"""
        data = self.db.get_comprehensive_stock_data(symbol)
        if not data:
            return None

        # Create multiple sheets for Excel or single combined CSV
        sheets = {}

        # Stock info
        stock_info = pd.DataFrame([data['stock']])
        if data['fundamentals']:
            fundamentals = pd.DataFrame([data['fundamentals']])
            stock_info = pd.concat([stock_info, fundamentals], axis=1)
        sheets['Stock Info'] = stock_info

        # Get OHLCV history
        stock = self.db.get_stock_by_symbol(symbol)
        if stock:
            ohlcv = self.db.get_ohlcv_data(stock['id'])
            if not ohlcv.empty:
                sheets['OHLCV Data'] = ohlcv.tail(100)

            # Get indicators
            indicators = self.db.get_indicators(stock['id'])
            if not indicators.empty:
                sheets['Indicators'] = indicators.tail(100)

            # Get extended indicators
            extended = self.db.get_extended_indicators(stock['id'])
            if not extended.empty:
                sheets['Extended Indicators'] = extended.tail(100)

        # Breakout signals
        if data['breakout_signals']:
            sheets['Breakout Signals'] = pd.DataFrame(data['breakout_signals'])

        # Bulk/Block deals
        if data['bulk_block_deals']:
            sheets['Bulk Block Deals'] = pd.DataFrame(data['bulk_block_deals'])

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{symbol}_analysis_{timestamp}"

        if format == 'excel':
            filepath = os.path.join(self.export_dir, f"{filename}.xlsx")
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            return filepath
        else:
            # For CSV, combine all data
            combined = pd.DataFrame()
            for name, df in sheets.items():
                if not df.empty:
                    df['_section'] = name
                    combined = pd.concat([combined, df], ignore_index=True)
            filepath = os.path.join(self.export_dir, f"{filename}.csv")
            combined.to_csv(filepath, index=False)
            return filepath

    def export_daily_report(self, filename=None, format='excel'):
        """Export comprehensive daily analysis report"""
        today = date.today().isoformat()

        sheets = {}

        # 1. Market Overview
        stats = self.db.get_download_stats()
        conn = self.db.get_connection()

        overview_data = {
            'Total Stocks': [stats['total']],
            'Data Downloaded': [stats['completed']],
            'Date': [today]
        }
        sheets['Overview'] = pd.DataFrame(overview_data)

        # 2. Today's Breakout Signals
        breakouts = self.db.get_breakout_signals(min_strength=50, date=today)
        sheets['Breakout Signals'] = breakouts.head(100)

        # 3. Top Momentum Stocks
        momentum = self.db.get_top_momentum_stocks(limit=100)
        sheets['Momentum Ranking'] = momentum

        # 4. High Delivery Stocks
        high_delivery = self.db.get_high_delivery_stocks(min_delivery_pct=50)
        sheets['High Delivery'] = high_delivery.head(100)

        # 5. Circuit Events Today
        uc_events = self.db.get_today_circuits('UC')
        lc_events = self.db.get_today_circuits('LC')
        circuits = pd.concat([uc_events, lc_events], ignore_index=True)
        sheets['Circuit Events'] = circuits

        # 6. Recent Bulk/Block Deals
        deals = self.db.get_bulk_block_deals(start_date=(date.today() - timedelta(days=3)).isoformat())
        sheets['Bulk Block Deals'] = deals.head(100)

        # 7. Penny Stocks
        penny = self.db.get_penny_stocks()
        sheets['Penny Stocks'] = penny.head(100)

        conn.close()

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"daily_report_{timestamp}"

        if format == 'excel':
            filepath = os.path.join(self.export_dir, f"{filename}.xlsx")
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                for sheet_name, df in sheets.items():
                    if not df.empty:
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
            return filepath
        else:
            # For CSV, create separate files
            filepaths = []
            for name, df in sheets.items():
                if not df.empty:
                    filepath = os.path.join(self.export_dir, f"{filename}_{name.lower().replace(' ', '_')}.csv")
                    df.to_csv(filepath, index=False)
                    filepaths.append(filepath)
            return filepaths

    def export_watchlist(self, symbols, filename=None, format='excel'):
        """Export analysis for a list of watchlist stocks"""
        all_data = []

        for symbol in symbols:
            data = self.db.get_comprehensive_stock_data(symbol)
            if data:
                row = {
                    'Symbol': symbol,
                    'Name': data['stock']['name'],
                    'Exchange': data['stock']['exchange']
                }

                if data['fundamentals']:
                    row['Market Cap'] = data['fundamentals'].get('market_cap')
                    row['Market Cap Category'] = data['fundamentals'].get('market_cap_category')
                    row['52W High'] = data['fundamentals'].get('week_52_high')
                    row['52W Low'] = data['fundamentals'].get('week_52_low')
                    row['PE Ratio'] = data['fundamentals'].get('pe_ratio')
                    row['Is F&O'] = 'Yes' if data['fundamentals'].get('is_fno') else 'No'
                    row['Lot Size'] = data['fundamentals'].get('lot_size')

                if data['ohlcv']:
                    row['Last Close'] = data['ohlcv'].get('close')
                    row['Last Volume'] = data['ohlcv'].get('volume')
                    row['Last Date'] = data['ohlcv'].get('date')

                if data['indicators']:
                    row['RSI'] = data['indicators'].get('rsi_14')
                    row['MACD'] = data['indicators'].get('macd')

                if data['extended_indicators']:
                    row['Momentum Score'] = data['extended_indicators'].get('momentum_score')
                    row['Momentum Rank'] = data['extended_indicators'].get('momentum_rank')

                if data['delivery']:
                    row['Delivery %'] = data['delivery'].get('delivery_pct')

                all_data.append(row)

        df = pd.DataFrame(all_data)

        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"watchlist_{timestamp}"

        filepath = self._save_file(df, filename, format)
        return filepath

    def _save_file(self, df, filename, format):
        """Save DataFrame to file"""
        if format == 'excel':
            filepath = os.path.join(self.export_dir, f"{filename}.xlsx")
            df.to_excel(filepath, index=False, engine='openpyxl')
        else:  # CSV
            filepath = os.path.join(self.export_dir, f"{filename}.csv")
            df.to_csv(filepath, index=False)

        return filepath


if __name__ == '__main__':
    exporter = DataExporter()

    print("Testing Data Exporter...")
    print(f"Export directory: {exporter.export_dir}")

    # Test export
    try:
        filepath = exporter.export_stock_list(format='csv')
        print(f"Exported stock list to: {filepath}")
    except Exception as e:
        print(f"Export test error: {e}")

    print("Data Exporter initialized successfully!")
