# Financial Terminal DSL Examples

This document lists all command types defined in the DSL grammar (`grammar.bnf`), with examples. It categorizes them by implementation status based on the current code.

## Fully Supported Commands

### Analyze Stock

Fetches historical prices and calculates volatility from Yahoo Finance.

- Syntax: `analyze stock <ticker> for <period>`
- Periods: 1M, 6M, 1Y, 5Y
- Examples:
  - `analyze stock AAPL for 1Y` → Prices and volatility for Apple.
  - `analyze stock GOOGL for 6M` → Google data for 6 months.
  - `analyze stock TSLA for 1M` → Tesla for 1 month.

## Partially Supported Commands

These parse and validate correctly, but execution is incomplete (placeholders, partial data, or errors).

### Show Prices

Fetches and displays the latest stock price.

- Syntax: `show prices for <ticker>`
- Example: `show prices for AAPL` → Latest close price.

### Show Income Statement / Balance Sheet / Cash Flow

Attempts to fetch financial statements, but may fail due to API limits or missing keys.

- Syntax: `show <show_type> for <ticker>`
- Show Types: income_statement, balance_sheet, cash_flow
- Examples:
  - `show income_statement for AAPL` → May show data or "Failed to fetch".
  - `show balance_sheet for AAPL` → Same.

### Calculate DCF

Parses parameters and prints a placeholder (no real DCF calculation).

- Syntax: `calculate dcf for <ticker> <params>`
- Params: growth (float), discount (float), years (int)
- Example: `calculate dcf for AAPL growth 0.05 discount 0.1 years 5` → Placeholder output.

## Not Supported Yet

These are defined in the grammar but not implemented in the interpreter. They parse without errors but do nothing or error on execution.

### Analyze Option / Future / Bond

- Syntax: `analyze <asset_type> <ticker> for <period>`
- Asset Types: option, future, bond
- Examples:
  - `analyze option AAPL for 1Y` → No execution.
  - `analyze future GC=F for 6M` → No execution.
  - `analyze bond US10Y for 1Y` → No execution.

### Calculate Black-Scholes / Futures Price / Bond Price

- Syntax: `calculate <calc_type> for <ticker> <params>`
- Calc Types: black_scholes, futures_price, bond_price
- Params vary (e.g., strike, volatility for black_scholes).
- Examples:
  - `calculate black_scholes for AAPL strike 150 volatility 0.2 maturity 1` → No execution.
  - `calculate futures_price for GC=F` → No execution.
  - `calculate bond_price for US10Y face_value 1000 coupon 0.03 ytm 0.035` → No execution.

### Show Volatility

Defined but not implemented (volatility is in analyze instead).

- Syntax: `show volatility for <ticker>`
- Example: `show volatility for AAPL` → No execution.
