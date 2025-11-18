# Stock Circuit Predictor

A local-only application for analyzing NSE and BSE stocks to predict Upper Circuit (UC) and Lower Circuit (LC) events.

## Features

- **UC/LC Detection**: Identifies stocks at Upper Circuit (close = high within 1%) or Lower Circuit (close = low within 1%)
- **UC Prediction**: ML model predicts probability of stocks hitting UC tomorrow (0-100%)
- **UC to LC Duration**: Estimates how many days until a stock at UC hits LC
- **Technical Indicators**: Calculates RSI, MACD, Moving Averages, ATR, Volume Ratio, Support/Resistance
- **Complete Stock Universe**: Downloads and processes all NSE and BSE stocks
- **Web Interface**: Simple multi-page interface for analysis and screening
- **Local Storage**: All data stored locally in SQLite database
- **Resume Support**: Downloads can be interrupted and resumed

## Installation

1. Install Python 3.8 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Application

```bash
python run.py
```

Or:
```bash
python app.py
```

Then open your browser to: http://127.0.0.1:5000

### First Time Setup

1. Go to the **Data** page
2. Click **Run Full Pipeline** to:
   - Fetch stock lists from NSE and BSE
   - Download historical OHLCV data
   - Calculate technical indicators
   - Detect UC/LC events
   - Train prediction models

This process may take a while depending on your internet connection.

### Daily Usage

1. **Dashboard**: View overview, today's circuits, and top UC candidates
2. **UC Screener**: Filter stocks by UC probability threshold
3. **Stock Analysis**: Detailed view of any stock with predictions and history
4. **History**: View historical UC/LC events and patterns
5. **Data**: Update data and retrain models

## UC/LC Rules

These rules are used exactly as specified:

### Upper Circuit (UC)
A day is UC if: Close price equals High price within 1% tolerance

```
UC = |close - high| / high <= 0.01
```

### Lower Circuit (LC)
A day is LC if: Close price equals Low price within 1% tolerance

```
LC = |close - low| / low <= 0.01
```

## Technical Indicators

The system calculates these indicators for each stock:

- **Price Changes**: 1-day and 5-day percentage changes
- **Moving Averages**: 5-day, 20-day, 50-day
- **RSI**: 14-period Relative Strength Index
- **MACD**: 12/26/9 Moving Average Convergence Divergence
- **Volume Ratio**: Today's volume / 20-day average volume
- **ATR**: 14-period Average True Range
- **Support/Resistance**: 20-day low (support) and high (resistance)

## Project Structure

```
stockanalyser/
├── app.py                    # Main Flask application
├── run.py                    # Launcher script
├── config.py                 # Configuration settings
├── requirements.txt          # Python dependencies
├── database/
│   └── db_manager.py         # SQLite database operations
├── data/
│   ├── stock_fetcher.py      # Fetch NSE/BSE stock lists
│   └── ohlcv_downloader.py   # Download OHLCV data
├── analysis/
│   ├── indicators.py         # Technical indicators
│   ├── circuit_detector.py   # UC/LC detection
│   └── predictor.py          # ML predictions
├── templates/                # HTML templates
└── static/css/               # Stylesheets
```

## Configuration

Edit `config.py` to customize:

- `UC_TOLERANCE` / `LC_TOLERANCE`: Circuit detection tolerance (default: 0.01 = 1%)
- `DOWNLOAD_HISTORY_DAYS`: Days of historical data to download (default: 365)
- `RSI_PERIOD`, `MACD_*`, etc.: Technical indicator parameters

## Data Storage

All data is stored locally:

- `stock_data.db`: SQLite database with all stocks, prices, indicators, and events
- `stored_data/`: Intermediate data files
- `models/`: Trained ML models

## Troubleshooting

### No data showing
- Go to Data page and run the full pipeline
- Check if yfinance can access the internet

### Missing dependencies
```bash
pip install -r requirements.txt
```

### Database errors
- Delete `stock_data.db` and restart to reinitialize

## Disclaimer

This tool is for educational and research purposes only. It is not financial advice. Always do your own research before making investment decisions.

## License

MIT License
