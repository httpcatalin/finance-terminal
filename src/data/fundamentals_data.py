import yfinance as yf
import logging

logging.basicConfig(level=logging.INFO)

def get_income_statement(ticker):
    try:
        stock = yf.Ticker(ticker)
        income_stmt = stock.financials
        return income_stmt
    except Exception as e:
        logging.error(f"Error fetching income statement for {ticker}: {e}")
        return None

def get_balance_sheet(ticker):
    try:
        stock = yf.Ticker(ticker)
        balance_sheet = stock.balance_sheet
        return balance_sheet
    except Exception as e:
        logging.error(f"Error fetching balance sheet for {ticker}: {e}")
        return None

def get_cash_flow(ticker):
    try:
        stock = yf.Ticker(ticker)
        cash_flow = stock.cashflow
        return cash_flow
    except Exception as e:
        logging.error(f"Error fetching cash flow for {ticker}: {e}")
        return None
