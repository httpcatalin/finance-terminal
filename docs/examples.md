# Financial Terminal DSL Examples

This document lists all command types defined in the DSL grammar (`grammar.bnf`), with examples. It categorizes them by implementation status based on the current code. Examples demonstrate the grammar rules and syntax.

## Fully Supported Commands

These commands are fully implemented: they parse correctly and execute with real data or calculations.

### Analyze Stock

Fetches historical prices and calculates volatility from Yahoo Finance.

- Syntax: `analyze stock <ticker> for <period>`
- Periods: 1M, 6M, 1Y, 5Y
- Examples:
  - `analyze stock AAPL for 1Y` → Prices and volatility for Apple.
  - `analyze stock GOOGL for 6M` → Google data for 6 months.
  - `analyze stock TSLA for 1M` → Tesla for 1 month.

### Show Prices

Fetches and displays the latest stock price.

- Syntax: `show prices for <ticker>`
- Example: `show prices for AAPL` → Latest close price.

### Show Financial Statements

Fetches income statement, balance sheet, or cash flow data.

- Syntax: `show <show_type> for <ticker>`
- Show Types: income_statement, balance_sheet, cash_flow
- Examples:
  - `show income_statement for AAPL` → Income statement data.
  - `show balance_sheet for AAPL` → Balance sheet data.
  - `show cash_flow for AAPL` → Cash flow data.

### Calculate DCF

Performs Discounted Cash Flow valuation (placeholder implementation).

- Syntax: `calculate dcf for <ticker> <params>`
- Params: growth (float), discount (float), years (int)
- Example: `calculate dcf for AAPL growth 0.05 discount 0.1 years 5` → DCF valuation result.

## Partially Supported Commands

These parse correctly but execution is incomplete or uses placeholders.

### Advanced Analyze Options

Basic analyze works, but options are not implemented.

- Syntax: `analyze stock <ticker> for <period> <analyze_options>`
- Analyze Options: with <identifier>, filter <expression>, group by <identifier>
- Example: `analyze stock AAPL for 1Y with volatility` → Parses but options ignored.

### Advanced Calculate Options

Basic calculate works, but options are not implemented.

- Syntax: `calculate <calc_type> for <ticker> <params> <calc_options>`
- Calc Options: using <identifier>, method <string>, iterations <number>
- Example: `calculate dcf for AAPL growth 0.05 using advanced_method` → Parses but options ignored.

### Advanced Show Options

Basic show works, but filters and formats are not implemented.

- Syntax: `show <show_type> for <ticker> <show_filters> <show_format>`
- Show Filters: where <expression>
- Show Format: as <format_type> (table, chart, json, csv)
- Example: `show prices for AAPL as json` → Parses but format ignored.

## Not Yet Implemented (Defined in BNF but Not Supported)

These features are defined in the grammar but not implemented in lexer, parser, or interpreter. They will parse as unknown tokens or fail.

### Variable Declarations and Assignments

- Syntax: `<type> <identifier> | <type> <identifier> = <expression>`
- Types: int, float, string, bool, date, currency, array[type], dict[type,type]
- Examples:
  - `int x = 5;`
  - `float pi = 3.14159;`
  - `string ticker = "AAPL";`
  - `bool is_bull = true;`
  - `date today = date("2024-01-01");`
  - `currency amount = currency(1000.0, "USD");`
  - `array[int] numbers = [1, 2, 3];`
  - `dict[string, float] portfolio = {"AAPL": 100.0};`

### Assignments

- Syntax: `<identifier> = <expression> | <identifier>[<expression>] = <expression> | <identifier>.<identifier> = <expression>`
- Examples:
  - `x = x + 1;`
  - `portfolio["AAPL"] = 150.0;`
  - `stock.price = 145.5;`

### Control Structures

- If Statement: `if (<expression>) <statement> | if (<expression>) <statement> else <statement>`
  - Example: `if (price > 150.0) { show prices for AAPL; } else { analyze stock GOOGL for 1M; }`

- While Loop: `while (<expression>) <statement>`
  - Example: `while (i < 10) { i = i + 1; calculate dcf for AAPL growth 0.05 years i; }`

- For Loop: `for (<identifier> in <expression>) <statement>`
  - Example: `for (ticker in ["AAPL", "GOOGL"]) { show prices for ticker; }`

### Function Definitions

- Syntax: `def <identifier> (<param_list>) <statement>`
- Param List: <type> <identifier>, ...
- Example: `def calculate_total(portfolio) { float total = 0.0; for (stock in portfolio) { total = total + portfolio[stock]; } return total; }`

### Return Statement

- Syntax: `return <expression> | return`
- Example: `return result;`

### Expressions

Complex expressions with operators (precedence: logical → comparison → additive → multiplicative → power → unary → primary)

- Arithmetic: `x + y * 2 ^ 3`
- Comparison: `price > 150.0 && volatility < 0.3`
- Logical: `(condition1 || condition2) && condition3`
- Function Call: `calculate_dcf(AAPL, 0.05, 0.1, 5)`
- Member Access: `stock.price`
- Array Access: `portfolio[0]`
- Literals: `42`, `"string"`, `true`, `date("2024-01-01")`, `currency(100.0, "USD")`
- Arrays: `[1, 2, 3]`
- Dicts: `{"key": "value"}`

### Advanced Financial Commands

- Analyze Other Assets: `analyze option AAPL for 1Y`, `analyze future GC=F for 6M`, `analyze bond US10Y for 1Y`, `analyze portfolio MY_PORTFOLIO for 1Y`
- Advanced Calculations: `calculate black_scholes for AAPL strike 150.0 volatility 0.25 maturity 1.0`, `calculate futures_price for GC=F underlying 1800 cost_of_carry 0.02`, `calculate bond_price for US10Y face_value 1000 coupon 0.03 ytm 0.035`, `calculate sharpe_ratio for AAPL`, `calculate var for PORTFOLIO confidence 0.95`, `calculate correlation for AAPL GOOGL`, `calculate beta for AAPL`, `calculate monte_carlo for AAPL simulations 10000`
- Advanced Show: `show ratios for AAPL`, `show chart for AAPL`, `show statistics for AAPL`, `show correlation_matrix for PORTFOLIO`, `show portfolio_performance for MY_PORTFOLIO`

### Block Statements

- Syntax: `{ <statement_list> }`
- Example: `{ int x = 5; if (x > 3) { show prices for AAPL; } }`

### Expression Statements

- Syntax: `<expression>;`
- Example: `calculate_dcf(AAPL, 0.05, 0.1, 5);`
