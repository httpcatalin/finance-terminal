"""
Binomial tree option pricing (Hull Ch. 12, 20).

Covers:
  - CRR (Cox-Ross-Rubinstein) recombining tree
  - European and American exercise
  - Control variate technique (European BSM as control)
  - Continuous dividend yield support
  - Convergence verification (tree → BSM as N → ∞)
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np

OptionType = Literal["call", "put"]
ExerciseStyle = Literal["european", "american"]


def binomial_tree(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    N: int = 200,
    option_type: OptionType = "call",
    exercise: ExerciseStyle = "european",
    q: float = 0.0,
) -> float:
    """Price an option using the CRR binomial tree.

    Parameters
    ----------
    N : int
        Number of time steps (200+ recommended for accuracy).
    """
    if T <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)

    dt = T / N
    u = math.exp(sigma * math.sqrt(dt))
    d = 1.0 / u
    disc = math.exp(-r * dt)
    p = (math.exp((r - q) * dt) - d) / (u - d)

    # Use numpy vectorised terminal payoff for speed
    j = np.arange(N + 1)
    ST = S * u ** (2 * j - N)  # stock prices at final nodes

    if option_type == "call":
        values = np.maximum(ST - K, 0.0)
    else:
        values = np.maximum(K - ST, 0.0)

    # Backward induction
    for i in range(N - 1, -1, -1):
        values = disc * (p * values[1:] + (1 - p) * values[:-1])
        if exercise == "american":
            S_nodes = S * u ** (2 * np.arange(i + 1) - i)
            if option_type == "call":
                intrinsic = np.maximum(S_nodes - K, 0.0)
            else:
                intrinsic = np.maximum(K - S_nodes, 0.0)
            values = np.maximum(values, intrinsic)

    return float(values[0])


def binomial_tree_with_control_variate(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    N: int = 200,
    option_type: OptionType = "call",
    q: float = 0.0,
) -> float:
    """American option price using the control variate technique (Hull Ch. 20).

    Uses the European BSM price as a control to reduce tree bias:
        price_american_cv = tree_american + (bsm_european - tree_european)
    """
    from .bsm import bsm_price

    tree_american = binomial_tree(S, K, T, r, sigma, N, option_type, "american", q)
    tree_european = binomial_tree(S, K, T, r, sigma, N, option_type, "european", q)
    bsm_european = bsm_price(S, K, T, r, sigma, option_type, q)

    return tree_american + (bsm_european - tree_european)


def binomial_convergence_test(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType = "call",
    q: float = 0.0,
    steps_list: list[int] | None = None,
) -> list[tuple[int, float, float]]:
    """Show how the binomial tree converges to BSM as N → ∞.

    Returns list of (N, tree_price, bsm_price).
    """
    from .bsm import bsm_price

    if steps_list is None:
        steps_list = [10, 25, 50, 100, 200, 500, 1000]

    bsm = bsm_price(S, K, T, r, sigma, option_type, q)
    results = []
    for n in steps_list:
        tree = binomial_tree(S, K, T, r, sigma, n, option_type, "european", q)
        results.append((n, tree, bsm))
    return results
