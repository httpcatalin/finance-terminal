"""
src/models/sentiment.py
════════════════════════
Calls the Anthropic Claude API to produce structured sentiment analysis
for a batch of news articles about a stock ticker.

Output per article:  label (BULLISH / BEARISH / NEUTRAL), confidence (0-1),
                     one-line reason
Output overall:      verdict, aggregate score (-1.0 to +1.0), key_drivers list
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

SentimentLabel = Literal["BULLISH", "BEARISH", "NEUTRAL"]

LABEL_SCORE = {"BULLISH": +1, "BEARISH": -1, "NEUTRAL": 0}

LABEL_SYMBOLS = {
    "BULLISH": "+",
    "BEARISH": "-",
    "NEUTRAL": "~",
}

# ─────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────

@dataclass
class ArticleSentiment:
    title:      str
    source:     str
    label:      SentimentLabel
    confidence: float           # 0.0 – 1.0
    reason:     str             # one sentence


@dataclass
class SentimentReport:
    ticker:        str
    date_str:      str
    article_count: int
    results:       list[ArticleSentiment]
    verdict:       SentimentLabel     # overall
    score:         float              # weighted average, -1.0 to +1.0
    key_drivers:   list[str]          # 2-4 bullet points
    bullish_count: int
    bearish_count: int
    neutral_count: int

    def print_report(self) -> None:
        """Render the full sentiment report to the terminal."""
        w = 62
        verdict_sym = LABEL_SYMBOLS[self.verdict]

        # Score bar  +++++++...  (+0.64)
        bar_filled = int(abs(self.score) * 10)
        bar_empty  = 10 - bar_filled
        bar_char   = "+" if self.score >= 0 else "-"
        bar = bar_char * bar_filled + "." * bar_empty

        print("\n" + "=" * w)
        print(f"  NEWS SENTIMENT — {self.ticker}  |  {self.date_str}  |  {self.article_count} articles")
        print("=" * w)
        print(f"  Overall  :  [{verdict_sym}] {self.verdict}  [{bar}]  ({self.score:+.2f})")
        print(f"  Counts   :  +{self.bullish_count} bullish   ~{self.neutral_count} neutral   -{self.bearish_count} bearish")

        if self.key_drivers:
            print(f"\n  Key drivers")
            for kd in self.key_drivers:
                print(f"    • {kd}")

        for label in ("BULLISH", "NEUTRAL", "BEARISH"):
            group = [r for r in self.results if r.label == label]
            if not group:
                continue
            sym = LABEL_SYMBOLS[label]
            print(f"\n  {label} ({len(group)})")
            for art in group:
                src  = f"[{art.source}]" if art.source else ""
                conf = f" {art.confidence:.0%}" if art.confidence < 0.75 else ""
                title = art.title[:52] + "…" if len(art.title) > 52 else art.title
                print(f"  {sym} {title} {src}{conf}")
                if art.reason:
                    print(f"    ↳ {art.reason}")

        print("=" * w + "\n")


# ─────────────────────────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────────────────────────

def _build_prompt(ticker: str, articles: list) -> str:
    lines = [
        f"You are a financial analyst. Analyse the following {len(articles)} news headlines",
        f"and summaries about {ticker}. For EACH article, classify the sentiment as one of:",
        "  BULLISH — positive for the stock (revenue beat, expansion, product launch, upgrade)",
        "  BEARISH — negative for the stock (miss, lawsuit, regulation, downgrade, layoffs)",
        "  NEUTRAL — factual / no clear directional impact",
        "",
        "Then provide an OVERALL verdict for the batch.",
        "",
        "Return ONLY valid JSON in exactly this schema, no markdown, no preamble:",
        "{",
        '  "articles": [',
        '    {"title": "...", "label": "BULLISH|BEARISH|NEUTRAL",',
        '     "confidence": 0.0-1.0, "reason": "one sentence"},',
        '    ...',
        '  ],',
        '  "overall": {',
        '    "verdict": "BULLISH|BEARISH|NEUTRAL",',
        '    "score": -1.0 to +1.0,',
        '    "key_drivers": ["driver 1", "driver 2", "driver 3"]',
        '  }',
        "}",
        "",
        "Articles:",
    ]

    for i, art in enumerate(articles, 1):
        lines.append(f"{i}. [{art.source}] {art.title}")
        if art.summary and art.summary != art.title:
            lines.append(f"   {art.summary[:200]}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# OPENAI API CALL
# ─────────────────────────────────────────────────────────────

def _call_openai(prompt: str) -> dict:
    """Call the OpenAI Chat Completions API and return the parsed JSON dict."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "")
    client  = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model       = "gpt-4o-mini",
        max_tokens  = 1500,
        temperature = 0,
        messages    = [
            {
                "role":    "system",
                "content": "You are a financial analyst. Return only valid JSON, no markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    raw_text = response.choices[0].message.content or ""
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    return json.loads(raw_text.strip())


# ─────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────

def analyse_sentiment(
    ticker:   str,
    articles: list,
    date_str: str  = "today",
    verbose:  bool = True,
) -> SentimentReport:
    """
    Run sentiment analysis on a list of NewsArticle objects.
    Returns a SentimentReport and optionally prints it to the terminal.
    """
    ticker = ticker.upper().strip()

    if not articles:
        report = SentimentReport(
            ticker        = ticker,
            date_str      = date_str,
            article_count = 0,
            results       = [],
            verdict       = "NEUTRAL",
            score         = 0.0,
            key_drivers   = ["No news articles found for this period."],
            bullish_count = 0,
            bearish_count = 0,
            neutral_count = 0,
        )
        if verbose:
            report.print_report()
        return report

    prompt = _build_prompt(ticker, articles)
    raw    = _call_openai(prompt)

    article_map = {a.title: a for a in articles}
    results: list[ArticleSentiment] = []

    for item in raw.get("articles", []):
        title_key = item.get("title", "")
        art       = article_map.get(title_key)
        label     = item.get("label", "NEUTRAL").upper()
        if label not in ("BULLISH", "BEARISH", "NEUTRAL"):
            label = "NEUTRAL"

        results.append(ArticleSentiment(
            title      = title_key,
            source     = art.source if art else "",
            label      = label,
            confidence = float(item.get("confidence", 0.7)),
            reason     = item.get("reason", ""),
        ))

    overall = raw.get("overall", {})
    verdict = overall.get("verdict", "NEUTRAL").upper()
    if verdict not in ("BULLISH", "BEARISH", "NEUTRAL"):
        verdict = "NEUTRAL"

    score = float(overall.get("score", 0.0))
    score = max(-1.0, min(1.0, score))

    key_drivers = [str(kd) for kd in overall.get("key_drivers", [])][:4]

    bullish_count = sum(1 for r in results if r.label == "BULLISH")
    bearish_count = sum(1 for r in results if r.label == "BEARISH")
    neutral_count = sum(1 for r in results if r.label == "NEUTRAL")

    report = SentimentReport(
        ticker        = ticker,
        date_str      = date_str,
        article_count = len(results),
        results       = results,
        verdict       = verdict,
        score         = score,
        key_drivers   = key_drivers,
        bullish_count = bullish_count,
        bearish_count = bearish_count,
        neutral_count = neutral_count,
    )

    if verbose:
        report.print_report()

    return report
