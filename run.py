#!/usr/bin/env python3
"""
Stock Circuit Predictor - Launcher Script
Run this to start the application
"""
import os
import sys

def main():
    print("=" * 60)
    print("Stock Circuit Predictor")
    print("=" * 60)
    print()

    # Check if dependencies are installed
    try:
        import flask
        import yfinance
        import pandas
        import sklearn
    except ImportError as e:
        print("Missing dependencies. Please install them first:")
        print()
        print("  pip install -r requirements.txt")
        print()
        print(f"Error: {e}")
        sys.exit(1)

    # Initialize database
    from database.db_manager import DatabaseManager
    db = DatabaseManager()
    print("Database initialized.")

    # Check if we have stocks
    stock_count = db.get_stock_count()
    if stock_count == 0:
        print()
        print("No stocks found in database.")
        print("After starting the app, go to 'Data' page to fetch stocks and download data.")
    else:
        print(f"Found {stock_count} stocks in database.")

    print()
    print("Starting web server...")
    print()
    print("Open your browser and go to: http://127.0.0.1:5000")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()

    # Start the Flask app
    from app import app
    app.run(debug=True, host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
