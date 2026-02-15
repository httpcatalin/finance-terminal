from .lexer import Token, Lexer

class ASTNode:
    pass

class AnalyzeStmt(ASTNode):
    def __init__(self, asset_type, ticker, period):
        self.asset_type = asset_type
        self.ticker = ticker
        self.period = period

    def __repr__(self):
        return f"AnalyzeStmt(asset_type='{self.asset_type}', ticker='{self.ticker}', period='{self.period}')"

class CalculateStmt(ASTNode):
    def __init__(self, calc_type, ticker, params):
        self.calc_type = calc_type
        self.ticker = ticker
        self.params = params

    def __repr__(self):
        return f"CalculateStmt(calc_type='{self.calc_type}', ticker='{self.ticker}', params={self.params})"

class ShowStmt(ASTNode):
    def __init__(self, show_type, ticker):
        self.show_type = show_type
        self.ticker = ticker

    def __repr__(self):
        return f"ShowStmt(show_type='{self.show_type}', ticker='{self.ticker}')"

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.current_token = self.tokens[0] if self.tokens else None

    def advance(self):
        self.pos += 1
        if self.pos > len(self.tokens) - 1:
            self.current_token = None
        else:
            self.current_token = self.tokens[self.pos]

    def parse(self):
        statements = []
        while self.current_token is not None:
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
            else:
                self.advance()
        return statements

    def parse_statement(self):
        if self.current_token and self.current_token.type in ['ANALYZE', 'CALCULATE', 'SHOW']:
            if self.current_token.type == 'ANALYZE':
                return self.parse_analyze()
            elif self.current_token.type == 'CALCULATE':
                return self.parse_calculate()
            elif self.current_token.type == 'SHOW':
                return self.parse_show()
        return None

    def parse_analyze(self):
        self.advance()
        asset_type = self.current_token.value if self.current_token else None
        self.advance()
        ticker = self.current_token.value if self.current_token else None
        self.advance()
        self.advance()
        period = self.current_token.value if self.current_token and self.current_token.type == 'PERIOD' else None
        self.advance()
        return AnalyzeStmt(asset_type, ticker, period)

    def parse_calculate(self):
        self.advance()
        calc_type = self.current_token.value
        self.advance()
        self.advance()
        ticker = self.current_token.value
        self.advance()
        params = {}
        while self.current_token and self.current_token.type == 'IDENTIFIER':
            key = self.current_token.value
            self.advance()
            value = self.current_token.value if self.current_token.type in ['NUMBER', 'STRING'] else None
            self.advance()
            params[key] = value
        return CalculateStmt(calc_type, ticker, params)

    def parse_show(self):
        self.advance()
        show_type = self.current_token.value
        self.advance()
        self.advance()
        ticker = self.current_token.value
        self.advance()
        return ShowStmt(show_type, ticker)