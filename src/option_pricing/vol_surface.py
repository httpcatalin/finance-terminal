"""
Volatility surface construction and smile analysis (Hull Ch. 19).

Covers:
  - Implied vol extraction across strikes/maturities
  - Vol surface interpolation (cubic spline strike, linear maturity)
  - Sticky-strike vs sticky-delta conventions
  - Breeden-Litzenberger risk-neutral density extraction
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
from scipy.interpolate import CubicSpline, interp1d

from .bsm import bsm_price, implied_volatility

OptionType = Literal["call", "put"]


class VolSurface:
    """Volatility surface built from market option prices.

    Construct with arrays of strikes, maturities, and corresponding
    market implied vols.  Interpolates with cubic spline across strikes
    and linear across maturities.
    """

    def __init__(
        self,
        strikes: np.ndarray,
        maturities: np.ndarray,
        iv_matrix: np.ndarray,
    ):
        """
        Parameters
        ----------
        strikes : 1-D array of strike prices, shape (K,)
        maturities : 1-D array of maturities in years, shape (M,)
        iv_matrix : 2-D array, shape (M, K) — each row is the IV smile
                    for a single maturity across all strikes.
        """
        self.strikes = np.asarray(strikes, dtype=float)
        self.maturities = np.asarray(maturities, dtype=float)
        self.iv_matrix = np.asarray(iv_matrix, dtype=float)

        if self.iv_matrix.shape != (len(self.maturities), len(self.strikes)):
            raise ValueError(
                f"iv_matrix shape {self.iv_matrix.shape} doesn't match "
                f"({len(self.maturities)}, {len(self.strikes)})"
            )

        # Build cubic spline interpolators per maturity row
        self._strike_splines: list[CubicSpline] = []
        for row in self.iv_matrix:
            self._strike_splines.append(CubicSpline(self.strikes, row))

    def get_vol(self, K: float, T: float) -> float:
        """Interpolate implied vol for a given strike and maturity."""
        if T <= 0:
            raise ValueError("Maturity must be positive")

        # Interpolate along strikes for each available maturity
        vols_at_K = np.array([spl(K) for spl in self._strike_splines])

        if len(self.maturities) == 1:
            return float(vols_at_K[0])

        # Linear interpolation across maturities (variance-weighted)
        total_var = vols_at_K ** 2 * self.maturities
        var_interp = interp1d(
            self.maturities, total_var,
            kind="linear",
            fill_value="extrapolate",
        )
        interp_total_var = float(var_interp(T))
        return math.sqrt(max(interp_total_var / T, 1e-12))

    def smile(self, T: float, K_range: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Return (strikes, vols) for a given maturity."""
        if K_range is None:
            K_range = self.strikes
        vols = np.array([self.get_vol(k, T) for k in K_range])
        return K_range, vols


def build_vol_surface_from_market(
    S: float,
    r: float,
    strikes: np.ndarray,
    maturities: np.ndarray,
    market_prices: np.ndarray,
    option_type: OptionType = "call",
    q: float = 0.0,
) -> VolSurface:
    """Build a VolSurface by extracting implied vols from market option prices.

    market_prices : shape (M, K) matching (maturities, strikes).
    """
    strikes = np.asarray(strikes, dtype=float)
    maturities = np.asarray(maturities, dtype=float)
    market_prices = np.asarray(market_prices, dtype=float)

    iv_matrix = np.empty_like(market_prices)
    for i, T in enumerate(maturities):
        for j, K in enumerate(strikes):
            try:
                iv_matrix[i, j] = implied_volatility(
                    market_prices[i, j], S, K, T, r, option_type, q,
                )
            except ValueError:
                iv_matrix[i, j] = np.nan

    # Fill NaNs with nearest neighbour along strike axis
    for i in range(iv_matrix.shape[0]):
        row = iv_matrix[i]
        mask = np.isnan(row)
        if mask.all():
            continue
        row[mask] = np.interp(
            strikes[mask], strikes[~mask], row[~mask],
        )

    return VolSurface(strikes, maturities, iv_matrix)


# ---------------------------------------------------------------------------
# Sticky-strike vs sticky-delta (Hull Ch. 19 appendix)
# ---------------------------------------------------------------------------

class StickyStrike:
    """Under sticky-strike, the vol for a given strike remains constant
    as the spot moves."""

    def __init__(self, surface: VolSurface):
        self.surface = surface

    def get_vol(self, K: float, T: float, _S: float | None = None) -> float:
        return self.surface.get_vol(K, T)


class StickyDelta:
    """Under sticky-delta, the vol for a given moneyness (K/S) remains
    constant as the spot moves."""

    def __init__(self, surface: VolSurface, S_ref: float):
        self.surface = surface
        self.S_ref = S_ref

    def get_vol(self, K: float, T: float, S_current: float | None = None) -> float:
        if S_current is None:
            S_current = self.S_ref
        # Map current K to the reference-spot strike with same moneyness
        K_ref = K * self.S_ref / S_current
        return self.surface.get_vol(K_ref, T)


# ---------------------------------------------------------------------------
# Breeden-Litzenberger risk-neutral density (Hull Ch. 19 appendix)
# ---------------------------------------------------------------------------

def risk_neutral_density(
    surface: VolSurface,
    S: float,
    T: float,
    r: float,
    q: float = 0.0,
    K_range: np.ndarray | None = None,
    dK: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract the risk-neutral probability density from the vol surface
    using the Breeden-Litzenberger result:

        g(K) = e^{rT} · ∂²C/∂K²

    Returns (strikes, density).
    """
    if K_range is None:
        K_range = np.linspace(
            surface.strikes.min() * 0.8,
            surface.strikes.max() * 1.2,
            200,
        )

    # Compute call prices across strikes
    prices = np.array([
        bsm_price(S, K, T, r, surface.get_vol(K, T), "call", q)
        for K in K_range
    ])

    # Numerical second derivative
    d2CdK2 = np.gradient(np.gradient(prices, K_range), K_range)
    density = math.exp(r * T) * d2CdK2

    # Clamp negative densities to zero (numerical artefact)
    density = np.maximum(density, 0.0)

    return K_range, density
