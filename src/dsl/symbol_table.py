class SymbolTable:
    def __init__(self):
        self.symbols = {}

    def define(self, name, value):
        self.symbols[name] = value

    def lookup(self, name):
        return self.symbols.get(name, None)