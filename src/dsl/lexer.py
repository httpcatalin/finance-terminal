import re

import re

KEYWORDS = {
    'analyze': 'ANALYZE',
    'calculate': 'CALCULATE',
    'show': 'SHOW',
    'stock': 'STOCK',
    'option': 'OPTION',
    'future': 'FUTURE',
    'bond': 'BOND',
    'portfolio': 'PORTFOLIO',
    'for': 'FOR',
    'dcf': 'DCF',
    'black_scholes': 'BLACK_SCHOLES',
    'futures_price': 'FUTURES_PRICE',
    'bond_price': 'BOND_PRICE',
    'volatility': 'VOLATILITY',
    'sharpe_ratio': 'SHARPE_RATIO',
    'var': 'VAR',
    'correlation': 'CORRELATION',
    'beta': 'BETA',
    'monte_carlo': 'MONTE_CARLO',
    'income_statement': 'INCOME_STATEMENT',
    'balance_sheet': 'BALANCE_SHEET',
    'cash_flow': 'CASH_FLOW',
    'prices': 'PRICES',
    'ratios': 'RATIOS',
    'chart': 'CHART',
    'statistics': 'STATISTICS',
    'correlation_matrix': 'CORRELATION_MATRIX',
    'portfolio_performance': 'PORTFOLIO_PERFORMANCE',
    'int': 'INT',
    'float': 'FLOAT',
    'string': 'STRING',
    'bool': 'BOOL',
    'date': 'DATE',
    'currency': 'CURRENCY',
    'array': 'ARRAY',
    'dict': 'DICT',
    'if': 'IF',
    'else': 'ELSE',
    'while': 'WHILE',
    'for': 'FOR',
    'def': 'DEF',
    'return': 'RETURN',
    'true': 'TRUE',
    'false': 'FALSE',
    'with': 'WITH',
    'filter': 'FILTER',
    'group': 'GROUP',
    'by': 'BY',
    'where': 'WHERE',
    'as': 'AS',
    'table': 'TABLE',
    'chart': 'CHART',
    'json': 'JSON',
    'csv': 'CSV',
    'using': 'USING',
    'method': 'METHOD',
    'iterations': 'ITERATIONS',
    'in': 'IN',
    'days': 'DAYS',
    'weeks': 'WEEKS',
    'months': 'MONTHS',
    'years': 'YEARS'
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
        while self.current_char is not None and (self.current_char.isdigit() or self.current_char == '.'):
            result += self.current_char
            self.advance()
        return result

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
                tokens.append(Token('NUMBER', self.read_number()))
                continue
            if self.current_char == '"':
                self.advance()
                string = ''
                while self.current_char is not None and self.current_char != '"':
                    if self.current_char == '\\':
                        self.advance()
                        if self.current_char == 'n':
                            string += '\n'
                        elif self.current_char == 't':
                            string += '\t'
                        elif self.current_char == '"':
                            string += '"'
                        elif self.current_char == '\\':
                            string += '\\'
                        else:
                            string += self.current_char
                    else:
                        string += self.current_char
                    self.advance()
                self.advance()
                tokens.append(Token('STRING', string))
                continue
            if self.current_char == "'":
                self.advance()
                string = ''
                while self.current_char is not None and self.current_char != "'":
                    if self.current_char == '\\':
                        self.advance()
                        if self.current_char == 'n':
                            string += '\n'
                        elif self.current_char == 't':
                            string += '\t'
                        elif self.current_char == "'":
                            string += "'"
                        elif self.current_char == '\\':
                            string += '\\'
                        else:
                            string += self.current_char
                    else:
                        string += self.current_char
                    self.advance()
                self.advance()
                tokens.append(Token('STRING', string))
                continue
            # Two-character operators
            if self.current_char == '=' and self.peek() == '=':
                self.advance()
                self.advance()
                tokens.append(Token('EQ', '=='))
                continue
            if self.current_char == '!' and self.peek() == '=':
                self.advance()
                self.advance()
                tokens.append(Token('NE', '!='))
                continue
            if self.current_char == '<' and self.peek() == '=':
                self.advance()
                self.advance()
                tokens.append(Token('LE', '<='))
                continue
            if self.current_char == '>' and self.peek() == '=':
                self.advance()
                self.advance()
                tokens.append(Token('GE', '>='))
                continue
            if self.current_char == '&' and self.peek() == '&':
                self.advance()
                self.advance()
                tokens.append(Token('AND', '&&'))
                continue
            if self.current_char == '|' and self.peek() == '|':
                self.advance()
                self.advance()
                tokens.append(Token('OR', '||'))
                continue
            # Single-character operators and symbols
            if self.current_char == '+':
                tokens.append(Token('PLUS', '+'))
                self.advance()
                continue
            if self.current_char == '-':
                tokens.append(Token('MINUS', '-'))
                self.advance()
                continue
            if self.current_char == '*':
                tokens.append(Token('MUL', '*'))
                self.advance()
                continue
            if self.current_char == '/':
                tokens.append(Token('DIV', '/'))
                self.advance()
                continue
            if self.current_char == '%':
                tokens.append(Token('MOD', '%'))
                self.advance()
                continue
            if self.current_char == '^':
                tokens.append(Token('POW', '^'))
                self.advance()
                continue
            if self.current_char == '=':
                tokens.append(Token('ASSIGN', '='))
                self.advance()
                continue
            if self.current_char == '<':
                tokens.append(Token('LT', '<'))
                self.advance()
                continue
            if self.current_char == '>':
                tokens.append(Token('GT', '>'))
                self.advance()
                continue
            if self.current_char == '!':
                tokens.append(Token('NOT', '!'))
                self.advance()
                continue
            if self.current_char == '.':
                tokens.append(Token('DOT', '.'))
                self.advance()
                continue
            if self.current_char == ',':
                tokens.append(Token('COMMA', ','))
                self.advance()
                continue
            if self.current_char == ':':
                tokens.append(Token('COLON', ':'))
                self.advance()
                continue
            if self.current_char == ';':
                tokens.append(Token('SEMICOLON', ';'))
                self.advance()
                continue
            if self.current_char == '(':
                tokens.append(Token('LPAREN', '('))
                self.advance()
                continue
            if self.current_char == ')':
                tokens.append(Token('RPAREN', ')'))
                self.advance()
                continue
            if self.current_char == '[':
                tokens.append(Token('LBRACKET', '['))
                self.advance()
                continue
            if self.current_char == ']':
                tokens.append(Token('RBRACKET', ']'))
                self.advance()
                continue
            if self.current_char == '{':
                tokens.append(Token('LBRACE', '{'))
                self.advance()
                continue
            if self.current_char == '}':
                tokens.append(Token('RBRACE', '}'))
                self.advance()
                continue
            tokens.append(Token('UNKNOWN', self.current_char))
            self.advance()
        return tokens