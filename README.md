# Finance Terminal

PBL project that allows users should be able to analyze **Stocks, Options, Futures, and Bonds** from the command line, then ask an AI helper to explain results in plain English.

## Current Project Structure

```text
finance-terminal/
├─ README.md
└─ src/
	└─ finance_terminal/
		├─ __init__.py
		├─ cli/
		│  ├─ __init__.py
		│  └─ main.py
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
			├─ validation.py
			└─ math_helpers.py
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
```

When dependencies are finalized, install them with:

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m src.finance_terminal.cli.main
```

## TODO Checklist (ne impartim aici cu takurile)

### 2) Data Layer (`data/`)

- [ ] Create/centralize `data_api.py` style orchestration (or keep split files + one aggregator)
- [ ] Fetch stock historical prices using `yfinance`
- [ ] Fetch stock financial statements (income, balance sheet, cash flow)
- [ ] Calculate historical volatility for options
- [ ] Fetch risk-free rates (Treasury yields via FRED API)
- [ ] Fetch futures prices (commodities/indices)
- [ ] Fetch bond yields
- [ ] Fetch Fear & Greed index (CNN API)
- [ ] Add error handling/retries for API failures

### 3) Stocks Module (`models/stocks.py`)

- [ ] Add price performance for 1M, 6M, 1Y, 5Y
- [ ] Show financial statements (income, balance sheet, cash flow)
- [ ] Implement DCF model with user inputs: growth %, discount rate, forecast years
- [ ] Compute discounted cash flows + intrinsic value output
- [ ] (Optional) Add ratios: P/E, P/B, ROE, Debt/Equity
- [ ] (Optional) Add ASCII chart for price trends

### 4) Options Module (`models/options.py`)

- [ ] Implement Black-Scholes pricing (call + put)
- [ ] Accept strike, stock price, volatility, time to maturity inputs
- [ ] Adjust option pricing context using Fear & Greed index
- [ ] (Optional) Add Greeks: Delta, Gamma, Theta, Vega
- [ ] (Optional) Add Monte Carlo option pricing simulation

### 5) Futures Module (`models/futures.py`)

- [ ] Implement cost-of-carry futures pricing model
- [ ] Build PnL simulator (entry price vs current price)
- [ ] (Optional) Add contango/backwardation indicator
- [ ] (Optional) Add simple commodity futures dashboard in terminal

### 6) Bonds Module (`models/bonds.py`)

- [ ] Implement bond pricing formula (face value, coupon, years, YTM)
- [ ] Calculate Yield to Maturity
- [ ] Calculate Duration and Convexity
- [ ] (Optional) Plot/print yield curve view
- [ ] (Optional) Show interest-rate sensitivity output

### 7) AI Helper (`utils/ai_helper.py`)

- [ ] Add function to send prompt + receive response from OpenAI API
- [ ] Add DCF explanation prompt template
- [ ] Add options-price explanation template
- [ ] Add futures-market explanation template
- [ ] Add bond-risk explanation template
- [ ] (Optional) Generate full AI Risk Report per asset

### 8) CLI Interface (`cli/main.py`)

- [ ] Build main menu: Stocks / Options / Futures / Bonds / Exit
- [ ] Add submenus with input prompts and result display
- [ ] Add AI explanation option for each analysis flow
- [ ] (Optional) Allow saving report output to `.txt`

### 9) Extras / Advanced (Optional, unlikely lol)

- [ ] Stock technical indicators (RSI, MACD, moving averages)
- [ ] Portfolio tracker (multiple assets)
- [ ] Portfolio risk metrics (volatility, Sharpe ratio, sector allocation)
- [ ] News sentiment analysis for stocks/futures using AI
- [ ] More ASCII terminal charts
- [ ] Interactive AI chat mode: “Ask AI about this stock”
