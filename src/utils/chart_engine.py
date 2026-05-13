"""
Chart engine — interactive Plotly charts for the option pricing terminal.

Chart types:
  1. Payoff / P&L diagram (strategy legs)
  2. BSM Greek sensitivity sweep
  3. Volatility surface / smile
  4. Model comparison bar chart
  5. GARCH vol forecast
  6. VaR histogram
  7. ARIMA forecast
  8. Binomial convergence
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np

OptionType = Literal["call", "put"]

_LAYOUT_DEFAULTS = dict(
    template="plotly_dark",
    margin=dict(l=60, r=30, t=50, b=50),
    font=dict(size=12),
)


def _go():
    """Import plotly lazily to keep module load fast."""
    import plotly.graph_objects as go
    return go


def _show(fig, save_path: str | None = None, show: bool = True):
    """Render a figure — writes HTML to disk or opens in browser."""
    if save_path:
        fig.write_html(save_path)
        print(f"  Chart saved to {save_path}")
    if show:
        fig.show()


# ---------------------------------------------------------------------------
# 1. Payoff / P&L diagram
# ---------------------------------------------------------------------------

def plot_payoff(
    legs: list,
    S_current: float,
    T: float = 0.0,
    r: float = 0.05,
    sigma: float = 0.20,
    q: float = 0.0,
    S_min: float | None = None,
    S_max: float | None = None,
    save_path: str | None = None,
    show: bool = True,
) -> None:
    from ..option_pricing.strategies import payoff_at_expiry
    from ..option_pricing.bsm import bsm_price

    go = _go()

    strikes = [l.strike for l in legs if hasattr(l, "option_type") and l.option_type != "stock"]
    if S_min is None:
        S_min = min(strikes + [S_current]) * 0.6
    if S_max is None:
        S_max = max(strikes + [S_current]) * 1.4

    S_range = np.linspace(S_min, S_max, 500)
    expiry_payoff = payoff_at_expiry(legs, S_range)

    today_pnl = None
    if T > 0 and sigma > 0:
        today_pnl = np.zeros_like(S_range)
        for leg in legs:
            sign = 1.0 if leg.side == "long" else -1.0
            qty = leg.quantity
            if leg.option_type == "stock":
                today_pnl += sign * qty * (S_range - leg.strike - leg.premium)
            else:
                for i, s in enumerate(S_range):
                    bsm_val = bsm_price(s, leg.strike, T, r, sigma, leg.option_type, q)
                    today_pnl[i] += sign * qty * (bsm_val - leg.premium)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=S_range, y=expiry_payoff, mode="lines",
                             name="Payoff at expiry", line=dict(color="#2196F3", width=2)))
    if today_pnl is not None:
        fig.add_trace(go.Scatter(x=S_range, y=today_pnl, mode="lines",
                                 name=f"P&L today (T={T:.3f})", line=dict(color="#FF5252", dash="dash", width=1.5)))
    fig.add_hline(y=0, line_color="gray", line_width=0.5)
    fig.add_vline(x=S_current, line_color="green", line_dash="dot", opacity=0.7,
                  annotation_text=f"Spot={S_current:.2f}")
    fig.update_layout(xaxis_title="Underlying Price at Expiry", yaxis_title="Profit / Loss",
                      title="Strategy Payoff Diagram", **_LAYOUT_DEFAULTS)
    _show(fig, save_path, show)


# ---------------------------------------------------------------------------
# 2. BSM Greek sensitivity sweep
# ---------------------------------------------------------------------------

def plot_greek(
    greek_name: str,
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    vs: str = "spot",
    save_path: str | None = None,
    show: bool = True,
) -> None:
    from ..option_pricing import greeks as grk

    go = _go()
    greek_fn = getattr(grk, greek_name, None)
    if greek_fn is None:
        raise ValueError(f"Unknown Greek: {greek_name}")

    needs_type = greek_name in ("delta", "theta", "rho")

    if vs == "spot":
        x = np.linspace(S * 0.5, S * 1.5, 200)
        x_label = "Spot Price"
        def calc(ot, xi):
            args = (xi, K, T, r, sigma)
            return greek_fn(*args, option_type=ot, q=q) if needs_type else greek_fn(*args, q=q)
    elif vs == "vol":
        x = np.linspace(0.05, 0.80, 200)
        x_label = "Volatility (σ)"
        def calc(ot, xi):
            args = (S, K, T, r, xi)
            return greek_fn(*args, option_type=ot, q=q) if needs_type else greek_fn(*args, q=q)
    elif vs == "time":
        x = np.linspace(0.01, T, 200)
        x_label = "Time to Expiry (years)"
        def calc(ot, xi):
            args = (S, K, xi, r, sigma)
            return greek_fn(*args, option_type=ot, q=q) if needs_type else greek_fn(*args, q=q)
    else:
        raise ValueError(f"Unknown sweep variable: {vs}")

    fig = go.Figure()
    if needs_type:
        y_call = np.array([calc("call", xi) for xi in x])
        y_put = np.array([calc("put", xi) for xi in x])
        fig.add_trace(go.Scatter(x=x, y=y_call, mode="lines",
                                 name=f"{greek_name} (call)", line=dict(color="#2196F3", width=2)))
        fig.add_trace(go.Scatter(x=x, y=y_put, mode="lines",
                                 name=f"{greek_name} (put)", line=dict(color="#FF5252", dash="dash", width=2)))
    else:
        y = np.array([calc("call", xi) for xi in x])
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines",
                                 name=greek_name, line=dict(color="#2196F3", width=2)))

    fig.update_layout(xaxis_title=x_label, yaxis_title=greek_name.capitalize(),
                      title=f"{greek_name.capitalize()} vs {x_label}", **_LAYOUT_DEFAULTS)
    _show(fig, save_path, show)


# ---------------------------------------------------------------------------
# 3. Volatility surface / smile
# ---------------------------------------------------------------------------

def plot_vol_smile(
    strikes: np.ndarray,
    ivs: np.ndarray,
    expiry_label: str = "",
    save_path: str | None = None,
    show: bool = True,
) -> None:
    go = _go()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=strikes, y=ivs * 100, mode="lines+markers",
                             marker=dict(size=4), line=dict(color="#2196F3", width=1.5)))
    fig.update_layout(xaxis_title="Strike", yaxis_title="Implied Volatility (%)",
                      title=f"Volatility Smile {expiry_label}", **_LAYOUT_DEFAULTS)
    _show(fig, save_path, show)


def plot_vol_surface(
    strikes: np.ndarray,
    maturities: np.ndarray,
    iv_matrix: np.ndarray,
    save_path: str | None = None,
    show: bool = True,
) -> None:
    go = _go()
    fig = go.Figure(data=go.Heatmap(
        z=iv_matrix * 100,
        x=strikes,
        y=maturities,
        colorscale="RdYlBu_r",
        colorbar=dict(title="IV (%)"),
    ))
    fig.update_layout(xaxis_title="Strike", yaxis_title="Maturity (years)",
                      title="Volatility Surface", **_LAYOUT_DEFAULTS)
    _show(fig, save_path, show)


# ---------------------------------------------------------------------------
# 4. Model comparison bar chart
# ---------------------------------------------------------------------------

def plot_model_comparison(
    labels: list[str],
    prices: list[float],
    market_mid: float | None = None,
    save_path: str | None = None,
    show: bool = True,
) -> None:
    go = _go()
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0"]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=prices,
        marker_color=[colors[i % len(colors)] for i in range(len(labels))],
        text=[f"{p:.4f}" for p in prices], textposition="outside",
    ))
    if market_mid is not None:
        fig.add_hline(y=market_mid, line_color="red", line_dash="dash",
                      annotation_text=f"Market mid = {market_mid:.4f}")
    fig.update_layout(yaxis_title="Option Price", title="Model Comparison", **_LAYOUT_DEFAULTS)
    _show(fig, save_path, show)


# ---------------------------------------------------------------------------
# 5. GARCH vol forecast chart
# ---------------------------------------------------------------------------

def plot_garch_forecast(
    term_structure: np.ndarray,
    ewma_vol: float | None = None,
    save_path: str | None = None,
    show: bool = True,
) -> None:
    go = _go()
    days = np.arange(1, len(term_structure) + 1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=days, y=term_structure * 100, mode="lines",
                             name="GARCH term structure", line=dict(color="#2196F3", width=2)))
    if ewma_vol is not None:
        fig.add_hline(y=ewma_vol * 100, line_color="orange", line_dash="dash",
                      annotation_text=f"EWMA = {ewma_vol*100:.1f}%")
    fig.update_layout(xaxis_title="Forecast Horizon (days)", yaxis_title="Annualised Volatility (%)",
                      title="GARCH(1,1) Forward Vol Term Structure", **_LAYOUT_DEFAULTS)
    _show(fig, save_path, show)


# ---------------------------------------------------------------------------
# 6. VaR histogram
# ---------------------------------------------------------------------------

def plot_var_histogram(
    returns: np.ndarray,
    var_1day: float,
    es_1day: float,
    confidence: float = 0.99,
    save_path: str | None = None,
    show: bool = True,
) -> None:
    go = _go()
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=returns, nbinsx=80, histnorm="probability density",
                               marker_color="#2196F3", opacity=0.7, name="Returns"))
    fig.add_vline(x=-var_1day, line_color="red", line_width=2,
                  annotation_text=f"{confidence*100:.0f}% VaR = {var_1day:.4f}")
    fig.add_vline(x=-es_1day, line_color="darkred", line_width=2, line_dash="dash",
                  annotation_text=f"ES = {es_1day:.4f}")
    fig.update_layout(xaxis_title="Daily Return", yaxis_title="Density",
                      title=f"Return Distribution — {confidence*100:.0f}% VaR", **_LAYOUT_DEFAULTS)
    if save_path:
        fig.savefig(save_path, dpi=150)
    _show(fig, save_path, show)


# ---------------------------------------------------------------------------
# 7. ARIMA / SARIMA forecast chart
# ---------------------------------------------------------------------------

def plot_arima_forecast(
    historical: np.ndarray,
    forecast: np.ndarray,
    conf_lower: np.ndarray,
    conf_upper: np.ndarray,
    ticker: str = "",
    target: str = "price",
    save_path: str | None = None,
    show: bool = True,
) -> None:
    go = _go()
    n_hist = len(historical)
    n_fcast = len(forecast)
    x_hist = list(range(n_hist))
    x_fcast = list(range(n_hist, n_hist + n_fcast))

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_hist, y=historical, mode="lines",
                             name="Historical", line=dict(color="#2196F3", width=1.5)))
    fig.add_trace(go.Scatter(x=x_fcast, y=forecast, mode="lines",
                             name="Forecast", line=dict(color="#FF9800", width=2)))
    fig.add_trace(go.Scatter(x=x_fcast, y=conf_upper, mode="lines",
                             line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=x_fcast, y=conf_lower, mode="lines",
                             line=dict(width=0), fill="tonexty", fillcolor="rgba(255,152,0,0.15)",
                             name="95% CI"))
    label = f"{ticker} " if ticker else ""
    fig.update_layout(xaxis_title="Trading Days", yaxis_title=target.capitalize(),
                      title=f"{label}ARIMA {target.capitalize()} Forecast", **_LAYOUT_DEFAULTS)
    _show(fig, save_path, show)


# ---------------------------------------------------------------------------
# 8. Binomial convergence chart
# ---------------------------------------------------------------------------

def plot_binomial_convergence(
    steps_list: list[int],
    tree_prices: list[float],
    bsm_price: float,
    save_path: str | None = None,
    show: bool = True,
) -> None:
    go = _go()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=steps_list, y=tree_prices, mode="lines+markers",
                             name="Binomial", marker=dict(size=4), line=dict(color="#2196F3", width=1.5)))
    fig.add_hline(y=bsm_price, line_color="red", line_dash="dash",
                  annotation_text=f"BSM = {bsm_price:.4f}")
    fig.update_layout(xaxis_title="Number of Steps", yaxis_title="Option Price",
                      title="Binomial Convergence to BSM", **_LAYOUT_DEFAULTS)
    _show(fig, save_path, show)
