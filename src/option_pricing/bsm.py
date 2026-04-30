"""
Black-Scholes-Merton option pricing model (Hull Ch. 13-14).

Covers:
  - European call/put pricing
  - Continuous dividend yield adjustment (index/currency options)
  - Discrete dividend adjustment for European options
  - Garman-Kohlhagen currency option extension
  - Black's model for futures options
  - Employee stock option (expected-life) pricing
  - Implied volatility via Newton-Raphson with Brent fallback
  - Put-call parity verification
  - Analytical bound checks
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from scipy.stats import norm

OptionType = Literal["call", "put"]

# ---------------------------------------------------------------------------
# Core BSM
# ---------------------------------------------------------------------------

def bsm_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType = "call",
    q: float = 0.0,
) -> float:
    """European option price under BSM with continuous dividend yield *q*.

    For plain equity options set q=0.
    For index options, q = continuous dividend yield.
    For currency options, q = foreign risk-free rate (Garman-Kohlhagen).
    """
    if T <= 0:
        # At expiry, intrinsic value
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
    if sigma <= 0:
        raise ValueError("Volatility must be positive")

    d1, d2 = _d1d2(S, K, T, r, sigma, q)

    if option_type == "call":
        price = S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)

    return price


def _d1d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0):
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    return d1, d2


# ---------------------------------------------------------------------------
# Discrete dividend adjustment (Hull 14.12)
# ---------------------------------------------------------------------------

def bsm_discrete_dividends(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    dividends: list[tuple[float, float]],
) -> float:
    """BSM price with discrete dividends.

    *dividends* is a list of (time, amount) pairs where time < T.
    The stock price is reduced by the PV of known dividends.
    """
    pv_divs = sum(d * math.exp(-r * t) for t, d in dividends if t < T)
    S_adj = S - pv_divs
    if S_adj <= 0:
        raise ValueError("PV of dividends exceeds stock price")
    return bsm_price(S_adj, K, T, r, sigma, option_type, q=0.0)


# ---------------------------------------------------------------------------
# Black's model for futures options (Hull Ch. 17)
# ---------------------------------------------------------------------------

def blacks_model(
    F: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType = "call",
) -> float:
    """Price a European futures option using Black's model.

    F = current futures price.
    """
    if T <= 0:
        return max(F - K, 0.0) if option_type == "call" else max(K - F, 0.0)

    # Black's model is BSM with S = F*exp(-rT), q = 0
    return bsm_price(F * math.exp(-r * T), K, T, r, sigma, option_type, q=0.0)


# ---------------------------------------------------------------------------
# Employee stock option pricing (Hull Ch. 15)
# ---------------------------------------------------------------------------

def employee_stock_option_price(
    S: float,
    K: float,
    T_stated: float,
    T_expected: float,
    r: float,
    sigma: float,
    q: float = 0.0,
    option_type: OptionType = "call",
) -> float:
    """Price using the FAS 123R expected-life approximation."""
    return bsm_price(S, K, T_expected, r, sigma, option_type, q)


# ---------------------------------------------------------------------------
# Implied volatility (Newton-Raphson + Brent fallback)
# ---------------------------------------------------------------------------

def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType = "call",
    q: float = 0.0,
    tol: float = 1e-8,
    max_iter: int = 100,
) -> float:
    """Compute implied volatility using Newton-Raphson with Brent fallback."""
    if T <= 0:
        raise ValueError("Cannot compute IV for expired option")

    # Quick intrinsic-value sanity check
    intrinsic = max(S * math.exp(-q * T) - K * math.exp(-r * T), 0.0) if option_type == "call" \
        else max(K * math.exp(-r * T) - S * math.exp(-q * T), 0.0)
    if market_price < intrinsic - 1e-10:
        raise ValueError("Market price below intrinsic value — no IV solution")

    # Seed: Brenner-Subrahmanyam approximation
    sigma = math.sqrt(2.0 * math.pi / T) * market_price / S

    # Newton-Raphson
    for _ in range(max_iter):
        price = bsm_price(S, K, T, r, sigma, option_type, q)
        vega = bsm_vega(S, K, T, r, sigma, q)
        if vega < 1e-12:
            break
        diff = price - market_price
        if abs(diff) < tol:
            return sigma
        sigma -= diff / vega
        if sigma <= 0:
            break

    # Brent fallback on [0.001, 5.0]
    from scipy.optimize import brentq

    def obj(sig):
        return bsm_price(S, K, T, r, sig, option_type, q) - market_price

    try:
        return brentq(obj, 1e-4, 5.0, xtol=tol)
    except ValueError:
        raise ValueError("Could not find implied volatility within [0.01%, 500%]")


def bsm_vega(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> float:
    """Vega: dC/dσ (same for call and put)."""
    d1, _ = _d1d2(S, K, T, r, sigma, q)
    return S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T)


# ---------------------------------------------------------------------------
# Validation helpers (Hull Ch. 10)
# ---------------------------------------------------------------------------

def check_bounds(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType,
    q: float = 0.0,
) -> list[str]:
    """Return a list of warning strings if analytical bounds are violated."""
    warnings: list[str] = []
    pv_K = K * math.exp(-r * T)
    fwd_S = S * math.exp(-q * T)

    if option_type == "call":
        lower = max(fwd_S - pv_K, 0.0)
        upper = fwd_S
    else:
        lower = max(pv_K - fwd_S, 0.0)
        upper = pv_K

    if price < lower - 1e-8:
        warnings.append(f"Price {price:.6f} is below lower bound {lower:.6f}")
    if price > upper + 1e-8:
        warnings.append(f"Price {price:.6f} exceeds upper bound {upper:.6f}")

    return warnings


def put_call_parity_check(
    call_price: float,
    put_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    tol: float = 0.01,
) -> tuple[bool, float]:
    """Verify put-call parity: C + K*e^{-rT} = P + S*e^{-qT}.

    Returns (satisfied, residual).
    """
    lhs = call_price + K * math.exp(-r * T)
    rhs = put_price + S * math.exp(-q * T)
    residual = lhs - rhs
    return abs(residual) <= tol, residual
