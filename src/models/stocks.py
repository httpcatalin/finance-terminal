from __future__ import annotations

import logging
from typing import Optional

import yfinance as yf

from ..stock_modelling.dcf import DCFResult, calculate_dcf
from ..data.fundamentals_data import get_balance_sheet, get_cash_flow, get_income_statement


logger = logging.getLogger(__name__)


class Stock:
    def __init__(self, ticker):
        self.ticker = ticker.upper().strip()

    def get_price_performance(self, periods):
        try:
            period = (periods or "1y").lower()
            data = yf.Ticker(self.ticker).history(period=period)
            if data is None or data.empty:
                return None

            start_close = float(data["Close"].iloc[0])
            end_close = float(data["Close"].iloc[-1])
            return {
                "period": period,
                "start_close": start_close,
                "end_close": end_close,
                "return_pct": ((end_close - start_close) / start_close) if start_close else 0.0,
            }
        except Exception as exc:
            logger.error("Error fetching price performance for %s: %s", self.ticker, exc)
            return None

    def get_financial_statements(self):
        return {
            "income_statement": get_income_statement(self.ticker),
            "balance_sheet": get_balance_sheet(self.ticker),
            "cash_flow": get_cash_flow(self.ticker),
        }

    def perform_dcf_valuation(
        self,
        revenue_growth: float = 0.07,
        discount_rate: Optional[float] = None,
        forecast_years: int = 10,
        terminal_growth_rate: float = 0.03,
        beta_override: Optional[float] = None,
        tgr_source: str = "default",
        discount_source: str = "auto",
        moat_type: Optional[str] = None,
        moat_width: Optional[int] = None,
        shares_outstanding: Optional[float] = None,
        verbose: bool = True,
    ) -> DCFResult:
        return calculate_dcf(
            ticker=self.ticker,
            growth_rate=float(revenue_growth),
            years=int(forecast_years),
            terminal_growth_rate=float(terminal_growth_rate),
            discount_rate_override=float(discount_rate) if discount_rate is not None else None,
            beta_override=float(beta_override) if beta_override is not None else None,
            moat_type_override=moat_type,
            moat_width_override=int(moat_width) if moat_width is not None else None,
            shares_outstanding_override=(
                float(shares_outstanding) if shares_outstanding is not None else None
            ),
            tgr_source=tgr_source,
            discount_source=discount_source,
            verbose=bool(verbose),
        )

    def calculate_ratios(self):
        pass

    def generate_price_chart(self):
        pass
