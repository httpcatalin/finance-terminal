"""
DataCache — unified market data layer with TTL caching.

Provides live stock data, options chains, risk-free rate, and historical
prices via yfinance + FRED.  Falls back to stale data with a warning
when fetches fail.
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    value: Any
    timestamp: float
    stale: bool = False


class DataCache:
    """Per-key TTL cache wrapping yfinance and FRED fetches."""

    def __init__(self, ttl_seconds: float = 300):
        self._store: dict[str, CacheEntry] = {}
        self.ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, key: str) -> CacheEntry | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry.timestamp > self.ttl:
            entry.stale = True
        return entry

    def _put(self, key: str, value: Any) -> CacheEntry:
        entry = CacheEntry(value=value, timestamp=time.time(), stale=False)
        self._store[key] = entry
        return entry

    def _get_or_fetch(self, key: str, fetcher):
        cached = self._get(key)
        if cached and not cached.stale:
            return cached.value, False  # (value, is_stale)

        try:
            value = fetcher()
            if value is None:
                raise ValueError("Fetch returned None")
            self._put(key, value)
            return value, False
        except Exception as e:
            logger.warning("Fetch failed for %s: %s", key, e)
            if cached is not None:
                return cached.value, True
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_ticker_info(self, ticker: str) -> tuple[dict, bool]:
        """Return yfinance .info dict.  Second element is stale flag."""
        def fetch():
            t = yf.Ticker(ticker)
            info = t.info
            if not info or "regularMarketPrice" not in info:
                raise ValueError(f"No info for {ticker}")
            return info
        return self._get_or_fetch(f"info:{ticker}", fetch)

    def get_spot_price(self, ticker: str) -> tuple[float, bool]:
        info, stale = self.get_ticker_info(ticker)
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        if price is None:
            raise ValueError(f"No spot price for {ticker}")
        return float(price), stale

    def get_dividend_yield(self, ticker: str) -> tuple[float, bool]:
        info, stale = self.get_ticker_info(ticker)
        # Prefer trailingAnnualDividendYield (reliable decimal) over
        # dividendYield which yfinance sometimes returns as a percentage
        # value masquerading as a decimal (e.g. 0.41 meaning 0.41%).
        dy = info.get("trailingAnnualDividendYield") or 0.0
        if dy == 0.0:
            dy = info.get("dividendYield") or 0.0
            # Sanity: cap at 20% — anything higher is likely a yfinance bug
            if dy > 0.20:
                dy = dy / 100.0
        return float(dy), stale

    def get_history(self, ticker: str, period: str = "1y") -> tuple[pd.DataFrame, bool]:
        def fetch():
            t = yf.Ticker(ticker)
            df = t.history(period=period)
            if df is None or df.empty:
                raise ValueError(f"No history for {ticker}")
            return df
        return self._get_or_fetch(f"hist:{ticker}:{period}", fetch)

    def get_historical_volatility(self, ticker: str, period: str = "1y") -> tuple[float, bool]:
        df, stale = self.get_history(ticker, period)
        returns = df["Close"].pct_change().dropna()
        vol = float(returns.std() * np.sqrt(252))
        return vol, stale

    def get_log_returns(self, ticker: str, period: str = "1y") -> tuple[np.ndarray, bool]:
        df, stale = self.get_history(ticker, period)
        prices = df["Close"].dropna().values
        returns = np.diff(np.log(prices))
        return returns, stale

    def get_options_expirations(self, ticker: str) -> tuple[list[str], bool]:
        def fetch():
            t = yf.Ticker(ticker)
            exps = list(t.options)
            if not exps:
                raise ValueError(f"No options data for {ticker}")
            return exps
        return self._get_or_fetch(f"optexp:{ticker}", fetch)

    def get_options_chain(self, ticker: str, expiry: str | None = None) -> tuple[dict, bool]:
        """Return {'calls': DataFrame, 'puts': DataFrame, 'expiry': str}."""
        def fetch():
            t = yf.Ticker(ticker)
            if expiry is None:
                exp = t.options[0]  # nearest expiry
            else:
                exp = expiry
            chain = t.option_chain(exp)
            return {"calls": chain.calls, "puts": chain.puts, "expiry": exp}
        return self._get_or_fetch(f"chain:{ticker}:{expiry}", fetch)

    def get_risk_free_rate(self) -> tuple[float, bool]:
        """3-month T-bill rate from FRED (DGS3MO), annualised decimal."""
        def fetch():
            api_key = os.getenv("FRED_API_KEY")
            if api_key:
                from fredapi import Fred
                fred = Fred(api_key=api_key)
                series = fred.get_series("DGS3MO")
                rate = series.dropna().iloc[-1]
                return float(rate) / 100.0
            else:
                # Fallback: use 10Y from yfinance ^TNX
                tnx = yf.Ticker("^IRX")  # 13-week T-bill
                info = tnx.info
                price = info.get("regularMarketPrice") or info.get("previousClose")
                if price:
                    return float(price) / 100.0
                return 0.05  # hard fallback
        return self._get_or_fetch("rfr", fetch)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_cache = DataCache()


def get_cache() -> DataCache:
    return _cache


def resolve_defaults(ticker: str, user_params: dict, cache: DataCache | None = None) -> dict:
    """Fill in missing parameters from live market data.

    Accepts user-provided K, T, sigma, r, q and fills defaults:
      S     → live spot
      sigma → 252-day realised vol
      r     → 3-month T-bill
      q     → trailing dividend yield
      K     → nearest round strike (round(S, -1))
      T     → 30/365
    """
    if cache is None:
        cache = _cache

    params = dict(user_params)
    stale_flags: list[str] = []

    # Spot price
    if "S" not in params:
        try:
            S, st = cache.get_spot_price(ticker)
            params["S"] = S
            if st:
                stale_flags.append("spot")
        except Exception:
            pass

    S = params.get("S", 100.0)

    # Strike
    if "K" not in params:
        # Nearest $5 strike
        params["K"] = round(S / 5) * 5

    # Maturity
    if "T" not in params:
        params["T"] = 30 / 365.0

    # Volatility
    if "sigma" not in params:
        try:
            vol, st = cache.get_historical_volatility(ticker)
            params["sigma"] = vol
            if st:
                stale_flags.append("vol")
        except Exception:
            params["sigma"] = 0.20

    # Risk-free rate
    if "r" not in params:
        try:
            r, st = cache.get_risk_free_rate()
            params["r"] = r
            if st:
                stale_flags.append("rfr")
        except Exception:
            params["r"] = 0.05

    # Dividend yield
    if "q" not in params:
        try:
            q, st = cache.get_dividend_yield(ticker)
            params["q"] = q
            if st:
                stale_flags.append("div_yield")
        except Exception:
            params["q"] = 0.0

    params["_stale"] = stale_flags
    return params
