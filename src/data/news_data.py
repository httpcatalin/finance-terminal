"""
src/data/news_data.py
═════════════════════
Fetches news articles for a ticker from two sources:
  1. yfinance ticker.news  — free, no API key, always available
  2. NewsAPI.org           — free tier (100 req/day), richer descriptions

Returns a unified list of NewsArticle objects sorted by recency.
"""

from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import yfinance as yf

logger = logging.getLogger(__name__)

# NewsAPI key — set via env var or hardcoded fallback
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "bf095eed71024f269b030cc6cd79944d")


@dataclass
class NewsArticle:
    title:     str
    summary:   str          # description / first paragraph
    source:    str          # publisher name
    url:       str
    published: datetime     # UTC


# ─────────────────────────────────────────────────────────────
# DATE RANGE HELPERS
# ─────────────────────────────────────────────────────────────

def _parse_date_range(date_str: str) -> tuple[datetime, datetime]:
    """
    Convert DSL date string to (start, end) UTC datetime pair.

    Supported values:
        "today"      → last 24 hours
        "yesterday"  → 24-48 hours ago
        "last_week"  → last 7 days
        "last_month" → last 30 days
        "YYYY-MM-DD" → that calendar day
    """
    now = datetime.now(timezone.utc)

    if date_str in ("today", ""):
        return now - timedelta(days=1), now
    if date_str == "yesterday":
        return now - timedelta(days=2), now - timedelta(days=1)
    if date_str == "last_week":
        return now - timedelta(days=7), now
    if date_str == "last_month":
        return now - timedelta(days=30), now

    # Try ISO date
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return day, day + timedelta(days=1)
    except ValueError:
        pass

    # Fallback: last 24h
    logger.warning("Unrecognised date '%s', defaulting to today", date_str)
    return now - timedelta(days=1), now


# ─────────────────────────────────────────────────────────────
# SOURCE 1: yfinance  (always free, no key required)
# ─────────────────────────────────────────────────────────────

def _fetch_yfinance_news(ticker: str, start: datetime, end: datetime) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    try:
        raw = yf.Ticker(ticker).news or []
        for item in raw:
            ts = item.get("providerPublishTime") or item.get("published", 0)
            if not ts:
                continue
            pub = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            if not (start <= pub <= end):
                continue
            articles.append(NewsArticle(
                title     = item.get("title", "").strip(),
                summary   = item.get("summary", item.get("title", "")).strip(),
                source    = item.get("publisher", "Yahoo Finance"),
                url       = item.get("link", ""),
                published = pub,
            ))
    except Exception as exc:
        logger.warning("yfinance news fetch failed for %s: %s", ticker, exc)
    return articles


# ─────────────────────────────────────────────────────────────
# SOURCE 2: NewsAPI.org  (requires free API key)
# ─────────────────────────────────────────────────────────────

def _fetch_newsapi(ticker: str, company_name: str, start: datetime, end: datetime) -> list[NewsArticle]:
    if not NEWSAPI_KEY:
        return []
    try:
        query   = f'"{ticker}" OR "{company_name}"'
        from_dt = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_dt   = end.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = (
            "https://newsapi.org/v2/everything"
            f"?q={urllib.parse.quote(query)}"
            f"&from={from_dt}&to={to_dt}"
            f"&sortBy=publishedAt&language=en&pageSize=20"
            f"&apiKey={NEWSAPI_KEY}"
        )
        with urllib.request.urlopen(url, timeout=8) as resp:  # noqa: S310
            data = json.loads(resp.read())

        articles: list[NewsArticle] = []
        for item in data.get("articles", []):
            pub_str = item.get("publishedAt", "")
            try:
                pub = datetime.strptime(pub_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except Exception:
                continue
            articles.append(NewsArticle(
                title     = (item.get("title") or "").strip(),
                summary   = (item.get("description") or item.get("title") or "").strip(),
                source    = item.get("source", {}).get("name", "NewsAPI"),
                url       = item.get("url", ""),
                published = pub,
            ))
        return articles
    except Exception as exc:
        logger.warning("NewsAPI fetch failed for %s: %s", ticker, exc)
        return []


# ─────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────

def get_news(
    ticker:   str,
    date_str: str = "today",
    limit:    int = 15,
) -> list[NewsArticle]:
    """
    Return up to `limit` deduplicated NewsArticle objects for ticker,
    filtered to the date range described by date_str, sorted newest first.
    """
    ticker = ticker.upper().strip()

    company_name = ticker
    try:
        info = yf.Ticker(ticker).info
        company_name = info.get("longName", ticker) or ticker
    except Exception:
        pass

    start, end = _parse_date_range(date_str)

    articles  = _fetch_yfinance_news(ticker, start, end)
    articles += _fetch_newsapi(ticker, company_name, start, end)

    # Deduplicate by title (normalised to lowercase)
    seen:   set[str]          = set()
    unique: list[NewsArticle] = []
    for art in articles:
        key = art.title.lower().strip()[:80]
        if key and key not in seen:
            seen.add(key)
            unique.append(art)

    unique.sort(key=lambda a: a.published, reverse=True)
    return unique[:limit]
