import re

KEYWORDS = {
    'analyze': 'ANALYZE',
    'calculate': 'CALCULATE',
    'show': 'SHOW',
    'stock': 'STOCK',
    'option': 'OPTION',
    'future': 'FUTURE',
    'bond': 'BOND',
    'for': 'FOR',
    'dcf': 'DCF',
    'black_scholes': 'BLACK_SCHOLES',
    'futures_price': 'FUTURES_PRICE',
    'bond_price': 'BOND_PRICE',
    'income_statement': 'INCOME_STATEMENT',
    'balance_sheet': 'BALANCE_SHEET',
    'cash_flow': 'CASH_FLOW',
    'prices': 'PRICES',
    'volatility': 'VOLATILITY',
    'moat': 'MOAT',
    'news': 'NEWS',
    'limit': 'LIMIT',
}

class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f'Token({self.type}, {self.value})'

class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.current_char = self.text[0] if self.text else None

    def advance(self):
        self.pos += 1
        if self.pos > len(self.text) - 1:
            self.current_char = None
        else:
            self.current_char = self.text[self.pos]

    def peek(self, offset=1):
        peek_pos = self.pos + offset
        if peek_pos > len(self.text) - 1:
            return None
        return self.text[peek_pos]

    def skip_whitespace(self):
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def read_identifier(self):
        result = ''
        while self.current_char is not None and (self.current_char.isalnum() or self.current_char == '_'):
            result += self.current_char
            self.advance()
        return result

    def read_period(self):
        result = ''
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char in 'YM'):
            result += self.current_char
            self.advance()
        return result

    def read_number(self):
        result = ''
        dot_count = 0
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == '.'):
            if self.current_char == '.':
                dot_count += 1
                if dot_count > 1:
                    break
            result += self.current_char
            self.advance()

        # Support percent-style literals like 5% by normalizing to decimal.
        if self.current_char == '%':
            self.advance()
            try:
                return str(float(result) / 100.0)
            except ValueError:
                return result
        return result

    def _try_read_date(self):
        """
        If the next characters match YYYY-MM-DD, consume and return the string.
        Otherwise return None and leave position unchanged.
        """
        saved_pos  = self.pos
        saved_char = self.current_char
        result = ''
        # Read up to 10 chars without advancing permanently
        lookahead = self.text[self.pos:self.pos + 10]
        import re
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', lookahead):
            # Consume exactly 10 characters
            for _ in range(10):
                result += self.current_char
                self.advance()
            return result
        return None

    def tokenize(self):
        tokens = []
        while self.current_char is not None:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue
            if self.current_char.isalpha() or self.current_char == '_':
                identifier = self.read_identifier()
                token_type = KEYWORDS.get(identifier, 'IDENTIFIER')
                tokens.append(Token(token_type, identifier))
                continue
            if self.current_char.isdigit():
                # Check for ISO date YYYY-MM-DD before treating as number/period
                date_val = self._try_read_date()
                if date_val is not None:
                    tokens.append(Token('IDENTIFIER', date_val))
                    continue
                if self.peek() and self.peek() in 'YM':
                    tokens.append(Token('PERIOD', self.read_period()))
                else:
                    tokens.append(Token('NUMBER', self.read_number()))
                continue
            if self.current_char == '"':
                self.advance()
                string = ''
                while self.current_char is not None and self.current_char != '"':
                    string += self.current_char
                    self.advance()
                self.advance()
                tokens.append(Token('STRING', string))
                continue
            tokens.append(Token('UNKNOWN', self.current_char))
            self.advance()
        return tokens