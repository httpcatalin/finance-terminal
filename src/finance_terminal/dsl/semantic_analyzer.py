from .parser import AnalyzeStmt, CalculateStmt, ShowStmt
from .symbol_table import SymbolTable

class SemanticAnalyzer:
    def __init__(self, ast, symbol_table):
        self.ast = ast
        self.symbol_table = symbol_table
        self.errors = []

    def analyze(self):
        # daca o sa avem mai multe comenzi intr un rand (acum nu suporta)
        for node in self.ast:
            self.visit(node)

    def visit(self, node):
        if isinstance(node, AnalyzeStmt):
            self.visit_analyze(node)
        elif isinstance(node, CalculateStmt):
            self.visit_calculate(node)
        elif isinstance(node, ShowStmt):
            self.visit_show(node)

    def visit_analyze(self, node):
        if node.asset_type not in ['stock', 'option', 'future', 'bond']:
            self.errors.append(f"Invalid asset type: {node.asset_type}")
        if node.period not in ['1M', '6M', '1Y', '5Y']:
            self.errors.append(f"Invalid period: {node.period}")
        self.symbol_table.define(node.ticker, node.asset_type)

    def visit_calculate(self, node):
        if node.calc_type not in ['dcf', 'black_scholes', 'futures_price', 'bond_price']:
            self.errors.append(f"Invalid calculation type: {node.calc_type}")

    def visit_show(self, node):
        if node.show_type not in ['income_statement', 'balance_sheet', 'cash_flow', 'prices', 'volatility']:
            self.errors.append(f"Invalid show type: {node.show_type}")