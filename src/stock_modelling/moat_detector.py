"""
moat_detector.py  —  drop-in replacement for the auto_detect_moat section of dcf.py
======================================================================================

WHY META (and similar platform companies) were being misclassified
-------------------------------------------------------------------
The original scorer was purely quantitative and had a single fatal blind spot:

  Intangible Assets score = gross_margin * 0.50  +  rd_intensity * 0.30  + op_margin * 0.20

META has gross_margin ~80% and R&D intensity ~18% — numbers that look identical to
ASML (semiconductor lithography patents) or Novo Nordisk (GLP-1 patents) on paper.
The algorithm had no concept of *why* a company has high margins and heavy R&D spend.

Fix — two additional layers
----------------------------
1. SECTOR PRIOR   — yfinance exposes `info['sector']` and `info['industry']`.
   We use these to add a Bayesian-style prior boost to the most likely moat type
   for each sector.  Communication Services → Network Effects prior.
   Healthcare / Technology (Semiconductors) → Intangible Assets prior.
   Utilities → Efficient Scale prior.  Etc.

2. THREE NEW SIGNALS — computed from balance sheet data:
   a) asset_lightness    = Revenue / Total Assets
      High value (>1.0) = the company generates more revenue than it owns in assets.
      This is the hallmark of platform / marketplace businesses (META, GOOG, UBER).
      Physical businesses (utilities, manufacturing) have ratios well below 1.0.
      → Boosts Network Effects score; penalises Efficient Scale.

   b) capex_intensity    = CapEx / Revenue
      High capex (>10%) = the company must build and maintain physical infrastructure.
      Low capex (<5%)   = asset-light software/platform model.
      → High capex boosts Efficient Scale and Cost Advantage.
      → Low capex boosts Network Effects and Switching Costs.

   c) rd_type_discriminator = R&D intensity × Revenue CAGR
      The key insight:
        Platform R&D (META, GOOG) → high R&D AND high revenue growth (users drive revenue)
        Patent R&D   (NVO, ASML)  → high R&D AND slow/moderate revenue growth
      Multiplying R&D intensity × CAGR creates a signal that is large only for platform
      companies.  This directly breaks the tie between META and pharma/semiconductor firms.
      → Boosts Network Effects for high-R&D + high-growth companies.
      → Leaves Intangible Assets for high-R&D + low-growth companies.

SECTOR → MOAT PRIOR MAP
------------------------
Communication Services  → Network Effects    +0.40
Technology (Internet)   → Network Effects    +0.25
Technology (Software)   → Switching Costs    +0.30
Technology (Semis/HW)   → Intangible Assets  +0.30
Healthcare / Biotech    → Intangible Assets  +0.40
Consumer Staples        → Cost Advantage     +0.25
Consumer Discretionary  → Cost Advantage     +0.20
  (Luxury sub-sector)   → Intangible Assets  +0.30  (overrides above)
Financial Services      → Switching Costs    +0.20
Industrials             → Cost Advantage     +0.20
Utilities               → Efficient Scale    +0.40
Real Estate             → Efficient Scale    +0.35
Energy                  → Cost Advantage     +0.15
Basic Materials         → Cost Advantage     +0.15

EXAMPLE OUTCOMES
----------------
Company      Sector                  Detected moat
--------     ------                  -------------
META         Communication Services  Network Effects      (was: Intangible Assets)
GOOG         Communication Services  Network Effects
NFLX         Communication Services  Network Effects
MSFT         Technology (Software)   Switching Costs
ORCL         Technology (Software)   Switching Costs
ADBE         Technology (Software)   Switching Costs
AAPL         Technology (Consumer)   Intangible Assets    (brand + ecosystem)
ASML         Technology (Semis)      Intangible Assets    (EUV patent monopoly)
NVO          Healthcare              Intangible Assets    (GLP-1 patents)
COST         Consumer Staples        Cost Advantage
AMZN         Consumer Discretionary  Cost Advantage / NE  (hybrid, CA wins on scale)
LVMH         Consumer Disc. Luxury   Intangible Assets    (brand)
NEE          Utilities               Efficient Scale
SAP          Technology (Software)   Switching Costs
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional
import yfinance as yf

logger = logging.getLogger(__name__)

# ── Re-use MoatType from dcf.py if importing, else redefine ──────────────
try:
    from .dcf import MoatType, MoatSignals, MOAT_WIDTH_LABELS
except ImportError:
    from enum import Enum
    class MoatType(Enum):
        NONE              = "none"
        COST_ADVANTAGE    = "cost_advantage"
        NETWORK_EFFECTS   = "network_effects"
        SWITCHING_COSTS   = "switching_costs"
        INTANGIBLE_ASSETS = "intangible_assets"
        EFFICIENT_SCALE   = "efficient_scale"

    @dataclass
    class MoatSignals:
        gross_margin:           float = 0.0
        operating_margin:       float = 0.0
        revenue_cagr_3y:        float = 0.0
        fcf_margin:             float = 0.0
        rd_intensity:           float = 0.0
        roic:                   float = 0.0
        gross_margin_stability: float = 0.0
        debt_to_equity:         float = 0.0
        # New signals
        asset_lightness:        float = 0.0
        capex_intensity:        float = 0.0
        rd_type_discriminator:  float = 0.0

    MOAT_WIDTH_LABELS = {0: "None", 1: "Narrow", 2: "Wide", 3: "Fortress"}


# ─────────────────────────────────────────────────────────────
# 1.  SECTOR → MOAT PRIOR
# ─────────────────────────────────────────────────────────────

# Maps (sector, optional industry substring) → (MoatType, prior_boost)
# Rules evaluated top-to-bottom; first match wins.
# Industry substring match takes priority over sector-only match.
_SECTOR_PRIORS: list[tuple[str, Optional[str], MoatType, float]] = [
    # sector                    industry substring    moat type           boost
    ("Communication Services",  None,                MoatType.NETWORK_EFFECTS,   0.40),
    ("Technology",              "Internet",           MoatType.NETWORK_EFFECTS,   0.25),
    ("Technology",              "Software",           MoatType.SWITCHING_COSTS,   0.30),
    ("Technology",              "Semiconductor",      MoatType.INTANGIBLE_ASSETS, 0.30),
    ("Technology",              "Electronic",         MoatType.INTANGIBLE_ASSETS, 0.25),
    ("Technology",              None,                MoatType.SWITCHING_COSTS,   0.20),  # default tech
    ("Healthcare",              "Biotechnology",      MoatType.INTANGIBLE_ASSETS, 0.40),
    ("Healthcare",              "Drug",               MoatType.INTANGIBLE_ASSETS, 0.40),
    ("Healthcare",              None,                MoatType.INTANGIBLE_ASSETS, 0.30),
    ("Consumer Cyclical",       "Luxury",             MoatType.INTANGIBLE_ASSETS, 0.30),
    ("Consumer Cyclical",       "Apparel",            MoatType.INTANGIBLE_ASSETS, 0.20),
    ("Consumer Cyclical",       None,                MoatType.COST_ADVANTAGE,    0.20),
    ("Consumer Defensive",      None,                MoatType.COST_ADVANTAGE,    0.25),
    ("Financial Services",      "Insurance",          MoatType.EFFICIENT_SCALE,   0.20),
    ("Financial Services",      None,                MoatType.SWITCHING_COSTS,   0.20),
    ("Industrials",             None,                MoatType.COST_ADVANTAGE,    0.20),
    ("Utilities",               None,                MoatType.EFFICIENT_SCALE,   0.40),
    ("Real Estate",             None,                MoatType.EFFICIENT_SCALE,   0.35),
    ("Energy",                  None,                MoatType.COST_ADVANTAGE,    0.15),
    ("Basic Materials",         None,                MoatType.COST_ADVANTAGE,    0.15),
]


def _get_sector_prior(sector: str, industry: str) -> tuple[MoatType, float]:
    """
    Return (moat_type, prior_boost) for the given sector/industry.
    Industry substring match takes priority over sector-only match.
    Falls back to (NONE, 0.0) if nothing matches.
    """
    sector   = sector   or ""
    industry = industry or ""

    for s, ind_substr, moat, boost in _SECTOR_PRIORS:
        if s.lower() not in sector.lower():
            continue
        if ind_substr is None:
            # sector-only rule — record as fallback but keep scanning for industry match
            fallback = (moat, boost)
            continue
        if ind_substr.lower() in industry.lower():
            return moat, boost

    # return sector-only fallback if we found one
    for s, ind_substr, moat, boost in _SECTOR_PRIORS:
        if s.lower() in sector.lower() and ind_substr is None:
            return moat, boost

    return MoatType.NONE, 0.0


# ─────────────────────────────────────────────────────────────
# 2.  EXTENDED SIGNAL FETCHER
# ─────────────────────────────────────────────────────────────

def _safe_row(df, candidates: list[str]):
    for name in candidates:
        if name in df.index:
            return df.loc[name]
    return None


def fetch_extended_moat_signals(ticker: str) -> tuple[MoatSignals, str, str]:
    """
    Fetch all moat signals including the three new ones.
    Returns (MoatSignals, sector, industry).
    """
    s = MoatSignals()
    sector   = ""
    industry = ""
    t = yf.Ticker(ticker)

    # ── info dict (fast, low-fidelity) ───────────────────────
    try:
        info = t.info
        sector   = info.get("sector",   "") or ""
        industry = info.get("industry", "") or ""

        s.gross_margin     = float(info.get("grossMargins",    0.0) or 0.0)
        s.operating_margin = float(info.get("operatingMargins",0.0) or 0.0)

        revenue    = float(info.get("totalRevenue",  0.0) or 0.0)
        fcf        = float(info.get("freeCashflow",  0.0) or 0.0)
        total_assets = float(info.get("totalAssets", 0.0) or 0.0)
        capex      = abs(float(info.get("capitalExpenditures", 0.0) or 0.0))

        s.fcf_margin = (fcf / revenue)          if revenue > 0 else 0.0

        # NEW: asset lightness — platform companies score > 1.0
        s.asset_lightness = (revenue / total_assets) if total_assets > 0 else 0.0

        # NEW: capex intensity — low for asset-light platforms
        s.capex_intensity = (capex / revenue)   if revenue > 0 else 0.0

        de_raw = float(info.get("debtToEquity", 0.0) or 0.0) / 100.0
        s.debt_to_equity = max(0.0, 1.0 - min(de_raw / 3.0, 1.0))

    except Exception as exc:
        logger.warning("info-dict fetch failed for %s: %s", ticker, exc)

    # ── Annual financials (higher fidelity) ──────────────────
    try:
        fin = t.financials
        bs  = t.balance_sheet

        # ROIC
        ebit_row   = _safe_row(fin, ["EBIT", "Operating Income"])
        equity_row = _safe_row(bs,  ["Stockholders Equity",
                                     "Total Stockholder Equity",
                                     "Common Stock Equity"])
        debt_row   = _safe_row(bs,  ["Total Debt", "Long Term Debt"])
        if ebit_row is not None and equity_row is not None:
            ebit    = float(ebit_row.iloc[0])
            equity  = float(equity_row.iloc[0])
            debt    = float(debt_row.iloc[0]) if debt_row is not None else 0.0
            inv_cap = equity + debt
            s.roic  = (ebit * 0.79 / inv_cap) if inv_cap > 0 else 0.0
    except Exception as exc:
        logger.warning("ROIC fetch failed for %s: %s", ticker, exc)

    try:
        fin = t.financials
        rd_row  = _safe_row(fin, ["Research And Development",
                                  "Research Development",
                                  "Research & Development"])
        rev_row = _safe_row(fin, ["Total Revenue", "Revenue"])
        if rd_row is not None and rev_row is not None:
            rd  = float(rd_row.iloc[0])
            rev = float(rev_row.iloc[0])
            s.rd_intensity = (rd / rev) if rev > 0 else 0.0
    except Exception as exc:
        logger.warning("R&D fetch failed for %s: %s", ticker, exc)

    try:
        fin = t.financials
        rev_row = _safe_row(fin, ["Total Revenue", "Revenue"])
        if rev_row is not None and len(rev_row) >= 3:
            r_old = float(rev_row.iloc[-1])
            r_new = float(rev_row.iloc[0])
            n     = min(len(rev_row) - 1, 3)
            if r_old > 0:
                s.revenue_cagr_3y = (r_new / r_old) ** (1.0 / n) - 1.0
    except Exception as exc:
        logger.warning("CAGR fetch failed for %s: %s", ticker, exc)

    try:
        fin = t.financials
        gp_row  = _safe_row(fin, ["Gross Profit"])
        rev_row = _safe_row(fin, ["Total Revenue", "Revenue"])
        if gp_row is not None and rev_row is not None:
            margins = (gp_row / rev_row).dropna()
            if len(margins) > 1:
                s.gross_margin_stability = max(0.0, 1.0 - float(margins.std()) * 10.0)
    except Exception as exc:
        logger.warning("Stability fetch failed for %s: %s", ticker, exc)

    # NEW: R&D type discriminator = R&D intensity × Revenue CAGR
    # Large only for platform companies (high R&D + high growth)
    # Small for pharma/semis (high R&D + slow growth)
    s.rd_type_discriminator = s.rd_intensity * max(0.0, s.revenue_cagr_3y)

    return s, sector, industry


def detect_secondary_moats(
    scores: dict[str, float],
    primary_moat: str,
    threshold: float = 0.35,
    max_secondary: int = 4,
) -> list[str]:
    """Return secondary moat types ranked by score above the given threshold."""
    ranked = sorted(
        [
            (moat_name, score)
            for moat_name, score in scores.items()
            if moat_name not in {"none", primary_moat}
        ],
        key=lambda x: x[1],
        reverse=True,
    )

    selected: list[str] = []
    for moat_name, score in ranked:
        if score < threshold or len(selected) >= max_secondary:
            break
        selected.append(moat_name)
    return selected


# ─────────────────────────────────────────────────────────────
# 3.  FIXED SCORER
# ─────────────────────────────────────────────────────────────

def auto_detect_moat(
    ticker: str,
    return_scores: bool = False,
) -> tuple[MoatType, int, MoatSignals] | tuple[MoatType, int, MoatSignals, dict[str, float]]:
    """
    Two-layer moat classification.

    Layer 1: sector prior — adds a flat boost to the most likely moat type
             for the company's industry (e.g. Comm. Services → NE +0.40).

    Layer 2: signal scoring — same weighted formula as before, but with three
             new signals that break the META vs pharma tie:
             • asset_lightness        → rewards platform / marketplace models
             • capex_intensity        → rewards physical-infrastructure moats
             • rd_type_discriminator  → separates platform R&D from patent R&D

    Final score = signal_score + sector_prior (capped at 1.0)
    """
    s, sector, industry = fetch_extended_moat_signals(ticker)

    # ── Layer 2: signal scores ────────────────────────────────
    # asset_lightness: normalise at 2.0 (platforms like META/GOOG hit ~1.5)
    al_norm  = min(s.asset_lightness / 2.0, 1.0)
    # capex_intensity: normalise at 0.20 (utilities/pipelines ~15-25%)
    ci_norm  = min(s.capex_intensity / 0.20, 1.0)
    # rd_type: normalise at 0.04 (18% R&D × 22% CAGR = 0.04)
    rdt_norm = min(s.rd_type_discriminator / 0.04, 1.0)

    signal_scores: dict[MoatType, float] = {
        MoatType.NONE: 0.0,

        # Network Effects:
        #   Added: asset_lightness (platform model) + rd_type_discriminator
        #   Removed: gross_margin from NE (too noisy — both pharma and platforms have high GM)
        MoatType.NETWORK_EFFECTS: (
            min(s.revenue_cagr_3y / 0.25, 1.0) * 0.35   # growth momentum
            + al_norm                           * 0.30   # NEW: asset-light platform
            + rdt_norm                          * 0.20   # NEW: platform R&D (not patent)
            + s.fcf_margin                      * 0.15   # cash generation
        ),

        # Intangible Assets:
        #   Added: penalise if rd_type_discriminator is high (platform R&D, not patents)
        #   The rdt_norm subtraction distinguishes ASML/NVO from META/GOOG
        MoatType.INTANGIBLE_ASSETS: (
            s.gross_margin                      * 0.45   # premium pricing from IP
            + min(s.rd_intensity / 0.15, 1.0)  * 0.30   # patent reinvestment
            + s.operating_margin                * 0.20   # structural profitability
            - rdt_norm                          * 0.15   # PENALTY: platform R&D hurts IA
        ),

        # Switching Costs:
        #   Unchanged — ROIC + margin stability is still the right signal
        MoatType.SWITCHING_COSTS: (
            s.gross_margin_stability            * 0.35
            + min(s.roic / 0.30, 1.0)          * 0.40
            + s.operating_margin                * 0.25
        ),

        # Cost Advantage:
        #   Added: capex intensity (scale economies need physical assets)
        MoatType.COST_ADVANTAGE: (
            s.fcf_margin                        * 0.35
            + s.operating_margin                * 0.25
            + ci_norm                           * 0.20   # NEW: capex = scale investment
            + s.gross_margin                    * 0.20
        ),

        # Efficient Scale:
        #   Added: high capex_intensity strongly indicates regulated infrastructure
        MoatType.EFFICIENT_SCALE: (
            s.gross_margin_stability            * 0.30
            + s.debt_to_equity                  * 0.20
            + ci_norm                           * 0.30   # NEW: infra capex
            + (1.0 - min(s.revenue_cagr_3y / 0.10, 1.0)) * 0.20  # mature market
        ),
    }

    # ── Layer 1: sector prior boost ───────────────────────────
    prior_type, prior_boost = _get_sector_prior(sector, industry)
    if prior_type != MoatType.NONE:
        signal_scores[prior_type] = min(1.0, signal_scores[prior_type] + prior_boost)

    best_type  = max(signal_scores, key=lambda x: signal_scores[x])
    best_score = signal_scores[best_type]

    # ── Moat width from overall quality ──────────────────────
    quality = (
        s.gross_margin             * 0.25
        + s.operating_margin       * 0.25
        + s.fcf_margin             * 0.25
        + s.gross_margin_stability * 0.25
    )
    if   quality < 0.10: width = 0
    elif quality < 0.25: width = 1
    elif quality < 0.45: width = 2
    else:                width = 3

    if best_score < 0.10:
        if return_scores:
            return MoatType.NONE, 0, s, {k.value: v for k, v in signal_scores.items()}
        return MoatType.NONE, 0, s

    logger.info(
        "%s → sector='%s' industry='%s' prior=(%s +%.2f) "
        "scores=%s → %s (width=%d)",
        ticker, sector, industry,
        prior_type.value, prior_boost,
        {k.value: f"{v:.2f}" for k, v in signal_scores.items()},
        best_type.value, width,
    )

    if return_scores:
        return best_type, width, s, {k.value: v for k, v in signal_scores.items()}
    return best_type, width, s


# ─────────────────────────────────────────────────────────────
# 4.  DEBUG HELPER  (run standalone to inspect any ticker)
# ─────────────────────────────────────────────────────────────

def explain_moat(ticker: str) -> None:
    """
    Print a full breakdown of every signal and score for a ticker.
    Useful for debugging misclassifications.

    Usage:
        python -m src.models.moat_detector AAPL
        python -m src.models.moat_detector META
    """
    s, sector, industry = fetch_extended_moat_signals(ticker)
    prior_type, prior_boost = _get_sector_prior(sector, industry)
    moat_type, width, _ = auto_detect_moat(ticker)

    al_norm  = min(s.asset_lightness / 2.0, 1.0)
    ci_norm  = min(s.capex_intensity / 0.20, 1.0)
    rdt_norm = min(s.rd_type_discriminator / 0.04, 1.0)

    print(f"\n{'='*56}")
    print(f"  MOAT EXPLANATION — {ticker.upper()}")
    print(f"{'='*56}")
    print(f"  Sector   : {sector}")
    print(f"  Industry : {industry}")
    print(f"  Sector prior → {prior_type.value}  +{prior_boost:.2f}")
    print(f"\n  RAW SIGNALS")
    print(f"  {'Gross Margin':<28} {s.gross_margin:>8.1%}")
    print(f"  {'Operating Margin':<28} {s.operating_margin:>8.1%}")
    print(f"  {'FCF Margin':<28} {s.fcf_margin:>8.1%}")
    print(f"  {'Revenue CAGR 3Y':<28} {s.revenue_cagr_3y:>8.1%}")
    print(f"  {'R&D Intensity':<28} {s.rd_intensity:>8.1%}")
    print(f"  {'ROIC':<28} {s.roic:>8.1%}")
    print(f"  {'Margin Stability':<28} {s.gross_margin_stability:>8.1%}")
    print(f"  {'Asset Lightness (Rev/Assets)':<28} {s.asset_lightness:>8.2f}")
    print(f"  {'CapEx Intensity':<28} {s.capex_intensity:>8.1%}")
    print(f"  {'R&D Type Discriminator':<28} {s.rd_type_discriminator:>8.3f}")
    print(f"\n  NORMALISED INPUTS")
    print(f"  {'al_norm (platform proxy)':<28} {al_norm:>8.2f}")
    print(f"  {'ci_norm (infra proxy)':<28} {ci_norm:>8.2f}")
    print(f"  {'rdt_norm (platform R&D)':<28} {rdt_norm:>8.2f}")
    print(f"\n  FINAL DECISION")
    print(f"  {'Moat Type':<28} {moat_type.value}")
    print(f"  {'Moat Width':<28} {MOAT_WIDTH_LABELS.get(width,'?')} ({width}/3)")
    print(f"{'='*56}\n")


if __name__ == "__main__":
    import sys
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["META", "AAPL", "ASML", "NVO", "NEE", "MSFT"]
    for t in tickers:
        explain_moat(t.upper())