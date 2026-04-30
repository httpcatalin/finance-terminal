"""
Session — persists ticker context across commands (Bloomberg-style).

Usage:
    SET GOOG        → session.ticker = "GOOG"
    BSM K=150       → uses session.ticker automatically
"""

from __future__ import annotations


class Session:
    def __init__(self):
        self.ticker: str | None = None

    def set_ticker(self, ticker: str) -> None:
        self.ticker = ticker.upper()

    def resolve_ticker(self, explicit: str | None) -> str:
        if explicit:
            self.ticker = explicit.upper()
            return self.ticker
        if self.ticker:
            return self.ticker
        raise ValueError("No ticker specified. Use SET <TICKER> first or pass a ticker.")
