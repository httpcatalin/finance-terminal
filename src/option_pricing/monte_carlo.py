"""
Monte Carlo simulation engine for option pricing (Hull Ch. 20).

Covers:
  - European vanilla pricing via GBM simulation
  - Antithetic variates variance reduction
  - Moment matching
  - Path-dependent options: Asian, barrier, lookback
  - Configurable number of paths and time steps
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np

OptionType = Literal["call", "put"]
BarrierType = Literal["up-and-out", "up-and-in", "down-and-out", "down-and-in"]


# ---------------------------------------------------------------------------
# GBM path generation
# ---------------------------------------------------------------------------

def _generate_paths(
    S: float,
    T: float,
    r: float,
    sigma: float,
    q: float,
    n_paths: int,
    n_steps: int,
    antithetic: bool,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate GBM stock-price paths.  Shape (n_paths, n_steps+1)."""
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma ** 2) * dt
    diffusion = sigma * math.sqrt(dt)

    half = n_paths // 2 if antithetic else n_paths
    Z = rng.standard_normal((half, n_steps))

    if antithetic:
        Z = np.vstack([Z, -Z])  # antithetic pairs

    log_returns = drift + diffusion * Z
    log_paths = np.cumsum(log_returns, axis=1)
    log_paths = np.column_stack([np.zeros(log_paths.shape[0]), log_paths])
    paths = S * np.exp(log_paths)

    return paths


# ---------------------------------------------------------------------------
# European vanilla
# ---------------------------------------------------------------------------

def mc_european(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType = "call",
    q: float = 0.0,
    n_paths: int = 100_000,
    n_steps: int = 1,
    antithetic: bool = True,
    moment_matching: bool = True,
    seed: int | None = None,
) -> dict:
    """Monte Carlo price for European vanilla option.

    Returns dict with price, std_error, and 95% confidence interval.
    """
    rng = np.random.default_rng(seed)
    paths = _generate_paths(S, T, r, sigma, q, n_paths, n_steps, antithetic, rng)
    ST = paths[:, -1]

    if moment_matching:
        # Adjust terminal prices so sample mean matches theoretical forward
        fwd = S * math.exp((r - q) * T)
        ST = ST * (fwd / ST.mean())

    if option_type == "call":
        payoffs = np.maximum(ST - K, 0.0)
    else:
        payoffs = np.maximum(K - ST, 0.0)

    disc = math.exp(-r * T)
    price = disc * payoffs.mean()
    std_err = disc * payoffs.std(ddof=1) / math.sqrt(len(payoffs))

    return {
        "price": float(price),
        "std_error": float(std_err),
        "ci_95": (float(price - 1.96 * std_err), float(price + 1.96 * std_err)),
        "n_paths": len(payoffs),
    }


# ---------------------------------------------------------------------------
# Asian option (arithmetic average)
# ---------------------------------------------------------------------------

def mc_asian(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType = "call",
    q: float = 0.0,
    n_paths: int = 100_000,
    n_steps: int = 252,
    antithetic: bool = True,
    seed: int | None = None,
) -> dict:
    """Price an arithmetic-average Asian option via Monte Carlo."""
    rng = np.random.default_rng(seed)
    paths = _generate_paths(S, T, r, sigma, q, n_paths, n_steps, antithetic, rng)

    # Average price over the path (excluding t=0)
    avg_price = paths[:, 1:].mean(axis=1)

    if option_type == "call":
        payoffs = np.maximum(avg_price - K, 0.0)
    else:
        payoffs = np.maximum(K - avg_price, 0.0)

    disc = math.exp(-r * T)
    price = disc * payoffs.mean()
    std_err = disc * payoffs.std(ddof=1) / math.sqrt(len(payoffs))

    return {
        "price": float(price),
        "std_error": float(std_err),
        "ci_95": (float(price - 1.96 * std_err), float(price + 1.96 * std_err)),
        "n_paths": len(payoffs),
    }


# ---------------------------------------------------------------------------
# Barrier option
# ---------------------------------------------------------------------------

def mc_barrier(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    barrier: float,
    barrier_type: BarrierType = "down-and-out",
    option_type: OptionType = "call",
    q: float = 0.0,
    n_paths: int = 100_000,
    n_steps: int = 252,
    antithetic: bool = True,
    seed: int | None = None,
) -> dict:
    """Price a barrier option via Monte Carlo."""
    rng = np.random.default_rng(seed)
    paths = _generate_paths(S, T, r, sigma, q, n_paths, n_steps, antithetic, rng)

    ST = paths[:, -1]

    if option_type == "call":
        payoffs = np.maximum(ST - K, 0.0)
    else:
        payoffs = np.maximum(K - ST, 0.0)

    # Determine which paths hit the barrier
    if barrier_type.startswith("down"):
        hit = np.any(paths <= barrier, axis=1)
    else:  # up
        hit = np.any(paths >= barrier, axis=1)

    if barrier_type.endswith("out"):
        payoffs[hit] = 0.0
    else:  # in
        payoffs[~hit] = 0.0

    disc = math.exp(-r * T)
    price = disc * payoffs.mean()
    std_err = disc * payoffs.std(ddof=1) / math.sqrt(len(payoffs))

    return {
        "price": float(price),
        "std_error": float(std_err),
        "ci_95": (float(price - 1.96 * std_err), float(price + 1.96 * std_err)),
        "n_paths": len(payoffs),
    }


# ---------------------------------------------------------------------------
# Lookback option (floating strike)
# ---------------------------------------------------------------------------

def mc_lookback(
    S: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType = "call",
    q: float = 0.0,
    n_paths: int = 100_000,
    n_steps: int = 252,
    antithetic: bool = True,
    seed: int | None = None,
) -> dict:
    """Price a floating-strike lookback option via Monte Carlo.

    Call payoff: S_T − S_min
    Put  payoff: S_max − S_T
    """
    rng = np.random.default_rng(seed)
    paths = _generate_paths(S, T, r, sigma, q, n_paths, n_steps, antithetic, rng)

    ST = paths[:, -1]

    if option_type == "call":
        payoffs = ST - paths.min(axis=1)
    else:
        payoffs = paths.max(axis=1) - ST

    payoffs = np.maximum(payoffs, 0.0)

    disc = math.exp(-r * T)
    price = disc * payoffs.mean()
    std_err = disc * payoffs.std(ddof=1) / math.sqrt(len(payoffs))

    return {
        "price": float(price),
        "std_error": float(std_err),
        "ci_95": (float(price - 1.96 * std_err), float(price + 1.96 * std_err)),
        "n_paths": len(payoffs),
    }
