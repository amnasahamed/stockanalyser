#!/usr/bin/env python3
"""
Comprehensive Stock Analysis Script
Downloads full NSE/BSE lists, normalizes symbols, fetches OHLC in bulk,
calculates all indicators, detects breakouts, and exports to Excel/CSV

Features:
- Market Cap & Category
- Sector & Industry
- 52W High/Low
- Delivery %
- Futures/Lot size
- SMA, EMA, RSI, MACD
- Daily momentum rank
- Penny stock detection
- Bulk/Block deal data
- High-probability breakout scanner
"""
import argparse
import os
import sys
from datetime import datetime, date

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DatabaseManager
from data.stock_fetcher import StockFetcher
from data.ohlcv_downloader import OHLCVDownloader
from data.enhanced_fetcher import EnhancedDataFetcher, EnhancedIndicatorCalculator
from data.exporter import DataExporter
from analysis.indicators import IndicatorCalculator
from analysis.circuit_detector import CircuitDetector
from analysis.breakout_scanner import BreakoutScanner
from analysis.predictor import CircuitPredictor


def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)


def print_progress(message):
    """Print progress message with timestamp"""
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] {message}")


def run_full_pipeline(exchange=None, skip_download=False, skip_fundamentals=False,
                      export_format='excel', export_report=True):
    """
    Run the complete stock analysis pipeline

    Args:
        exchange: 'NSE', 'BSE', or None for both
        skip_download: Skip OHLCV download if data exists
        skip_fundamentals: Skip fundamentals fetch
        export_format: 'excel' or 'csv'
        export_report: Export daily report at end
    """
    start_time = datetime.now()

    print_header("Stock Circuit Predictor - Full Analysis Pipeline")
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Exchange: {exchange or 'All'}")
    print()

    # Initialize components
    db = DatabaseManager()
    fetcher = StockFetcher()
    downloader = OHLCVDownloader()
    enhanced_fetcher = EnhancedDataFetcher()
    indicator_calc = IndicatorCalculator()
    extended_calc = EnhancedIndicatorCalculator()
    circuit_detector = CircuitDetector()
    breakout_scanner = BreakoutScanner()
    predictor = CircuitPredictor()
    exporter = DataExporter()

    # Step 1: Fetch Stock Lists
    print_header("Step 1: Fetching Stock Lists from NSE/BSE")
    result = fetcher.fetch_and_save_all()
    print_progress(f"NSE: {result['nse']} stocks")
    print_progress(f"BSE: {result['bse']} stocks")
    print_progress(f"Total: {result['total']} unique stocks")

    # Step 2: Download OHLCV Data
    if not skip_download:
        print_header("Step 2: Downloading OHLCV Data")
        if exchange:
            result = downloader.download_all_stocks(exchange=exchange,
                                                    progress_callback=print_progress)
        else:
            for exc in ['NSE', 'BSE']:
                result = downloader.download_all_stocks(exchange=exc,
                                                        progress_callback=print_progress)
    else:
        print_header("Step 2: Skipping OHLCV Download (--skip-download)")

    # Step 3: Fetch Fundamentals (Market Cap, 52W, F&O, etc.)
    if not skip_fundamentals:
        print_header("Step 3: Fetching Stock Fundamentals")
        result = enhanced_fetcher.update_all_fundamentals(exchange=exchange,
                                                          progress_callback=print_progress)
        print_progress(f"Updated: {result['updated']}, Errors: {result['errors']}")
    else:
        print_header("Step 3: Skipping Fundamentals (--skip-fundamentals)")

    # Step 4: Calculate Basic Technical Indicators
    print_header("Step 4: Calculating Technical Indicators")
    result = indicator_calc.calculate_for_all_stocks(exchange=exchange,
                                                     progress_callback=print_progress)
    print_progress(f"Calculated: {result['calculated']}, Errors: {result['errors']}")

    # Step 5: Calculate Extended Indicators (EMA, Bollinger, ADX, etc.)
    print_header("Step 5: Calculating Extended Indicators & Momentum")
    result = extended_calc.calculate_for_all_stocks(exchange=exchange,
                                                    progress_callback=print_progress)
    print_progress(f"Calculated: {result['calculated']}, Errors: {result['errors']}")

    # Step 6: Detect Circuit Events
    print_header("Step 6: Detecting Circuit Events (UC/LC)")
    result = circuit_detector.detect_for_all_stocks(exchange=exchange,
                                                    progress_callback=print_progress)
    print_progress(f"Detected: {result['detected']}, Errors: {result['errors']}")

    # Step 7: Scan for Breakout Signals
    print_header("Step 7: Scanning for Breakout Patterns")
    signals = breakout_scanner.scan_all_stocks(exchange=exchange, min_strength=50,
                                               progress_callback=print_progress)
    print_progress(f"Found {len(signals)} breakout signals")

    # Show top signals
    if signals:
        print("\nTop Breakout Signals:")
        for signal in signals[:10]:
            print(f"  {signal['symbol']}: {signal['signal_type']} "
                  f"(Strength: {signal['signal_strength']:.0f}%, "
                  f"R:R {signal['risk_reward_ratio']:.1f})")

    # Step 8: Fetch Bulk/Block Deals
    print_header("Step 8: Fetching Bulk/Block Deals")
    result = enhanced_fetcher.save_bulk_block_deals(progress_callback=print_progress)
    print_progress(f"Saved {result['saved']} deals")

    # Step 9: Update Delivery Data (NSE only)
    if exchange in [None, 'NSE']:
        print_header("Step 9: Updating Delivery Data")
        result = enhanced_fetcher.update_delivery_data(exchange='NSE',
                                                        progress_callback=print_progress)
        print_progress(f"Updated: {result['updated']}, Errors: {result['errors']}")

    # Step 10: Train/Update ML Models
    print_header("Step 10: Training Prediction Models")
    try:
        predictor.train_all_models()
        print_progress("Models trained successfully")
    except Exception as e:
        print_progress(f"Model training failed: {str(e)}")

    # Step 11: Export Report
    if export_report:
        print_header("Step 11: Exporting Daily Report")
        try:
            filepath = exporter.export_daily_report(format=export_format)
            print_progress(f"Report exported to: {filepath}")

            # Also export specific lists
            filepath = exporter.export_breakout_signals(min_strength=60, format=export_format)
            print_progress(f"Breakout signals: {filepath}")

            filepath = exporter.export_momentum_ranking(limit=200, format=export_format)
            print_progress(f"Momentum ranking: {filepath}")

        except Exception as e:
            print_progress(f"Export failed: {str(e)}")

    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60

    print_header("Pipeline Complete!")
    print(f"Duration: {duration:.1f} minutes")
    print(f"Finished at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Final statistics
    stats = db.get_download_stats()
    print(f"\nDatabase Statistics:")
    print(f"  Total Stocks: {stats['total']}")
    print(f"  Data Downloaded: {stats['completed']}")
    print(f"  Pending: {stats['pending']}")
    print(f"  Errors: {stats['errors']}")


def run_quick_scan(exchange='NSE'):
    """
    Run a quick scan for breakout signals without updating data

    Args:
        exchange: Exchange to scan
    """
    print_header(f"Quick Breakout Scan - {exchange}")

    scanner = BreakoutScanner()
    signals = scanner.scan_all_stocks(exchange=exchange, min_strength=50,
                                      progress_callback=print_progress)

    print(f"\nFound {len(signals)} breakout signals\n")

    if signals:
        print("="*80)
        print(f"{'Symbol':<12} {'Type':<25} {'Strength':<10} {'Entry':<10} {'Target':<10} {'R:R':<6}")
        print("="*80)

        for signal in signals[:30]:
            print(f"{signal['symbol']:<12} {signal['signal_type']:<25} "
                  f"{signal['signal_strength']:<10.0f} {signal['entry_price']:<10.2f} "
                  f"{signal['target_1']:<10.2f} {signal['risk_reward_ratio']:<6.1f}")

        print("="*80)


def run_export_only(export_type='daily', exchange=None, format='excel'):
    """
    Run export only without updating data

    Args:
        export_type: Type of export
        exchange: Exchange filter
        format: Export format
    """
    print_header(f"Exporting: {export_type}")

    exporter = DataExporter()

    if export_type == 'daily':
        filepath = exporter.export_daily_report(format=format)
    elif export_type == 'stocks':
        filepath = exporter.export_stock_list(exchange=exchange, format=format)
    elif export_type == 'breakouts':
        filepath = exporter.export_breakout_signals(format=format)
    elif export_type == 'momentum':
        filepath = exporter.export_momentum_ranking(exchange=exchange, format=format)
    elif export_type == 'penny':
        filepath = exporter.export_penny_stocks(format=format)
    elif export_type == 'fno':
        filepath = exporter.export_fno_stocks(format=format)
    elif export_type == 'deals':
        filepath = exporter.export_bulk_block_deals(format=format)
    else:
        print(f"Unknown export type: {export_type}")
        return

    print(f"Exported to: {filepath}")


def analyze_stock(symbol):
    """
    Get comprehensive analysis for a single stock

    Args:
        symbol: Stock symbol
    """
    db = DatabaseManager()
    data = db.get_comprehensive_stock_data(symbol)

    if not data:
        print(f"Stock not found: {symbol}")
        return

    print_header(f"Stock Analysis: {symbol}")

    stock = data['stock']
    print(f"\nBasic Info:")
    print(f"  Name: {stock['name']}")
    print(f"  Exchange: {stock['exchange']}")
    print(f"  Sector: {stock.get('sector', 'N/A')}")

    if data['fundamentals']:
        f = data['fundamentals']
        market_cap_cr = f.get('market_cap', 0) / 10000000 if f.get('market_cap') else 0

        print(f"\nFundamentals:")
        print(f"  Market Cap: Rs {market_cap_cr:,.0f} Cr ({f.get('market_cap_category', 'N/A')})")
        print(f"  52W High: {f.get('week_52_high', 'N/A')}")
        print(f"  52W Low: {f.get('week_52_low', 'N/A')}")
        print(f"  PE Ratio: {f.get('pe_ratio', 'N/A')}")
        print(f"  PB Ratio: {f.get('pb_ratio', 'N/A')}")
        print(f"  F&O Stock: {'Yes' if f.get('is_fno') else 'No'}")
        if f.get('is_fno'):
            print(f"  Lot Size: {f.get('lot_size', 'N/A')}")
        print(f"  Penny Stock: {'Yes' if f.get('is_penny_stock') else 'No'}")

    if data['ohlcv']:
        o = data['ohlcv']
        print(f"\nLatest Price ({o.get('date')}):")
        print(f"  Open: {o.get('open', 0):.2f}")
        print(f"  High: {o.get('high', 0):.2f}")
        print(f"  Low: {o.get('low', 0):.2f}")
        print(f"  Close: {o.get('close', 0):.2f}")
        print(f"  Volume: {o.get('volume', 0):,}")

    if data['indicators']:
        i = data['indicators']
        print(f"\nTechnical Indicators:")
        print(f"  RSI (14): {i.get('rsi_14', 0):.1f}")
        print(f"  MACD: {i.get('macd', 0):.2f}")
        print(f"  MACD Signal: {i.get('macd_signal', 0):.2f}")
        print(f"  MA (5): {i.get('ma_5', 0):.2f}")
        print(f"  MA (20): {i.get('ma_20', 0):.2f}")
        print(f"  MA (50): {i.get('ma_50', 0):.2f}")

    if data['extended_indicators']:
        e = data['extended_indicators']
        print(f"\nExtended Indicators:")
        print(f"  EMA (9): {e.get('ema_9', 0):.2f}")
        print(f"  EMA (21): {e.get('ema_21', 0):.2f}")
        print(f"  EMA (200): {e.get('ema_200', 0):.2f}")
        print(f"  Momentum Score: {e.get('momentum_score', 0):.0f}/100")
        print(f"  Momentum Rank: #{e.get('momentum_rank', 'N/A')}")
        print(f"  ADX: {e.get('adx_14', 0):.1f}")

    if data['delivery']:
        d = data['delivery']
        print(f"\nDelivery Data ({d.get('date')}):")
        print(f"  Traded Qty: {d.get('traded_qty', 0):,}")
        print(f"  Deliverable Qty: {d.get('deliverable_qty', 0):,}")
        print(f"  Delivery %: {d.get('delivery_pct', 0):.1f}%")

    if data['breakout_signals']:
        print(f"\nRecent Breakout Signals:")
        for signal in data['breakout_signals'][:3]:
            print(f"  {signal['date']}: {signal['signal_type']} "
                  f"(Strength: {signal['signal_strength']:.0f}%)")

    if data['bulk_block_deals']:
        print(f"\nRecent Bulk/Block Deals:")
        for deal in data['bulk_block_deals'][:3]:
            print(f"  {deal['date']}: {deal['deal_type']} - "
                  f"{deal['buy_sell']} {deal.get('quantity', 0):,} @ {deal.get('price', 0):.2f}")


def main():
    parser = argparse.ArgumentParser(description='Stock Circuit Predictor - Comprehensive Analysis')
    parser.add_argument('command', nargs='?', default='full',
                       choices=['full', 'scan', 'export', 'analyze'],
                       help='Command to run')
    parser.add_argument('--exchange', '-e', choices=['NSE', 'BSE'],
                       help='Exchange to process')
    parser.add_argument('--symbol', '-s', type=str,
                       help='Stock symbol for analysis')
    parser.add_argument('--export-type', '-t', default='daily',
                       choices=['daily', 'stocks', 'breakouts', 'momentum', 'penny', 'fno', 'deals'],
                       help='Type of export')
    parser.add_argument('--format', '-f', default='excel',
                       choices=['excel', 'csv'],
                       help='Export format')
    parser.add_argument('--skip-download', action='store_true',
                       help='Skip OHLCV download')
    parser.add_argument('--skip-fundamentals', action='store_true',
                       help='Skip fundamentals fetch')
    parser.add_argument('--no-export', action='store_true',
                       help='Skip export at end')

    args = parser.parse_args()

    if args.command == 'full':
        run_full_pipeline(
            exchange=args.exchange,
            skip_download=args.skip_download,
            skip_fundamentals=args.skip_fundamentals,
            export_format=args.format,
            export_report=not args.no_export
        )
    elif args.command == 'scan':
        run_quick_scan(exchange=args.exchange or 'NSE')
    elif args.command == 'export':
        run_export_only(
            export_type=args.export_type,
            exchange=args.exchange,
            format=args.format
        )
    elif args.command == 'analyze':
        if not args.symbol:
            print("Error: --symbol required for analyze command")
            sys.exit(1)
        analyze_stock(args.symbol.upper())


if __name__ == '__main__':
    main()
