from .parser import AnalyzeStmt, CalculateStmt, ShowStmt
from ..data.market_data import get_stock_prices, get_historical_volatility
from ..data.fundamentals_data import get_income_statement, get_balance_sheet, get_cash_flow
from ..models.stocks import Stock
from ..models.options import Option
from ..models.futures import Futures
from ..models.bonds import Bond

class Interpreter:
    def __init__(self, ast):
        self.ast = ast

    def execute(self):
        for node in self.ast:
            self.visit(node)

    def visit(self, node):
        if isinstance(node, AnalyzeStmt):
            self.execute_analyze(node)
        elif isinstance(node, CalculateStmt):
            self.execute_calculate(node)
        elif isinstance(node, ShowStmt):
            self.execute_show(node)

    def execute_analyze(self, node):
        try:
            if node.asset_type == 'stock':
                prices = get_stock_prices(node.ticker, node.period.lower())
                vol = get_historical_volatility(node.ticker, node.period.lower())
                if prices is not None:
                    print(f"Prices for {node.ticker}: Latest close {prices['Close'].iloc[-1]:.2f}")
                else:
                    print(f"Failed to fetch prices for {node.ticker}")
                if vol is not None:
                    print(f"Volatility for {node.ticker}: {vol:.2%}")
                else:
                    print(f"Failed to calculate volatility for {node.ticker}")
        except Exception as e:
            print(f"Error in analyze: {e}")

    def execute_calculate(self, node):
        try:
            if node.calc_type == 'dcf':
                stock = Stock(node.ticker)
                growth = float(node.params.get('growth', 0.05))
                discount = float(node.params.get('discount', 0.1))
                years = int(node.params.get('years', 5))
                print(f"DCF for {node.ticker}: Placeholder with growth {growth}, discount {discount}, years {years}")
        except Exception as e:
            print(f"Error in calculate: {e}")

    def execute_show(self, node):
        try:
            if node.show_type == 'income_statement':
                stmt = get_income_statement(node.ticker)
                if stmt is not None:
                    print(f"Income Statement for {node.ticker}: {stmt.head()}")
                else:
                    print(f"Failed to fetch income statement for {node.ticker}")
            elif node.show_type == 'prices':
                prices = get_stock_prices(node.ticker)
                if prices is not None:
                    print(f"Prices for {node.ticker}: Latest {prices['Close'].iloc[-1]:.2f}")
                else:
                    print(f"Failed to fetch prices for {node.ticker}")
        except Exception as e:
            print(f"Error in show: {e}")