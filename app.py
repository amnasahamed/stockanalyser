"""
Stock Circuit Predictor - Flask Web Application
Main application entry point
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import sys
from datetime import datetime, date, timedelta
import threading
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SECRET_KEY, DEBUG
from database.db_manager import DatabaseManager
from data.stock_fetcher import StockFetcher
from data.ohlcv_downloader import OHLCVDownloader
from data.enhanced_fetcher import EnhancedDataFetcher, EnhancedIndicatorCalculator
from data.exporter import DataExporter
from analysis.indicators import IndicatorCalculator
from analysis.circuit_detector import CircuitDetector
from analysis.predictor import CircuitPredictor
from analysis.breakout_scanner import BreakoutScanner

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize components
db = DatabaseManager()
stock_fetcher = StockFetcher()
ohlcv_downloader = OHLCVDownloader()
enhanced_fetcher = EnhancedDataFetcher()
extended_calc = EnhancedIndicatorCalculator()
exporter = DataExporter()
indicator_calc = IndicatorCalculator()
circuit_detector = CircuitDetector()
predictor = CircuitPredictor()
breakout_scanner = BreakoutScanner()

# Global state for background tasks
task_status = {
    'running': False,
    'current_task': None,
    'progress': 0,
    'message': '',
    'results': None
}


# Helper functions
def format_number(value, decimals=2):
    """Format number with thousand separators"""
    if value is None:
        return 'N/A'
    if isinstance(value, (int, float)):
        return f"{value:,.{decimals}f}"
    return value


def format_date(value):
    """Format date for display"""
    if value is None:
        return 'N/A'
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d')
        except:
            return value
    return value.strftime('%d %b %Y')


# Register template filters
app.jinja_env.filters['format_number'] = format_number
app.jinja_env.filters['format_date'] = format_date


# Routes
@app.route('/')
def index():
    """Dashboard - Main landing page"""
    # Get statistics
    nse_count = db.get_stock_count(exchange='NSE')
    bse_count = db.get_stock_count(exchange='BSE')
    total_count = db.get_stock_count()

    # Get today's circuits
    today_uc = db.get_today_circuits(event_type='UC')
    today_lc = db.get_today_circuits(event_type='LC')

    # Get download stats
    download_stats = db.get_download_stats()

    # Get circuit statistics
    circuit_stats = circuit_detector.get_circuit_statistics()

    # Get top UC candidates
    top_candidates = []
    try:
        candidates = predictor.screen_for_uc(min_probability=30)[:10]
        top_candidates = candidates
    except:
        pass

    return render_template('dashboard.html',
                           nse_count=nse_count,
                           bse_count=bse_count,
                           total_count=total_count,
                           today_uc=today_uc.to_dict('records') if not today_uc.empty else [],
                           today_lc=today_lc.to_dict('records') if not today_lc.empty else [],
                           download_stats=download_stats,
                           circuit_stats=circuit_stats,
                           top_candidates=top_candidates)


@app.route('/screener')
def screener():
    """UC Screener - Find stocks likely to hit UC"""
    min_prob = request.args.get('min_prob', 30, type=int)
    exchange = request.args.get('exchange', None)

    candidates = []
    try:
        all_candidates = predictor.screen_for_uc(min_probability=min_prob)
        if exchange:
            candidates = [c for c in all_candidates if c['exchange'] == exchange]
        else:
            candidates = all_candidates
    except Exception as e:
        print(f"Screener error: {e}")

    return render_template('screener.html',
                           candidates=candidates,
                           min_prob=min_prob,
                           exchange=exchange)


@app.route('/stock/<symbol>')
def stock_analysis(symbol):
    """Stock Analysis - Detailed view of a single stock"""
    # Get prediction and current status
    prediction = predictor.get_stock_prediction(symbol)

    if not prediction:
        return render_template('error.html', message=f"Stock {symbol} not found"), 404

    stock = db.get_stock_by_symbol(symbol)
    stock_id = stock['id']

    # Get OHLCV data for chart
    ohlcv = db.get_ohlcv_data(stock_id)

    # Get latest indicators
    indicators = indicator_calc.get_latest_indicators(stock_id)

    # Get circuit history
    uc_events = db.get_circuit_events(event_type='UC', stock_id=stock_id)
    lc_events = db.get_circuit_events(event_type='LC', stock_id=stock_id)

    # Get UC to LC history
    uc_to_lc = db.get_uc_to_lc_history(stock_id=stock_id)

    # Prepare chart data
    chart_data = []
    if not ohlcv.empty:
        for _, row in ohlcv.tail(90).iterrows():  # Last 90 days
            chart_data.append({
                'date': row['date'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['volume']
            })

    return render_template('stock_analysis.html',
                           stock=stock,
                           prediction=prediction,
                           indicators=indicators,
                           uc_events=uc_events.to_dict('records') if not uc_events.empty else [],
                           lc_events=lc_events.to_dict('records') if not lc_events.empty else [],
                           uc_to_lc=uc_to_lc.to_dict('records') if not uc_to_lc.empty else [],
                           chart_data=json.dumps(chart_data))


@app.route('/history')
def history():
    """UC/LC History - View all circuit events"""
    event_type = request.args.get('type', None)
    days = request.args.get('days', 30, type=int)

    start_date = (date.today() - timedelta(days=days)).isoformat()

    # Get circuit events
    events = db.get_circuit_events(event_type=event_type, start_date=start_date)

    # Get UC to LC duration history
    uc_to_lc = db.get_uc_to_lc_history()

    return render_template('history.html',
                           events=events.to_dict('records') if not events.empty else [],
                           uc_to_lc=uc_to_lc.head(100).to_dict('records') if not uc_to_lc.empty else [],
                           event_type=event_type,
                           days=days)


@app.route('/data-management')
def data_management():
    """Data Management - Download and update data"""
    # Get stock counts
    nse_count = db.get_stock_count(exchange='NSE')
    bse_count = db.get_stock_count(exchange='BSE')

    # Get download stats
    download_stats = db.get_download_stats()

    return render_template('data_management.html',
                           nse_count=nse_count,
                           bse_count=bse_count,
                           download_stats=download_stats,
                           task_status=task_status)


@app.route('/search')
def search():
    """Search for stocks"""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    results = db.search_stocks(query)
    return jsonify(results)


# API endpoints for background tasks
@app.route('/api/task/status')
def get_task_status():
    """Get current task status"""
    return jsonify(task_status)


@app.route('/api/fetch-stocks', methods=['POST'])
def fetch_stocks():
    """Fetch stock lists from NSE and BSE"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Fetching stock lists'
        task_status['progress'] = 0
        task_status['message'] = 'Fetching NSE stocks...'

        try:
            results = stock_fetcher.fetch_and_save_all()
            task_status['results'] = results
            task_status['message'] = f"Fetched {results['total']} stocks"
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False
            task_status['progress'] = 100

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/download-data', methods=['POST'])
def download_data():
    """Download OHLCV data for all stocks"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    exchange = request.json.get('exchange', None)

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Downloading OHLCV data'
        task_status['progress'] = 0
        task_status['message'] = 'Starting download...'

        def progress_callback(info):
            task_status['progress'] = int(info['current'] / info['total'] * 100)
            task_status['message'] = f"Downloading {info['symbol']} ({info['current']}/{info['total']})"

        try:
            results = ohlcv_downloader.download_all_stocks(
                exchange=exchange,
                progress_callback=progress_callback
            )
            task_status['results'] = results
            task_status['message'] = f"Downloaded data for {results['success']} stocks"
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False
            task_status['progress'] = 100

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/calculate-indicators', methods=['POST'])
def calculate_indicators():
    """Calculate technical indicators for all stocks"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Calculating indicators'
        task_status['progress'] = 0
        task_status['message'] = 'Calculating indicators...'

        try:
            results = indicator_calc.calculate_for_all_stocks()
            task_status['results'] = results
            task_status['message'] = f"Calculated indicators for {results['success']} stocks"
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False
            task_status['progress'] = 100

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/detect-circuits', methods=['POST'])
def detect_circuits():
    """Detect UC/LC events for all stocks"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Detecting circuits'
        task_status['progress'] = 0
        task_status['message'] = 'Detecting circuits...'

        try:
            results = circuit_detector.detect_for_all_stocks()
            task_status['results'] = results
            task_status['message'] = f"Found {results['total_uc']} UC and {results['total_lc']} LC events"
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False
            task_status['progress'] = 100

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/train-models', methods=['POST'])
def train_models():
    """Train prediction models"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Training models'
        task_status['progress'] = 0
        task_status['message'] = 'Training UC prediction model...'

        try:
            uc_success, duration_success = predictor.train_all_models()
            task_status['results'] = {
                'uc_model': 'success' if uc_success else 'failed',
                'duration_model': 'success' if duration_success else 'failed'
            }
            task_status['message'] = 'Models trained successfully'
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False
            task_status['progress'] = 100

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/run-full-pipeline', methods=['POST'])
def run_full_pipeline():
    """Run full data pipeline: fetch, download, calculate, detect, train"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Full pipeline'
        task_status['progress'] = 0

        try:
            # Step 1: Fetch stocks
            task_status['message'] = 'Step 1/5: Fetching stock lists...'
            stock_fetcher.fetch_and_save_all()
            task_status['progress'] = 20

            # Step 2: Download data
            task_status['message'] = 'Step 2/5: Downloading OHLCV data...'
            ohlcv_downloader.download_all_stocks()
            task_status['progress'] = 50

            # Step 3: Calculate indicators
            task_status['message'] = 'Step 3/5: Calculating indicators...'
            indicator_calc.calculate_for_all_stocks()
            task_status['progress'] = 70

            # Step 4: Detect circuits
            task_status['message'] = 'Step 4/5: Detecting circuits...'
            circuit_detector.detect_for_all_stocks()
            task_status['progress'] = 85

            # Step 5: Train models
            task_status['message'] = 'Step 5/5: Training models...'
            predictor.train_all_models()
            task_status['progress'] = 100

            task_status['message'] = 'Pipeline completed successfully!'

        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/stocks-at-circuit')
def stocks_at_circuit():
    """Get stocks currently at UC or LC"""
    event_type = request.args.get('type', 'UC')
    stocks = circuit_detector.get_stocks_at_circuit(event_type=event_type)
    return jsonify(stocks)


# New routes for enhanced features
@app.route('/breakouts')
def breakouts():
    """Breakout Scanner - Find high-probability breakout candidates"""
    min_strength = request.args.get('min_strength', 50, type=int)
    signal_type = request.args.get('type', None)

    today = date.today().isoformat()
    signals = db.get_breakout_signals(min_strength=min_strength, date=today, signal_type=signal_type)

    return render_template('breakouts.html',
                           signals=signals.to_dict('records') if not signals.empty else [],
                           min_strength=min_strength,
                           signal_type=signal_type)


@app.route('/momentum')
def momentum():
    """Momentum Ranking - Stocks ranked by momentum score"""
    exchange = request.args.get('exchange', None)
    limit = request.args.get('limit', 100, type=int)

    stocks = db.get_top_momentum_stocks(limit=limit, exchange=exchange)

    return render_template('momentum.html',
                           stocks=stocks.to_dict('records') if not stocks.empty else [],
                           exchange=exchange,
                           limit=limit)


@app.route('/deals')
def bulk_block_deals():
    """Bulk/Block Deals - Recent large deals"""
    days = request.args.get('days', 7, type=int)
    deal_type = request.args.get('type', None)

    start_date = (date.today() - timedelta(days=days)).isoformat()
    deals = db.get_bulk_block_deals(start_date=start_date, deal_type=deal_type)

    return render_template('deals.html',
                           deals=deals.to_dict('records') if not deals.empty else [],
                           days=days,
                           deal_type=deal_type)


@app.route('/high-delivery')
def high_delivery():
    """High Delivery Stocks - Stocks with high delivery percentage"""
    min_pct = request.args.get('min_pct', 50, type=float)

    stocks = db.get_high_delivery_stocks(min_delivery_pct=min_pct)

    return render_template('high_delivery.html',
                           stocks=stocks.to_dict('records') if not stocks.empty else [],
                           min_pct=min_pct)


@app.route('/penny-stocks')
def penny_stocks():
    """Penny Stocks - Stocks under Rs 20"""
    stocks = db.get_penny_stocks()

    return render_template('penny_stocks.html',
                           stocks=stocks.to_dict('records') if not stocks.empty else [])


@app.route('/fno')
def fno_stocks():
    """F&O Stocks - Stocks in Futures & Options"""
    stocks = db.get_fno_stocks()

    return render_template('fno_stocks.html',
                           stocks=stocks.to_dict('records') if not stocks.empty else [])


# API endpoints for new features
@app.route('/api/scan-breakouts', methods=['POST'])
def scan_breakouts():
    """Scan for breakout signals"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    exchange = request.json.get('exchange', None)
    min_strength = request.json.get('min_strength', 50)

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Scanning breakouts'
        task_status['progress'] = 0
        task_status['message'] = 'Scanning for breakout patterns...'

        try:
            signals = breakout_scanner.scan_all_stocks(
                exchange=exchange,
                min_strength=min_strength,
                progress_callback=lambda msg: setattr(task_status, 'message', msg) or None
            )
            task_status['results'] = {'count': len(signals)}
            task_status['message'] = f"Found {len(signals)} breakout signals"
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False
            task_status['progress'] = 100

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/update-fundamentals', methods=['POST'])
def update_fundamentals():
    """Update stock fundamentals (market cap, 52W, etc.)"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    exchange = request.json.get('exchange', None)

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Updating fundamentals'
        task_status['progress'] = 0
        task_status['message'] = 'Fetching fundamentals from yfinance...'

        def progress_callback(msg):
            task_status['message'] = msg

        try:
            results = enhanced_fetcher.update_all_fundamentals(
                exchange=exchange,
                progress_callback=progress_callback
            )
            task_status['results'] = results
            task_status['message'] = f"Updated {results['updated']} stocks"
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False
            task_status['progress'] = 100

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/calculate-extended', methods=['POST'])
def calculate_extended():
    """Calculate extended indicators (EMA, Bollinger, ADX, momentum)"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    exchange = request.json.get('exchange', None)

    def run_task():
        task_status['running'] = True
        task_status['current_task'] = 'Calculating extended indicators'
        task_status['progress'] = 0
        task_status['message'] = 'Calculating EMAs, Bollinger, ADX...'

        def progress_callback(msg):
            task_status['message'] = msg

        try:
            results = extended_calc.calculate_for_all_stocks(
                exchange=exchange,
                progress_callback=progress_callback
            )
            task_status['results'] = results
            task_status['message'] = f"Calculated for {results['calculated']} stocks"
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False
            task_status['progress'] = 100

    thread = threading.Thread(target=run_task)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/export/<export_type>')
def export_data(export_type):
    """Export data to Excel/CSV"""
    format_type = request.args.get('format', 'excel')
    exchange = request.args.get('exchange', None)

    try:
        if export_type == 'daily':
            filepath = exporter.export_daily_report(format=format_type)
        elif export_type == 'stocks':
            filepath = exporter.export_stock_list(exchange=exchange, format=format_type)
        elif export_type == 'breakouts':
            filepath = exporter.export_breakout_signals(format=format_type)
        elif export_type == 'momentum':
            filepath = exporter.export_momentum_ranking(exchange=exchange, format=format_type)
        elif export_type == 'penny':
            filepath = exporter.export_penny_stocks(format=format_type)
        elif export_type == 'fno':
            filepath = exporter.export_fno_stocks(format=format_type)
        elif export_type == 'deals':
            filepath = exporter.export_bulk_block_deals(format=format_type)
        else:
            return jsonify({'error': f'Unknown export type: {export_type}'}), 400

        return jsonify({'status': 'success', 'filepath': filepath})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stock-comprehensive/<symbol>')
def get_comprehensive_stock(symbol):
    """Get comprehensive stock data"""
    data = db.get_comprehensive_stock_data(symbol.upper())
    if not data:
        return jsonify({'error': 'Stock not found'}), 404
    return jsonify(data)


@app.route('/api/momentum-ranking')
def get_momentum_ranking():
    """Get momentum ranking"""
    limit = request.args.get('limit', 100, type=int)
    exchange = request.args.get('exchange', None)

    stocks = db.get_top_momentum_stocks(limit=limit, exchange=exchange)
    return jsonify(stocks.to_dict('records') if not stocks.empty else [])


@app.route('/api/breakout-signals')
def get_breakout_signals():
    """Get breakout signals"""
    min_strength = request.args.get('min_strength', 50, type=int)
    signal_type = request.args.get('type', None)

    today = date.today().isoformat()
    signals = db.get_breakout_signals(min_strength=min_strength, date=today, signal_type=signal_type)
    return jsonify(signals.to_dict('records') if not signals.empty else [])


@app.route('/api/high-delivery')
def get_high_delivery():
    """Get high delivery stocks"""
    min_pct = request.args.get('min_pct', 50, type=float)

    stocks = db.get_high_delivery_stocks(min_delivery_pct=min_pct)
    return jsonify(stocks.to_dict('records') if not stocks.empty else [])


@app.route('/api/bulk-block-deals')
def get_bulk_block_deals():
    """Get bulk/block deals"""
    days = request.args.get('days', 7, type=int)
    deal_type = request.args.get('type', None)

    start_date = (date.today() - timedelta(days=days)).isoformat()
    deals = db.get_bulk_block_deals(start_date=start_date, deal_type=deal_type)
    return jsonify(deals.to_dict('records') if not deals.empty else [])


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', message='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', message='Server error'), 500


if __name__ == '__main__':
    # Initialize database
    db.init_database()

    print("=" * 50)
    print("Stock Circuit Predictor")
    print("=" * 50)
    print(f"Running on http://127.0.0.1:5000")
    print("=" * 50)

    app.run(debug=DEBUG, host='0.0.0.0', port=5000)
