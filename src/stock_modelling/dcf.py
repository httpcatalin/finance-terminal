"""
Moat-adjusted discounted cash flow (DCF) engine.

Fixes in this version:
1) Discount rate uses nominal CAPM only (no CPI double counting)
2) ROIC computed from annual financial statements
3) R&D intensity computed from annual financial statements
4) Revenue CAGR isolated from other signal calculations
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import yfinance as yf


logger = logging.getLogger(__name__)


class MoatType(Enum):
    NONE = "none"
    COST_ADVANTAGE = "cost_advantage"
    NETWORK_EFFECTS = "network_effects"
    SWITCHING_COSTS = "switching_costs"
    INTANGIBLE_ASSETS = "intangible_assets"
    EFFICIENT_SCALE = "efficient_scale"


PRIMARY_MOAT_REDUCTION: dict[str, float] = {
    "none": 0.000,
    "network_effects": 0.030,
    "switching_costs": 0.030,
    "efficient_scale": 0.027,
    "intangible_assets": 0.025,
    "cost_advantage": 0.022,
}

SECONDARY_MOAT_BONUSES: list[float] = [0.0075, 0.0060, 0.0050, 0.0040]
MAX_TOTAL_REDUCTION = 0.060
SECONDARY_MOAT_THRESHOLD = 0.35

MOAT_WIDTH_LABELS = {0: "None", 1: "Narrow", 2: "Wide", 3: "Fortress"}


@dataclass
class MoatSignals:
    gross_margin: float = 0.0
    operating_margin: float = 0.0
    revenue_cagr_3y: float = 0.0
    fcf_margin: float = 0.0
    rd_intensity: float = 0.0
    roic: float = 0.0
    gross_margin_stability: float = 0.0
    debt_to_equity: float = 0.0
    asset_lightness: float = 0.0
    capex_intensity: float = 0.0
    rd_type_discriminator: float = 0.0


_SECTOR_PRIORS: list[tuple[str, Optional[str], MoatType, float]] = [
    ("Communication Services", None, MoatType.NETWORK_EFFECTS, 0.40),
    ("Technology", "Internet", MoatType.NETWORK_EFFECTS, 0.25),
    ("Technology", "Software", MoatType.SWITCHING_COSTS, 0.30),
    ("Technology", "Semiconductor", MoatType.INTANGIBLE_ASSETS, 0.30),
    ("Technology", "Electronic", MoatType.INTANGIBLE_ASSETS, 0.25),
    ("Technology", None, MoatType.SWITCHING_COSTS, 0.20),
    ("Healthcare", "Biotechnology", MoatType.INTANGIBLE_ASSETS, 0.40),
    ("Healthcare", "Drug", MoatType.INTANGIBLE_ASSETS, 0.40),
    ("Healthcare", None, MoatType.INTANGIBLE_ASSETS, 0.30),
    ("Consumer Cyclical", "Luxury", MoatType.INTANGIBLE_ASSETS, 0.30),
    ("Consumer Cyclical", "Apparel", MoatType.INTANGIBLE_ASSETS, 0.20),
    ("Consumer Cyclical", None, MoatType.COST_ADVANTAGE, 0.20),
    ("Consumer Defensive", None, MoatType.COST_ADVANTAGE, 0.25),
    ("Financial Services", "Insurance", MoatType.EFFICIENT_SCALE, 0.20),
    ("Financial Services", None, MoatType.SWITCHING_COSTS, 0.20),
    ("Industrials", None, MoatType.COST_ADVANTAGE, 0.20),
    ("Utilities", None, MoatType.EFFICIENT_SCALE, 0.40),
    ("Real Estate", None, MoatType.EFFICIENT_SCALE, 0.35),
    ("Energy", None, MoatType.COST_ADVANTAGE, 0.15),
    ("Basic Materials", None, MoatType.COST_ADVANTAGE, 0.15),
]


def _get_sector_prior(sector: str, industry: str) -> tuple[MoatType, float]:
    sector = sector or ""
    industry = industry or ""

    for sec, ind_substr, moat, boost in _SECTOR_PRIORS:
        if sec.lower() not in sector.lower():
            continue
        if ind_substr is not None and ind_substr.lower() in industry.lower():
            return moat, boost

    for sec, ind_substr, moat, boost in _SECTOR_PRIORS:
        if sec.lower() in sector.lower() and ind_substr is None:
            return moat, boost

    return MoatType.NONE, 0.0


@dataclass
class DiscountRateComponents:
    risk_free_rate: float
    beta: float
    equity_risk_premium: float
    company_risk_spread: float
    raw_capm_rate: float
    primary_moat_type: str
    primary_moat_width: int
    primary_moat_reduction: float
    secondary_moats: list[str]
    secondary_moat_reduction: float
    total_moat_reduction: float
    inflation_rate: float
    final_rate: float
    discount_source: str = "auto"

    def __str__(self) -> str:
        src_tag = " (user-defined)" if self.discount_source == "user-defined" else ""

        if self.secondary_moats:
            sec_names = ", ".join(m.replace("_", " ") for m in self.secondary_moats)
            sec_label = f"Secondary moats ({sec_names})"
            sec_rate = f"{-self.secondary_moat_reduction:>7.2%}"
            sec_added = "yes"
        else:
            sec_label = "No confirmed secondary moats"
            sec_rate = f"{'-':>7}"
            sec_added = ""

        return "\n".join(
            [
                "",
                f"  {'Component':<38}{'Rate':>7}  {'Added?':>7}",
                f"  {'-' * 52}",
                f"  {'Risk-free rate (T10Y nominal)':<38}{self.risk_free_rate:>7.2%}  {'yes':>7}",
                (
                    f"  {'Beta (' + f'{self.beta:.2f}' + ') x ERP (' + f'{self.equity_risk_premium:.2%}' + ')':<38}"
                    f"{self.company_risk_spread:>7.2%}  {'yes':>7}"
                ),
                f"  {'- ERP shown above (Rm-Rf), not added separately':<38}{'':>7}  {'':>7}",
                f"  {'-' * 52}",
                f"  {'Raw CAPM rate':<38}{self.raw_capm_rate:>7.2%}",
                f"  {'-' * 52}",
                (
                    f"  {'Primary moat (' + self.primary_moat_type.replace('_', ' ') + ', w=' + str(self.primary_moat_width) + '/3)':<38}"
                    f"{-self.primary_moat_reduction:>7.2%}  {'yes':>7}"
                ),
                f"  {sec_label:<38}{sec_rate}  {sec_added:>7}",
                f"  {'-' * 52}",
                f"  {'Total moat reduction':<38}{-self.total_moat_reduction:>7.2%}",
                f"  {'=' * 52}",
                f"  {'Final discount rate' + src_tag:<38}{self.final_rate:>7.2%}",
                "",
                f"  {'CPI (context only, not added)':<38}{self.inflation_rate:>7.2%}",
                "  Both T10Y and S&P return are nominal - CPI already embedded.",
                "",
            ]
        )


@dataclass
class DCFResult:
    ticker: str
    intrinsic_value: float
    current_price: float
    margin_of_safety: float
    projected_fcfs: list[float]
    terminal_value: float
    pv_fcfs: float
    pv_terminal: float
    discount_rate_details: DiscountRateComponents
    moat_type: MoatType
    moat_width: int
    moat_signals: MoatSignals
    growth_rate: float
    terminal_growth_rate: float
    years: int
    tgr_source: str = "default"
    discount_source: str = "auto"

    def print_report(self) -> None:
        moat_label = MOAT_WIDTH_LABELS.get(self.moat_width, "?")
        mos_pct = self.margin_of_safety * 100.0
        tgr_tag = "(user-defined)" if self.tgr_source == "user-defined" else "(default 3%)"

        print("\n" + "=" * 60)
        print(f"  DCF ANALYSIS - {self.ticker}")
        print("=" * 60)
        print(f"  Moat Type   : {self.moat_type.value.replace('_', ' ').title()}")
        print(f"  Moat Width  : {moat_label} ({self.moat_width}/3)")

        print("\n  KEY SIGNALS")
        print(f"  {'Gross Margin':<26} {self.moat_signals.gross_margin:>8.1%}")
        print(f"  {'Operating Margin':<26} {self.moat_signals.operating_margin:>8.1%}")
        print(f"  {'FCF Margin':<26} {self.moat_signals.fcf_margin:>8.1%}")
        print(f"  {'ROIC':<26} {self.moat_signals.roic:>8.1%}")
        print(f"  {'Revenue CAGR 3Y':<26} {self.moat_signals.revenue_cagr_3y:>8.1%}")
        print(f"  {'R&D Intensity':<26} {self.moat_signals.rd_intensity:>8.1%}")
        print(f"  {'Margin Stability':<26} {self.moat_signals.gross_margin_stability:>8.1%}")

        print("\n  DISCOUNT RATE BREAKDOWN")
        print(str(self.discount_rate_details))
        print(
            f"  {'Discount rate source':<26} "
            f"{'user-defined' if self.discount_source == 'user-defined' else 'auto (CAPM + moat)'}"
        )

        print("  VALUATION")
        print(f"  {'FCF Growth Rate':<26} {self.growth_rate:>8.1%}   <- applied to free cash flow each year")
        print(f"  {'Terminal Growth Rate':<26} {self.terminal_growth_rate:>8.1%}   {tgr_tag}")
        print(f"  {'Projection Years':<26} {self.years:>8}")
        print(f"  {'PV of FCFs':<26} ${self.pv_fcfs:>14,.0f}")
        print(f"  {'PV of Terminal':<26} ${self.pv_terminal:>14,.0f}")
        print(f"\n  {'Intrinsic Value / Share':<26} ${self.intrinsic_value:>10.2f}")
        print(f"  {'Current Price':<26} ${self.current_price:>10.2f}")
        print(f"  {'Margin of Safety':<26} {mos_pct:>9.1f}%")
        print("=" * 60 + "\n")


def _safe_row(df, candidates: list[str]):
    if df is None or df.empty:
        return None
    for name in candidates:
        if name in df.index:
            return df.loc[name]
    return None


def _fetch_macro_rates() -> dict[str, float]:
    values = {
        "risk_free_rate": 0.043,
        "inflation_rate": 0.031,
        "sp500_return": 0.100,
    }

    try:
        tnx = yf.Ticker("^TNX").history(period="5d")
        if tnx is not None and not tnx.empty:
            values["risk_free_rate"] = float(tnx["Close"].iloc[-1]) / 100.0
    except Exception as exc:
        logger.warning("Could not fetch ^TNX: %s", exc)

    try:
        spx = yf.Ticker("^GSPC").history(period="10y")
        if spx is not None and len(spx) > 250:
            start_p = float(spx["Close"].iloc[0])
            end_p = float(spx["Close"].iloc[-1])
            yrs = max(len(spx) / 252.0, 1.0)
            values["sp500_return"] = (end_p / start_p) ** (1.0 / yrs) - 1.0
    except Exception as exc:
        logger.warning("Could not fetch ^GSPC: %s", exc)

    return values


def _fetch_moat_signals(ticker: str) -> tuple[MoatSignals, str, str]:
    s = MoatSignals()
    sector = ""
    industry = ""
    t = yf.Ticker(ticker)

    try:
        info = t.info
        sector = info.get("sector", "") or ""
        industry = info.get("industry", "") or ""
        s.gross_margin = float(info.get("grossMargins", 0.0) or 0.0)
        s.operating_margin = float(info.get("operatingMargins", 0.0) or 0.0)

        revenue = float(info.get("totalRevenue", 0.0) or 0.0)
        fcf = float(info.get("freeCashflow", 0.0) or 0.0)
        total_assets = float(info.get("totalAssets", 0.0) or 0.0)
        capex = abs(float(info.get("capitalExpenditures", 0.0) or 0.0))

        s.fcf_margin = (fcf / revenue) if revenue > 0 else 0.0
        s.asset_lightness = (revenue / total_assets) if total_assets > 0 else 0.0
        s.capex_intensity = (capex / revenue) if revenue > 0 else 0.0

        de_raw = float(info.get("debtToEquity", 0.0) or 0.0) / 100.0
        s.debt_to_equity = max(0.0, 1.0 - min(de_raw / 3.0, 1.0))
    except Exception as exc:
        logger.warning("info fetch failed for %s: %s", ticker, exc)

    # Fallbacks for asset-lightness/capex-intensity from statements.
    if s.asset_lightness == 0.0 or s.capex_intensity == 0.0:
        try:
            fin = t.financials
            bs = t.balance_sheet
            cf = t.cashflow

            rev_row = _safe_row(fin, ["Total Revenue", "Revenue"])
            assets_row = _safe_row(bs, ["Total Assets"])
            capex_row = _safe_row(
                cf,
                ["Capital Expenditure", "Capital Expenditures", "Purchase Of PPE", "Purchase Of Property Plant And Equipment"],
            )

            revenue_stmt = float(rev_row.iloc[0]) if rev_row is not None else 0.0
            assets_stmt = float(assets_row.iloc[0]) if assets_row is not None else 0.0
            capex_stmt = abs(float(capex_row.iloc[0])) if capex_row is not None else 0.0

            if s.asset_lightness == 0.0 and revenue_stmt > 0 and assets_stmt > 0:
                s.asset_lightness = revenue_stmt / assets_stmt
            if s.capex_intensity == 0.0 and revenue_stmt > 0 and capex_stmt > 0:
                s.capex_intensity = capex_stmt / revenue_stmt
        except Exception as exc:
            logger.warning("Asset-lightness/capex fallback failed for %s: %s", ticker, exc)

    try:
        fin = t.financials
        bs = t.balance_sheet

        ebit_row = _safe_row(fin, ["EBIT", "Operating Income"]) 
        equity_row = _safe_row(bs, ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"])
        debt_row = _safe_row(bs, ["Total Debt", "Long Term Debt"])

        if ebit_row is not None and equity_row is not None:
            ebit = float(ebit_row.iloc[0])
            equity = float(equity_row.iloc[0])
            debt = float(debt_row.iloc[0]) if debt_row is not None else 0.0
            inv_cap = equity + debt
            nopat = ebit * (1.0 - 0.21)
            s.roic = (nopat / inv_cap) if inv_cap > 0 else 0.0
    except Exception as exc:
        logger.warning("ROIC calc failed for %s: %s", ticker, exc)

    try:
        fin = t.financials
        rd_row = _safe_row(fin, ["Research And Development", "Research Development", "Research & Development"])
        rev_row = _safe_row(fin, ["Total Revenue", "Revenue"])
        if rd_row is not None and rev_row is not None:
            rd = float(rd_row.iloc[0])
            rev = float(rev_row.iloc[0])
            s.rd_intensity = (rd / rev) if rev > 0 else 0.0
    except Exception as exc:
        logger.warning("R&D intensity failed for %s: %s", ticker, exc)

    try:
        fin = t.financials
        rev_row = _safe_row(fin, ["Total Revenue", "Revenue"])
        if rev_row is not None and len(rev_row) >= 3:
            r_old = float(rev_row.iloc[-1])
            r_new = float(rev_row.iloc[0])
            n = min(len(rev_row) - 1, 3)
            if r_old > 0:
                s.revenue_cagr_3y = (r_new / r_old) ** (1.0 / n) - 1.0
    except Exception as exc:
        logger.warning("Revenue CAGR failed for %s: %s", ticker, exc)

    # Fallback when annual statement history is incomplete.
    if s.revenue_cagr_3y == 0.0:
        try:
            info = t.info
            s.revenue_cagr_3y = float(info.get("revenueGrowth", 0.0) or 0.0)
        except Exception:
            pass

    try:
        fin = t.financials
        gp_row = _safe_row(fin, ["Gross Profit"])
        rev_row = _safe_row(fin, ["Total Revenue", "Revenue"])
        if gp_row is not None and rev_row is not None:
            margins = (gp_row / rev_row).dropna()
            if len(margins) > 1:
                std = float(margins.std())
                s.gross_margin_stability = max(0.0, 1.0 - std * 10.0)
    except Exception as exc:
        logger.warning("Margin stability failed for %s: %s", ticker, exc)

    s.rd_type_discriminator = s.rd_intensity * max(0.0, s.revenue_cagr_3y)

    return s, sector, industry


def auto_detect_moat(
    ticker: str,
    return_scores: bool = False,
) -> tuple[MoatType, int, MoatSignals] | tuple[MoatType, int, MoatSignals, dict[str, float]]:
    s, sector, industry = _fetch_moat_signals(ticker)

    al_norm = min(s.asset_lightness / 2.0, 1.0)
    ci_norm = min(s.capex_intensity / 0.20, 1.0)
    rdt_norm = min(s.rd_type_discriminator / 0.04, 1.0)

    scores: dict[MoatType, float] = {
        MoatType.NONE: 0.0,
        MoatType.NETWORK_EFFECTS: (
            min(s.revenue_cagr_3y / 0.25, 1.0) * 0.35
            + al_norm * 0.30
            + rdt_norm * 0.20
            + s.fcf_margin * 0.15
        ),
        MoatType.INTANGIBLE_ASSETS: (
            s.gross_margin * 0.45
            + min(s.rd_intensity / 0.15, 1.0) * 0.30
            + s.operating_margin * 0.20
            - rdt_norm * 0.15
        ),
        MoatType.SWITCHING_COSTS: (
            s.gross_margin_stability * 0.35
            + min(s.roic / 0.30, 1.0) * 0.40
            + s.operating_margin * 0.25
        ),
        MoatType.COST_ADVANTAGE: (
            s.fcf_margin * 0.35
            + s.operating_margin * 0.25
            + ci_norm * 0.20
            + s.gross_margin * 0.20
        ),
        MoatType.EFFICIENT_SCALE: (
            s.gross_margin_stability * 0.30
            + s.debt_to_equity * 0.20
            + ci_norm * 0.30
            + (1.0 - min(s.revenue_cagr_3y / 0.10, 1.0)) * 0.20
        ),
    }

    prior_type, prior_boost = _get_sector_prior(sector, industry)
    if prior_type != MoatType.NONE:
        scores[prior_type] = min(1.0, scores[prior_type] + prior_boost)

    best_type = max(scores, key=lambda x: scores[x])
    best_score = scores[best_type]

    quality = (
        s.gross_margin * 0.25
        + s.operating_margin * 0.25
        + s.fcf_margin * 0.25
        + s.gross_margin_stability * 0.25
    )
    if quality < 0.10:
        width = 0
    elif quality < 0.25:
        width = 1
    elif quality < 0.45:
        width = 2
    else:
        width = 3

    if best_score < 0.10:
        if return_scores:
            return MoatType.NONE, 0, s, {k.value: v for k, v in scores.items()}
        return MoatType.NONE, 0, s

    logger.info(
        "%s -> sector='%s' industry='%s' prior=(%s +%.2f) scores=%s -> %s (width=%d)",
        ticker,
        sector,
        industry,
        prior_type.value,
        prior_boost,
        {k.value: f"{v:.2f}" for k, v in scores.items()},
        best_type.value,
        width,
    )

    if return_scores:
        return best_type, width, s, {k.value: v for k, v in scores.items()}
    return best_type, width, s


def build_discount_rate(
    ticker: str,
    moat_type: str,
    moat_width: int,
    all_moat_scores: Optional[dict[str, float]] = None,
    beta_override: Optional[float] = None,
    macro_override: Optional[dict[str, float]] = None,
    discount_source: str = "auto",
    discount_rate_override: Optional[float] = None,
) -> DiscountRateComponents:
    macro = macro_override or _fetch_macro_rates()
    rfr = macro["risk_free_rate"]
    cpi = macro["inflation_rate"]
    sp500_ret = macro["sp500_return"]

    beta = beta_override
    if beta is None:
        try:
            beta = float(yf.Ticker(ticker).info.get("beta", 1.0) or 1.0)
        except Exception:
            beta = 1.0
    beta = max(0.2, float(beta))

    erp = sp500_ret - rfr
    company_risk = beta * erp
    raw_rate = rfr + company_risk

    width_factor = max(0, min(moat_width, 3)) / 3.0
    base_primary = PRIMARY_MOAT_REDUCTION.get(moat_type, 0.0)
    primary_reduction = base_primary * width_factor

    secondary_moats: list[str] = []
    secondary_reduction = 0.0
    if all_moat_scores is not None:
        ranked = sorted(
            [
                (m_type, score)
                for m_type, score in all_moat_scores.items()
                if m_type != "none" and m_type != moat_type
            ],
            key=lambda x: x[1],
            reverse=True,
        )
        for idx, (m_type, score) in enumerate(ranked):
            if score < SECONDARY_MOAT_THRESHOLD or idx >= len(SECONDARY_MOAT_BONUSES):
                break
            secondary_moats.append(m_type)
            secondary_reduction += SECONDARY_MOAT_BONUSES[idx] * width_factor

    total_reduction = min(primary_reduction + secondary_reduction, MAX_TOTAL_REDUCTION)

    if discount_rate_override is not None:
        final_rate = float(discount_rate_override)
        discount_source = "user-defined"
    else:
        final_rate = max(rfr, raw_rate - total_reduction)

    return DiscountRateComponents(
        risk_free_rate=rfr,
        beta=beta,
        inflation_rate=cpi,
        equity_risk_premium=erp,
        company_risk_spread=company_risk,
        raw_capm_rate=raw_rate,
        primary_moat_type=moat_type,
        primary_moat_width=moat_width,
        primary_moat_reduction=primary_reduction,
        secondary_moats=secondary_moats,
        secondary_moat_reduction=secondary_reduction,
        total_moat_reduction=total_reduction,
        final_rate=final_rate,
        discount_source=discount_source,
    )


def calculate_dcf(
    ticker: str,
    growth_rate: float = 0.07,
    years: int = 10,
    terminal_growth_rate: float = 0.03,
    discount_rate_override: Optional[float] = None,
    beta_override: Optional[float] = None,
    moat_type_override: Optional[str] = None,
    moat_width_override: Optional[int] = None,
    shares_outstanding_override: Optional[float] = None,
    tgr_source: str = "default",
    discount_source: str = "auto",
    verbose: bool = True,
) -> DCFResult:
    """
    Full moat-adjusted DCF calculation.

    Parameters
    ----------
    ticker                     : Stock ticker, e.g. "AAPL"
    growth_rate                : Expected FCF growth rate during projection period
    years                      : Projection horizon (default 10)
    terminal_growth_rate       : Perpetuity growth rate (default 3% = long-run GDP)
    discount_rate_override     : Skip auto-computation and use this rate directly
    moat_type_override         : Force a specific moat type ("switching_costs", etc.)
    moat_width_override        : Force moat width 0-3
    shares_outstanding_override: Override share count for intrinsic value per share
    verbose                    : Print the report to stdout
    """

    ticker = ticker.upper().strip()
    info = yf.Ticker(ticker).info

    fcf = float(info.get("freeCashflow", 0.0) or 0.0)
    if fcf <= 0:
        fcf = float(info.get("operatingCashflow", 0.0) or 0.0)
    if fcf <= 0:
        raise ValueError(
            f"Cannot compute DCF for {ticker}: FCF is non-positive ({fcf:,.0f}). The company may not yet be cash-flow-positive."
        )

    shares = shares_outstanding_override or float(info.get("sharesOutstanding", 1.0) or 1.0)
    current_price = float(info.get("currentPrice", 0.0) or info.get("regularMarketPrice", 0.0) or 0.0)

    if moat_type_override:
        try:
            moat_type = MoatType(moat_type_override.lower())
        except ValueError:
            moat_type = MoatType.NONE
            logger.warning("Unknown moat type '%s'; defaulting to none", moat_type_override)
        moat_signals, _, _ = _fetch_moat_signals(ticker)
        moat_width = moat_width_override if moat_width_override is not None else 2
        all_scores = None
    else:
        moat_type, moat_width, moat_signals, all_scores = auto_detect_moat(ticker, return_scores=True)
        if moat_width_override is not None:
            moat_width = moat_width_override

    moat_width = max(0, min(int(moat_width), 3))

    dr = build_discount_rate(
        ticker=ticker,
        moat_type=moat_type.value,
        moat_width=moat_width,
        all_moat_scores=all_scores,
        beta_override=beta_override,
        discount_source=discount_source,
        discount_rate_override=discount_rate_override,
    )

    rate = dr.final_rate
    if rate <= 0:
        raise ValueError(f"Invalid discount rate for {ticker}: {rate:.4f}")

    tgr = min(float(terminal_growth_rate), rate - 0.01)

    if discount_rate_override is not None:
        discount_source = "user-defined"

    projected_fcfs: list[float] = []
    pv_fcfs = 0.0
    running = fcf
    for yr in range(1, int(years) + 1):
        running *= 1.0 + float(growth_rate)
        projected_fcfs.append(running)
        pv_fcfs += running / ((1.0 + rate) ** yr)

    terminal_value = (running * (1.0 + tgr)) / (rate - tgr)
    pv_terminal = terminal_value / ((1.0 + rate) ** int(years))

    total_pv = pv_fcfs + pv_terminal
    intrinsic_value = total_pv / shares
    margin_of_safety = (intrinsic_value - current_price) / intrinsic_value if intrinsic_value > 0 else -1.0

    result = DCFResult(
        ticker=ticker,
        intrinsic_value=intrinsic_value,
        current_price=current_price,
        margin_of_safety=margin_of_safety,
        projected_fcfs=projected_fcfs,
        terminal_value=terminal_value,
        pv_fcfs=pv_fcfs,
        pv_terminal=pv_terminal,
        discount_rate_details=dr,
        moat_type=moat_type,
        moat_width=moat_width,
        moat_signals=moat_signals,
        growth_rate=float(growth_rate),
        terminal_growth_rate=tgr,
        years=int(years),
        tgr_source=tgr_source,
        discount_source=discount_source,
    )

    if verbose:
        result.print_report()

    return result


def dcf_sensitivity_table(
    ticker: str,
    growth_rates: list[float] = [0.03, 0.05, 0.07, 0.10, 0.15],
    moat_widths: list[int] = [0, 1, 2, 3],
    years: int = 10,
) -> None:
    moat_type, _, _ = auto_detect_moat(ticker)
    header = f"\n  Sensitivity - {ticker.upper()} | rows: FCF growth | cols: moat width\n"
    header += f"  {'Growth':>8}" + "".join(f"  {f'Width {w}':>12}" for w in moat_widths)
    print(header)
    print("  " + "-" * 56)
    for gr in growth_rates:
        row = f"  {gr:>7.0%} "
        for w in moat_widths:
            try:
                res = calculate_dcf(
                    ticker,
                    growth_rate=gr,
                    years=years,
                    moat_type_override=moat_type.value,
                    moat_width_override=w,
                    verbose=False,
                )
                row += f"  ${res.intrinsic_value:>10,.2f}"
            except Exception:
                row += f"  {'N/A':>11}"
        print(row)
    print()


def implied_growth_rate(
    ticker: str,
    years: int = 10,
    moat_type_override: Optional[str] = None,
    moat_width_override: Optional[int] = None,
    tol: float = 1e-5,
    max_iter: int = 200,
) -> float:
    info = yf.Ticker(ticker.upper()).info
    price = float(info.get("currentPrice", 0) or info.get("regularMarketPrice", 0) or 0)
    if price <= 0:
        raise ValueError(f"Cannot fetch current price for {ticker}")

    lo, hi, mid = -0.20, 1.00, 0.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        try:
            res = calculate_dcf(
                ticker,
                growth_rate=mid,
                years=years,
                moat_type_override=moat_type_override,
                moat_width_override=moat_width_override,
                verbose=False,
            )
            diff = res.intrinsic_value - price
            if abs(diff) < tol:
                break
            if diff > 0:
                hi = mid
            else:
                lo = mid
        except Exception:
            break

    print(f"\n  Reverse DCF - {ticker.upper()}")
    print(f"  Market pricing in FCF CAGR of ~= {mid:.2%} over {years} years\n")
    return mid


if __name__ == "__main__":
    import sys

    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    calculate_dcf(ticker, growth_rate=0.15, years=10)
