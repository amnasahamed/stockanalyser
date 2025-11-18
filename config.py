"""
Configuration for Stock Circuit Predictor
"""
import os

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database
DATABASE_PATH = os.path.join(BASE_DIR, 'stock_data.db')

# Data storage
DATA_DIR = os.path.join(BASE_DIR, 'stored_data')
MODELS_DIR = os.path.join(BASE_DIR, 'models')

# Create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

# UC/LC Detection Rules
UC_TOLERANCE = 0.01  # 1% tolerance for Upper Circuit
LC_TOLERANCE = 0.01  # 1% tolerance for Lower Circuit

# Technical Indicator Parameters
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
ATR_PERIOD = 14
MA_SHORT = 5
MA_MEDIUM = 20
MA_LONG = 50
VOLUME_MA_PERIOD = 20
SUPPORT_RESISTANCE_PERIOD = 20

# Data download settings
DOWNLOAD_HISTORY_DAYS = 365  # 1 year of historical data
DOWNLOAD_BATCH_SIZE = 50  # Stocks per batch
DOWNLOAD_DELAY = 1  # Seconds between batches

# Flask settings
SECRET_KEY = 'stock-circuit-predictor-local-key'
DEBUG = True
