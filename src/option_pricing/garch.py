"""
GARCH(1,1) and EWMA volatility estimation (Hull Ch. 22).

Covers:
  - EWMA volatility (λ = 0.94 RiskMetrics default)
  - GARCH(1,1) parameter estimation via MLE
  - Long-run variance V̄ = ω / (1 − α − β)
  - Forward volatility term structure (Hull 22.6)
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize


# ---------------------------------------------------------------------------
# EWMA (Hull 22.3)
# ---------------------------------------------------------------------------

def ewma_volatility(
    returns: np.ndarray,
    lam: float = 0.94,
) -> np.ndarray:
    """Compute EWMA variance series.

    σ²ₙ = λ σ²ₙ₋₁ + (1−λ) u²ₙ₋₁

    Returns array of σ (standard deviations), same length as *returns*.
    The first value is seeded with the sample variance of the first 20 obs
    (or all obs if fewer).
    """
    n = len(returns)
    var = np.empty(n)
    seed_window = min(20, n)
    var[0] = np.var(returns[:seed_window], ddof=1)

    for i in range(1, n):
        var[i] = lam * var[i - 1] + (1 - lam) * returns[i - 1] ** 2

    return np.sqrt(var)


def ewma_forecast(current_var: float, lam: float = 0.94, horizon: int = 1) -> float:
    """EWMA has a flat term structure — forecast is simply current variance."""
    return math.sqrt(current_var * horizon)


# ---------------------------------------------------------------------------
# GARCH(1,1) (Hull 22.4-22.5)
# ---------------------------------------------------------------------------

def garch_fit(
    returns: np.ndarray,
    omega_init: float = 1e-6,
    alpha_init: float = 0.05,
    beta_init: float = 0.90,
) -> dict:
    """Estimate GARCH(1,1) parameters via maximum likelihood.

    σ²ₙ = ω + α u²ₙ₋₁ + β σ²ₙ₋₁

    Returns dict with keys: omega, alpha, beta, long_run_var, persistence, log_likelihood.
    """
    n = len(returns)
    if n < 30:
        raise ValueError("Need at least 30 return observations for GARCH estimation")

    def neg_log_likelihood(params):
        omega, alpha, beta = params
        if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
            return 1e12

        var = np.empty(n)
        var[0] = omega / max(1 - alpha - beta, 1e-8)  # seed with long-run var

        for i in range(1, n):
            var[i] = omega + alpha * returns[i - 1] ** 2 + beta * var[i - 1]
            if var[i] <= 0:
                return 1e12

        # Gaussian log-likelihood (up to constant)
        ll = -0.5 * np.sum(np.log(var) + returns ** 2 / var)
        return -ll

    # Bounds: omega > 0, 0 ≤ α, β, α+β < 1
    bounds = [(1e-10, 1e-2), (1e-6, 0.5), (0.5, 0.9999)]
    result = minimize(
        neg_log_likelihood,
        x0=[omega_init, alpha_init, beta_init],
        method="L-BFGS-B",
        bounds=bounds,
    )

    omega, alpha, beta = result.x
    persistence = alpha + beta
    long_run_var = omega / max(1 - persistence, 1e-8)

    return {
        "omega": omega,
        "alpha": alpha,
        "beta": beta,
        "long_run_var": long_run_var,
        "long_run_vol": math.sqrt(long_run_var * 252),  # annualised
        "persistence": persistence,
        "log_likelihood": -result.fun,
    }


def garch_variance_series(
    returns: np.ndarray,
    omega: float,
    alpha: float,
    beta: float,
) -> np.ndarray:
    """Compute the GARCH(1,1) conditional variance series given fitted params."""
    n = len(returns)
    var = np.empty(n)
    var[0] = omega / max(1 - alpha - beta, 1e-8)

    for i in range(1, n):
        var[i] = omega + alpha * returns[i - 1] ** 2 + beta * var[i - 1]

    return var


def garch_forecast_term_structure(
    current_var: float,
    omega: float,
    alpha: float,
    beta: float,
    max_days: int = 252,
) -> np.ndarray:
    """GARCH forward volatility term structure (Hull 22.6).

    E[σ²ₙ₊ₜ] = V̄ + (α + β)^t (σ²ₙ − V̄)

    Returns annualised vol for each horizon 1..max_days.
    """
    persistence = alpha + beta
    long_run_var = omega / max(1 - persistence, 1e-8)

    horizons = np.arange(1, max_days + 1)
    # Average variance over [1, t] horizon
    if abs(persistence - 1.0) < 1e-8:
        avg_var = current_var * np.ones_like(horizons, dtype=float)
    else:
        cum_var = long_run_var * horizons + (current_var - long_run_var) * \
            (1 - persistence ** horizons) / (1 - persistence)
        avg_var = cum_var / horizons

    return np.sqrt(avg_var * 252)  # annualised vol


def returns_from_prices(prices: np.ndarray) -> np.ndarray:
    """Log returns from a price series."""
    prices = np.asarray(prices, dtype=float)
    return np.diff(np.log(prices))
