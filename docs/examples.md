# Financial Terminal — Command Reference

All commands available in the DSL and option-pricing shell, grouped by category.
See `grammar.bnf` for the formal grammar.

---

## 1. Stock Analysis

Fetches historical prices and historical volatility from Yahoo Finance.

- Syntax: `analyze stock <ticker> for <period>`
- Periods: `1M` `6M` `1Y` `5Y`

```
analyze stock AAPL for 1Y
analyze stock GOOGL for 6M
analyze stock TSLA for 1M
analyze stock MSFT for 5Y
```

---

## 2. Financial Statements

Fetch fundamental data from Yahoo Finance.

- Syntax: `show <type> for <ticker>`
- Types: `income_statement` `balance_sheet` `cash_flow` `prices`

```
show prices for AAPL
show income_statement for AAPL
show balance_sheet for MSFT
show cash_flow for GOOGL
```

---

## 3. Stock Valuation (DCF)

Discounted Cash Flow valuation. Uses live FCF data from Yahoo Finance.
All parameters are optional; omitted ones are auto-calculated.

- Syntax: `calculate dcf for <ticker> [growth <f>] [discount <f|auto>] [years <n>] [terminal_growth <f>] [beta <f>]`

```
calculate dcf for AAPL growth 0.15 years 10
calculate dcf for GOOGL growth 0.10 beta 1.00 years 10
calculate dcf for GOOGL growth 0.10 discount 0.09 years 10
calculate dcf for META growth 0.12 years 10 terminal_growth 0.025
calculate dcf for MSFT growth 0.08 discount auto years 10 terminal_growth 0.03
```

---

## 4. Moat Analysis

AI-powered economic moat detection — identifies competitive advantages.

- Syntax: `show moat for <ticker>`

```
show moat for GOOGL
show moat for AAPL
show moat for MSFT
```

---

## 5. News & Sentiment

Fetches recent news (yfinance + NewsAPI) and runs AI sentiment analysis
(OpenAI GPT-4o-mini) to classify each article as BULLISH / BEARISH / NEUTRAL.

- Syntax: `news <ticker> [<date_range>] [limit <n>]`
- Date ranges: `today` `yesterday` `last_week` `last_month` `YYYY-MM-DD`
- Default date range: `today`; default limit: `15`

```
news GOOGL
news GOOGL today
news GOOGL last_week
news AAPL last_month
news META yesterday
news TSLA 2026-04-20
news MSFT last_week limit 20
```

---

## 6. Option Pricing

POSIX-style commands. Use `SET <ticker>` to avoid repeating the ticker.

### Session
```
SET GOOG
```

### Black-Scholes (BSM)
```
BSM GOOG K=150 T=0.25
BSM GOOG K=150 T=0.25 --graph
BSM GOOG K=150 T=0.25 --graph --delta
```

### Binomial Tree (BIN)
```
BIN GOOG K=150 T=0.25
BIN GOOG K=150 T=0.25 --american
BIN GOOG K=150 T=0.25 steps=500 --graph
```

### Monte Carlo (MC)
```
MC GOOG K=150 T=0.25 N=100000
MC GOOG K=150 --asian
MC GOOG K=150 --barrier B=130 --up-and-out
MC GOOG --lookback
```

### GARCH Volatility
```
GARCH GOOG --forecast --graph
```

### Implied Volatility
```
VOL GOOG --smile
VOL GOOG --surface
IV GOOG K=150 T=0.25 PRICE=8.50
```

### Strategies
```
STRAT GOOG straddle K=150 --graph
STRAT GOOG bull-spread K1=140 K2=160 --graph
STRAT GOOG butterfly K1=140 K2=150 K3=160 --graph
```

### Model Comparison & VaR
```
COMPARE GOOG K=150 T=0.25 --graph
VAR GOOG --hist --graph
VAR GOOG --mc conf=0.99 horizon=10
```

### Options Chain
```
CHAIN GOOG
CHAIN GOOG expiry=2026-06-19
```

### Price Forecasting (ARIMA)
```
ARIMA GOOG steps=30 --graph
ARIMA GOOG --seasonal --graph
ARIMA GOOG --vol --graph
```

---

## 7. Misc

```
HELP      Show all available commands with syntax
```

---

## Parameter Reference

| Parameter       | Used in          | Description                              |
|-----------------|------------------|------------------------------------------|
| `growth`        | DCF              | FCF annual growth rate (e.g. `0.10`)     |
| `discount`      | DCF              | Discount / WACC rate, or `auto`          |
| `terminal_growth` | DCF            | Perpetuity growth rate (default `0.03`)  |
| `beta`          | DCF              | Override market beta                     |
| `years`         | DCF              | Forecast horizon in years                |
| `K`             | Options          | Strike price                             |
| `T`             | Options          | Time to expiry in years                  |
| `sigma`         | Options          | Volatility override                      |
| `r`             | Options          | Risk-free rate                           |
| `N`             | MC               | Number of simulations                    |
| `B`             | MC barrier       | Barrier level                            |
| `steps`         | BIN              | Binomial tree steps                      |
| `K1` `K2` `K3`  | Strategies       | Strike levels for spreads/butterflies    |
| `conf`          | VaR              | Confidence level (e.g. `0.99`)           |
| `horizon`       | VaR              | Horizon in days                          |
| `expiry`        | CHAIN            | Option expiry date (`YYYY-MM-DD`)        |
| `PRICE`         | IV               | Market option price for IV calculation   |
| `limit`         | NEWS             | Max articles to fetch (default `15`)     |
