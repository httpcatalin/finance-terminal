import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.dsl.lexer import Lexer
from src.dsl.parser import Parser
from src.dsl.symbol_table import SymbolTable
from src.dsl.semantic_analyzer import SemanticAnalyzer
from src.dsl.interpreter import Interpreter

# New command system
from src.cli.command_registry import tokenise
from src.cli.commands import registry
from src.cli.session import Session
from src.data.cache import DataCache

# Module-level singletons
_session = Session()
_cache = DataCache()

# Commands handled by the new registry (upper-cased first token)
_NEW_COMMANDS = {spec.name for spec in registry.all_commands()}
_NEW_COMMANDS |= {a.upper() for spec in registry.all_commands() for a in spec.aliases}


def main():
    if len(sys.argv) > 1:
        command = ' '.join(sys.argv[1:])
        process_command(command)
    else:
        print("Financial Terminal")
        print("Supports both DSL (analyze/calculate/show) and option pricing commands.")
        print("Type 'help' for option pricing commands, 'exit' to quit.\n")
        while True:
            try:
                ticker_hint = f" [{_session.ticker}]" if _session.ticker else ""
                command = input(f">{ticker_hint} ").strip()
                if command.lower() == 'exit':
                    break
                if not command:
                    continue
                process_command(command)
            except KeyboardInterrupt:
                print()
                break
            except Exception as e:
                print(f"Error: {e}")


def process_command(command):
    """Route to new command registry or legacy DSL depending on the first token."""
    first_token = command.strip().split()[0].upper() if command.strip() else ""

    if first_token in _NEW_COMMANDS:
        _process_new_command(command)
    else:
        _process_legacy_dsl(command)


def _process_new_command(command):
    """Handle POSIX-style option pricing commands."""
    try:
        parsed = tokenise(command)
        spec = registry.resolve(parsed.cmd)

        if spec is None:
            suggestions = registry.suggest(parsed.cmd)
            if suggestions:
                print(f"  Unknown command '{parsed.cmd}'. Did you mean: {', '.join(s.upper() for s in suggestions)}?")
            else:
                print(f"  Unknown command '{parsed.cmd}'. Type HELP for available commands.")
            return

        # Commands that don't need a ticker
        no_ticker = {"HELP", "SET"}
        if spec.name in no_ticker and parsed.ticker is None:
            ticker = parsed.ticker or ""
        else:
            ticker = _session.resolve_ticker(parsed.ticker)

        spec.handler(ticker, parsed.kwargs, parsed.flags, _session, _cache)

    except ValueError as e:
        print(f"  Error: {e}")
    except Exception as e:
        print(f"  Error: {e}")


def _process_legacy_dsl(command):
    """Handle legacy DSL commands (analyze, calculate, show)."""
    try:
        lexer = Lexer(command)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast = parser.parse()

        symbol_table = SymbolTable()
        analyzer = SemanticAnalyzer(ast, symbol_table)
        analyzer.analyze()

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