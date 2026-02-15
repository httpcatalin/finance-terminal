import yfinance as yf
import pandas as pd
import numpy as np
from fredapi import Fred
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

def get_stock_prices(ticker, period='1y'):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period)
        return data
    except Exception as e:
        logging.error(f"Error fetching stock prices for {ticker}: {e}")
        return None

def get_historical_volatility(ticker, period='1y'):
    try:
        data = get_stock_prices(ticker, period)
        if data is None or data.empty:
            return None
        returns = data['Close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) 
        return volatility
    except Exception as e:
        logging.error(f"Error calculating volatility for {ticker}: {e}")
        return None

def get_futures_prices(symbol):
    try:
        futures = yf.Ticker(symbol)
        data = futures.history(period='1y')
        return data
    except Exception as e:
        logging.error(f"Error fetching futures prices for {symbol}: {e}")
        return None

def get_risk_free_rate():
    try:
        fred = Fred(api_key=os.getenv('FRED_API_KEY'))
        data = fred.get_series('DGS10')
        return data.iloc[-1] if not data.empty else None
    except Exception as e:
        logging.error(f"Error fetching risk-free rate: {e}")
        return None

def get_bond_yields():
    try:
        fred = Fred(api_key=os.getenv('FRED_API_KEY'))
        data = fred.get_series('DGS10')
        return data
    except Exception as e:
        logging.error(f"Error fetching bond yields: {e}")
        return None