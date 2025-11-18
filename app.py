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
from functools import lru_cache
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SECRET_KEY, DEBUG
from database.db_manager import DatabaseManager
from data.stock_fetcher import StockFetcher
from data.ohlcv_downloader import OHLCVDownloader
from analysis.indicators import IndicatorCalculator
from analysis.circuit_detector import CircuitDetector
from analysis.predictor import CircuitPredictor

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Initialize components
db = DatabaseManager()
stock_fetcher = StockFetcher()
ohlcv_downloader = OHLCVDownloader()
indicator_calc = IndicatorCalculator()
circuit_detector = CircuitDetector()
predictor = CircuitPredictor()

# Thread-safe task status with lock
class TaskStatus:
    def __init__(self):
        self._lock = threading.Lock()
        self._status = {
            'running': False,
            'current_task': None,
            'progress': 0,
            'message': '',
            'results': None
        }

    def get(self):
        with self._lock:
            return self._status.copy()

    def update(self, **kwargs):
        with self._lock:
            self._status.update(kwargs)

    def __getitem__(self, key):
        with self._lock:
            return self._status[key]

    def __setitem__(self, key, value):
        with self._lock:
            self._status[key] = value

task_status = TaskStatus()

# Simple cache with TTL
class SimpleCache:
    def __init__(self):
        self._cache = {}
        self._timestamps = {}

    def get(self, key, ttl=60):
        if key in self._cache:
            if time.time() - self._timestamps[key] < ttl:
                return self._cache[key]
        return None

    def set(self, key, value):
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def clear(self):
        self._cache.clear()
        self._timestamps.clear()

cache = SimpleCache()


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
    # Get statistics with caching
    nse_count = cache.get('nse_count', ttl=300)
    if nse_count is None:
        nse_count = db.get_stock_count(exchange='NSE')
        cache.set('nse_count', nse_count)

    bse_count = cache.get('bse_count', ttl=300)
    if bse_count is None:
        bse_count = db.get_stock_count(exchange='BSE')
        cache.set('bse_count', bse_count)

    total_count = nse_count + bse_count

    # Get today's circuits
    today_uc = db.get_today_circuits(event_type='UC')
    today_lc = db.get_today_circuits(event_type='LC')

    # Get download stats with caching
    download_stats = cache.get('download_stats', ttl=300)
    if download_stats is None:
        download_stats = db.get_download_stats()
        cache.set('download_stats', download_stats)

    # Get circuit statistics with caching
    circuit_stats = cache.get('circuit_stats', ttl=300)
    if circuit_stats is None:
        circuit_stats = circuit_detector.get_circuit_statistics()
        cache.set('circuit_stats', circuit_stats)

    # Get top UC candidates with caching
    top_candidates = cache.get('top_candidates', ttl=120)
    if top_candidates is None:
        try:
            candidates = predictor.screen_for_uc(min_probability=30)[:10]
            top_candidates = candidates
            cache.set('top_candidates', top_candidates)
        except:
            top_candidates = []

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
                           task_status=task_status.get())


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
    return jsonify(task_status.get())


@app.route('/api/fetch-stocks', methods=['POST'])
def fetch_stocks():
    """Fetch stock lists from NSE and BSE"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status.update(
            running=True,
            current_task='Fetching stock lists',
            progress=0,
            message='Fetching NSE and BSE stocks...'
        )

        try:
            results = stock_fetcher.fetch_and_save_all()
            task_status.update(
                results=results,
                message=f"Fetched {results['total']} stocks (NSE: {results['nse']}, BSE: {results['bse']})"
            )
            # Clear cache to refresh counts
            cache.clear()
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status.update(running=False, progress=100)

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/download-data', methods=['POST'])
def download_data():
    """Download OHLCV data for all stocks"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    exchange = request.json.get('exchange', None) if request.json else None

    def run_task():
        task_status.update(
            running=True,
            current_task='Downloading OHLCV data',
            progress=0,
            message='Starting download...'
        )

        def progress_callback(info):
            task_status.update(
                progress=int(info['current'] / info['total'] * 100),
                message=f"Downloading {info['symbol']} ({info['current']}/{info['total']})"
            )

        try:
            results = ohlcv_downloader.download_all_stocks(
                exchange=exchange,
                progress_callback=progress_callback
            )
            task_status.update(
                results=results,
                message=f"Downloaded data for {results['success']} stocks ({results.get('failed', 0)} failed)"
            )
            cache.clear()
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status.update(running=False, progress=100)

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/calculate-indicators', methods=['POST'])
def calculate_indicators():
    """Calculate technical indicators for all stocks"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status.update(
            running=True,
            current_task='Calculating indicators',
            progress=0,
            message='Calculating technical indicators...'
        )

        try:
            results = indicator_calc.calculate_for_all_stocks()
            task_status.update(
                results=results,
                message=f"Calculated indicators for {results['success']} stocks"
            )
            cache.clear()
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status.update(running=False, progress=100)

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/detect-circuits', methods=['POST'])
def detect_circuits():
    """Detect UC/LC events for all stocks"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status.update(
            running=True,
            current_task='Detecting circuits',
            progress=0,
            message='Detecting UC/LC circuits...'
        )

        try:
            results = circuit_detector.detect_for_all_stocks()
            task_status.update(
                results=results,
                message=f"Found {results['total_uc']} UC and {results['total_lc']} LC events"
            )
            cache.clear()
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status.update(running=False, progress=100)

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/train-models', methods=['POST'])
def train_models():
    """Train prediction models"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status.update(
            running=True,
            current_task='Training models',
            progress=0,
            message='Training ML prediction models...'
        )

        try:
            uc_success, duration_success = predictor.train_all_models()
            task_status.update(
                results={
                    'uc_model': 'success' if uc_success else 'failed',
                    'duration_model': 'success' if duration_success else 'failed'
                },
                message='Models trained successfully!' if uc_success else 'Model training completed with issues'
            )
            cache.clear()
        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status.update(running=False, progress=100)

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/run-full-pipeline', methods=['POST'])
def run_full_pipeline():
    """Run full data pipeline: fetch, download, calculate, detect, train"""
    if task_status['running']:
        return jsonify({'error': 'A task is already running'}), 400

    def run_task():
        task_status.update(
            running=True,
            current_task='Full pipeline',
            progress=0
        )

        try:
            # Step 1: Fetch stocks
            task_status['message'] = 'Step 1/5: Fetching stock lists from NSE & BSE...'
            fetch_results = stock_fetcher.fetch_and_save_all()
            task_status['progress'] = 20

            # Step 2: Download data
            task_status['message'] = 'Step 2/5: Downloading OHLCV price data...'
            ohlcv_downloader.download_all_stocks()
            task_status['progress'] = 50

            # Step 3: Calculate indicators
            task_status['message'] = 'Step 3/5: Calculating technical indicators...'
            indicator_calc.calculate_for_all_stocks()
            task_status['progress'] = 70

            # Step 4: Detect circuits
            task_status['message'] = 'Step 4/5: Detecting UC/LC circuits...'
            circuit_results = circuit_detector.detect_for_all_stocks()
            task_status['progress'] = 85

            # Step 5: Train models
            task_status['message'] = 'Step 5/5: Training prediction models...'
            predictor.train_all_models()
            task_status['progress'] = 100

            task_status['message'] = f"Pipeline completed! Fetched {fetch_results['total']} stocks, found {circuit_results['total_uc']} UC events"

            # Clear all caches
            cache.clear()

        except Exception as e:
            task_status['message'] = f"Error: {str(e)}"
        finally:
            task_status['running'] = False

    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    return jsonify({'status': 'started'})


@app.route('/api/stocks-at-circuit')
def stocks_at_circuit():
    """Get stocks currently at UC or LC"""
    event_type = request.args.get('type', 'UC')
    stocks = circuit_detector.get_stocks_at_circuit(event_type=event_type)
    return jsonify(stocks)


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
