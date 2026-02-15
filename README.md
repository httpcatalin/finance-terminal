# Finance Terminal DSL

A Domain-Specific Language (DSL) for financial market analysis, supporting stocks, options, futures, and bonds. Built for university ELSD & LFA course.

## Project Structure

```
finance-terminal/
├─ README.md
├─ .env.example
├─ requirements.txt
├─ docs/
│  ├─ grammar.bnf
│  └─ examples.md
└─ src/
    ├─ __init__.py
    ├─ cli/
    │  ├─ __init__.py
    │  └─ main.py
    ├─ dsl/
    │  ├─ lexer.py
    │  ├─ parser.py
    │  ├─ symbol_table.py
    │  ├─ semantic_analyzer.py
    │  └─ interpreter.py
    ├─ data/
    │  ├─ __init__.py
    │  ├─ market_data.py
    │  ├─ fundamentals_data.py
    │  └─ sentiment_data.py
    ├─ models/
    │  ├─ __init__.py
    │  ├─ stocks.py
    │  ├─ options.py
    │  ├─ futures.py
    │  └─ bonds.py
    └─ utils/
        ├─ __init__.py
        ├─ ai_helper.py
        ├─ formatting.py
        └─ math_helpers.py
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys (or request from me)
```

## Run

```bash
# Interactive CLI
python -m src.cli.main
```

Enter DSL commands like:

- analyze stock AAPL for 1Y
- calculate dcf for AAPL growth 0.05 discount 0.1 years 5
- show income_statement for AAPL

## DSL Grammar

See docs/grammar.bnf

## Examples

See docs/examples.md

## TODO Checklist (DSL Project Tasks)

### 1) DSL Core Components (`dsl/`)

- [x] Define BNF grammar (docs/grammar.bnf)
- [x] Implement Lexer with tokenization (keywords, identifiers, periods, strings)
- [x] Implement Parser with AST nodes (AnalyzeStmt, CalculateStmt, ShowStmt)
- [x] Implement Symbol Table for variable storage
- [x] Implement Semantic Analyzer for validation (asset types, periods, errors)
- [x] Implement Interpreter with visitor pattern for execution
- [x] Integrate data fetching in interpreter (stock prices/volatility)

### 2) CLI Interface (`cli/`)

- [x] Build interactive CLI loop
- [x] Add command-line argument support
- [x] Add debug prints for AST and symbol table
- [x] Error handling for invalid commands
- [ ] Implement Telegram bot for DSL command execution
- [ ] Add document retrieval and sharing via Telegram bot
- [ ] Integrate bot with DSL interpreter for real-time responses

### 3) Data Integration (`data/`)

- [x] Stock market data fetching (yfinance)
- [x] Fundamentals data (placeholders for statements)
- [x] Sentiment data (Fear & Greed index)
- [x] Error handling for API failures

### 4) Model Skeletons (`models/`)

- [x] Stock class skeleton
- [x] Option/Futures/Bond class skeletons
- [ ] Implement full Stock model (DCF, ratios)
- [ ] Implement Option model (Black-Scholes)
- [ ] Implement Futures model (cost-of-carry)
- [ ] Implement Bond model (pricing)

### 5) Utils and Testing

- [x] Project structure with modular folders (cli, dsl, data, models, utils)
- [x] Dependencies setup (requirements.txt, .env.example)
- [x] AI helper skeleton
- [x] Formatting/validation/math helpers
- [x] Unit tests for data fetching
- [x] Documentation (README, examples.md)

### 6) Advanced DSL Features (Future)

- [ ] Support for multiple statements per command
- [ ] Variable declarations and symbol table usage
- [ ] String literals in commands
- [ ] Error recovery in parsing
- [ ] Performance optimizations
- [ ] AI integration for command explanations (e.g., explain DCF results)
- [ ] AI-powered risk reports per analysis
- [ ] Interactive AI chat mode for financial queries
- [ ] Sentiment analysis with AI for market context
- [ ] Export results to PDF/CSV via commands
- [ ] Multi-language support for DSL keywords
- [ ] Historical data caching for faster queries
- [ ] Real-time data streaming for live analysis

### 7) Bot and External Integrations

- [ ] Telegram bot setup with DSL command handling
- [ ] Document upload/download via bot (e.g., share reports)
- [ ] Webhook integration for automated DSL execution
