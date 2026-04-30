"""
Option Greeks — analytical closed-form BSM expressions (Hull Ch. 18).

Delta, Gamma, Theta, Vega, Rho for European options with continuous
dividend yield.  Includes the BSM PDE consistency check:
    Θ + r·S·Δ + ½σ²S²Γ = r·C
"""

from __future__ import annotations

import math
from typing import Literal

from scipy.stats import norm

from .bsm import _d1d2, bsm_price

OptionType = Literal["call", "put"]


def delta(S: float, K: float, T: float, r: float, sigma: float,
          option_type: OptionType = "call", q: float = 0.0) -> float:
    """∂C/∂S  or  ∂P/∂S."""
    if T <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0

    d1, _ = _d1d2(S, K, T, r, sigma, q)
    if option_type == "call":
        return math.exp(-q * T) * norm.cdf(d1)
    return math.exp(-q * T) * (norm.cdf(d1) - 1)


def gamma(S: float, K: float, T: float, r: float, sigma: float,
          q: float = 0.0) -> float:
    """∂²C/∂S² (same for call and put)."""
    if T <= 0:
        return 0.0
    d1, _ = _d1d2(S, K, T, r, sigma, q)
    return math.exp(-q * T) * norm.pdf(d1) / (S * sigma * math.sqrt(T))


def vega(S: float, K: float, T: float, r: float, sigma: float,
         q: float = 0.0) -> float:
    """∂C/∂σ (same for call and put).  Returned per 1 unit σ change."""
    if T <= 0:
        return 0.0
    d1, _ = _d1d2(S, K, T, r, sigma, q)
    return S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T)


def theta(S: float, K: float, T: float, r: float, sigma: float,
          option_type: OptionType = "call", q: float = 0.0) -> float:
    """∂C/∂t (per calendar day, i.e. divide annual theta by 365)."""
    if T <= 0:
        return 0.0
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    sqrt_T = math.sqrt(T)
    common = -(S * sigma * math.exp(-q * T) * norm.pdf(d1)) / (2 * sqrt_T)

    if option_type == "call":
        th = common + q * S * math.exp(-q * T) * norm.cdf(d1) \
             - r * K * math.exp(-r * T) * norm.cdf(d2)
    else:
        th = common - q * S * math.exp(-q * T) * norm.cdf(-d1) \
             + r * K * math.exp(-r * T) * norm.cdf(-d2)

    return th / 365.0  # per calendar day


def rho(S: float, K: float, T: float, r: float, sigma: float,
        option_type: OptionType = "call", q: float = 0.0) -> float:
    """∂C/∂r.  Returned per 1 unit r change."""
    if T <= 0:
        return 0.0
    _, d2 = _d1d2(S, K, T, r, sigma, q)
    if option_type == "call":
        return K * T * math.exp(-r * T) * norm.cdf(d2)
    return -K * T * math.exp(-r * T) * norm.cdf(-d2)


def all_greeks(S: float, K: float, T: float, r: float, sigma: float,
               option_type: OptionType = "call", q: float = 0.0) -> dict:
    """Compute all five Greeks in one call."""
    return {
        "delta": delta(S, K, T, r, sigma, option_type, q),
        "gamma": gamma(S, K, T, r, sigma, q),
        "theta": theta(S, K, T, r, sigma, option_type, q),
        "vega": vega(S, K, T, r, sigma, q),
        "rho": rho(S, K, T, r, sigma, option_type, q),
    }


def bsm_pde_check(
    S: float, K: float, T: float, r: float, sigma: float,
    option_type: OptionType = "call", q: float = 0.0,
    tol: float = 1e-6,
) -> tuple[bool, float]:
    """Verify Θ + r·S·Δ + ½σ²S²Γ = r·C (the BSM PDE identity).

    Theta here is annualised (multiply per-day theta by 365).
    Returns (satisfied, residual).
    """
    th = theta(S, K, T, r, sigma, option_type, q) * 365  # back to annual
    d = delta(S, K, T, r, sigma, option_type, q)
    g = gamma(S, K, T, r, sigma, q)
    price = bsm_price(S, K, T, r, sigma, option_type, q)

    lhs = th + r * S * d + 0.5 * sigma ** 2 * S ** 2 * g
    rhs = r * price
    residual = lhs - rhs
    return abs(residual) <= tol, residual
