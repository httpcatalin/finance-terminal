import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.dsl.lexer import Lexer
from src.dsl.parser import Parser
from src.dsl.symbol_table import SymbolTable
from src.dsl.semantic_analyzer import SemanticAnalyzer
from src.dsl.interpreter import Interpreter

def main():
    if len(sys.argv) > 1:
        command = ' '.join(sys.argv[1:])
        process_command(command)
    else:
        print("Financial Terminal DSL")
        print("Enter DSL commands (type 'exit' to quit):")
        while True:
            try:
                command = input("> ").strip()
                if command.lower() == 'exit':
                    break
                if not command:
                    continue
                process_command(command)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

def process_command(command):
    try:
        lexer = Lexer(command)

        tokens = lexer.tokenize()

        parser = Parser(tokens)
        
        ast = parser.parse()
        print(f"AST: {ast}")

        symbol_table = SymbolTable()
        analyzer = SemanticAnalyzer(ast, symbol_table)
        analyzer.analyze()

        print(f"symbol table: {symbol_table.symbols}")

        if analyzer.errors:
            for error in analyzer.errors:
                print(f"Semantic Error: {error}")
            return

        interpreter = Interpreter(ast)
        interpreter.execute()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()