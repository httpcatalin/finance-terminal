"""
Value at Risk (VaR) calculations (Hull Ch. 21).

Covers:
  - Historical simulation VaR (1-day, N-day, configurable confidence)
  - Delta-normal (linear) parametric VaR
  - Delta-gamma (quadratic) parametric VaR
  - Monte Carlo VaR for single option or portfolio
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm


# ---------------------------------------------------------------------------
# Historical simulation VaR
# ---------------------------------------------------------------------------

def historical_var(
    returns: np.ndarray,
    confidence: float = 0.99,
    horizon_days: int = 1,
) -> dict:
    """Historical simulation VaR.

    Parameters
    ----------
    returns : array of daily log returns
    confidence : e.g. 0.99 for 99%
    horizon_days : holding period (uses sqrt-time scaling)

    Returns dict with var_1day, var_Nday, es (expected shortfall).
    """
    returns = np.asarray(returns, dtype=float)
    alpha = 1 - confidence
    sorted_returns = np.sort(returns)

    idx = int(math.floor(alpha * len(sorted_returns)))
    idx = max(idx, 0)
    var_1day = -sorted_returns[idx]

    # Expected shortfall (conditional VaR)
    tail = sorted_returns[: idx + 1]
    es_1day = -tail.mean() if len(tail) > 0 else var_1day

    scale = math.sqrt(horizon_days)

    return {
        "var_1day": float(var_1day),
        "var_Nday": float(var_1day * scale),
        "es_1day": float(es_1day),
        "es_Nday": float(es_1day * scale),
        "confidence": confidence,
        "horizon_days": horizon_days,
    }


# ---------------------------------------------------------------------------
# Delta-normal (linear) VaR
# ---------------------------------------------------------------------------

def delta_normal_var(
    portfolio_value: float,
    delta: float,
    sigma_daily: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
) -> dict:
    """Parametric VaR using delta (linear) approximation.

    VaR = |Δ · S| · σ_daily · z_α · √h
    """
    z = norm.ppf(confidence)
    var_1day = abs(delta * portfolio_value) * sigma_daily * z
    scale = math.sqrt(horizon_days)

    return {
        "var_1day": float(var_1day),
        "var_Nday": float(var_1day * scale),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "method": "delta-normal",
    }


# ---------------------------------------------------------------------------
# Delta-gamma (quadratic) VaR
# ---------------------------------------------------------------------------

def delta_gamma_var(
    portfolio_value: float,
    delta: float,
    gamma: float,
    sigma_daily: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
    n_simulations: int = 100_000,
    seed: int | None = None,
) -> dict:
    """Parametric VaR with delta-gamma (quadratic) correction via simulation.

    ΔP ≈ Δ · ΔS + ½ Γ · (ΔS)²
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n_simulations)

    dS = portfolio_value * sigma_daily * z * math.sqrt(horizon_days)
    dP = delta * dS + 0.5 * gamma * dS ** 2

    alpha = 1 - confidence
    var_value = -np.percentile(dP, alpha * 100)

    tail = dP[dP <= -var_value]
    es_value = -tail.mean() if len(tail) > 0 else var_value

    return {
        "var_Nday": float(var_value),
        "es_Nday": float(es_value),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "method": "delta-gamma",
    }


# ---------------------------------------------------------------------------
# Monte Carlo VaR (full revaluation)
# ---------------------------------------------------------------------------

def mc_var(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str,
    position_size: int = 1,
    q: float = 0.0,
    confidence: float = 0.99,
    horizon_days: int = 10,
    n_simulations: int = 50_000,
    seed: int | None = None,
) -> dict:
    """Full-revaluation Monte Carlo VaR for a single option position.

    Simulates spot price moves over the holding period and re-prices
    the option at each scenario.
    """
    from .bsm import bsm_price

    rng = np.random.default_rng(seed)

    dt = horizon_days / 252.0
    drift = (r - q - 0.5 * sigma ** 2) * dt
    diffusion = sigma * math.sqrt(dt)

    Z = rng.standard_normal(n_simulations)
    S_future = S * np.exp(drift + diffusion * Z)
    T_future = max(T - dt, 1e-8)

    current_price = bsm_price(S, K, T, r, sigma, option_type, q)

    pnl = np.empty(n_simulations)
    for i in range(n_simulations):
        future_price = bsm_price(float(S_future[i]), K, T_future, r, sigma, option_type, q)
        pnl[i] = (future_price - current_price) * position_size

    alpha = 1 - confidence
    var_value = -np.percentile(pnl, alpha * 100)
    tail = pnl[pnl <= -var_value]
    es_value = -tail.mean() if len(tail) > 0 else var_value

    return {
        "var": float(var_value),
        "es": float(es_value),
        "confidence": confidence,
        "horizon_days": horizon_days,
        "current_option_price": float(current_price),
        "method": "monte-carlo-full-reval",
    }
