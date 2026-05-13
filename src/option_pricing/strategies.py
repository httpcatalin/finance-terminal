"""
Option trading strategies (Hull Ch. 11).

Compound position calculator — combines individual option legs into
strategy payoffs.  Computes net premium, breakeven, max profit/loss,
and payoff at a range of terminal prices.

Supported strategies:
  Bull/bear spread, straddle, strangle, butterfly, collar, iron condor,
  and arbitrary custom legs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

OptionType = Literal["call", "put"]
PositionSide = Literal["long", "short"]


@dataclass
class Leg:
    """A single option or stock position in a strategy."""
    option_type: OptionType | Literal["stock"]
    strike: float  # ignored for stock legs
    premium: float  # per-unit premium paid (positive) or received (negative)
    side: PositionSide
    quantity: int = 1


def payoff_at_expiry(legs: list[Leg], S_range: np.ndarray) -> np.ndarray:
    """Compute net payoff (including premium) across a range of terminal prices."""
    total = np.zeros_like(S_range, dtype=float)

    for leg in legs:
        sign = 1.0 if leg.side == "long" else -1.0
        q = leg.quantity

        if leg.option_type == "call":
            intrinsic = np.maximum(S_range - leg.strike, 0.0)
        elif leg.option_type == "put":
            intrinsic = np.maximum(leg.strike - S_range, 0.0)
        else:  # stock
            intrinsic = S_range - leg.strike  # strike stores entry price

        # Payoff = (intrinsic − premium) for long, −(intrinsic − premium) for short
        total += sign * q * (intrinsic - leg.premium)

    return total


def strategy_summary(legs: list[Leg], S_current: float,
                     S_min: float | None = None,
                     S_max: float | None = None,
                     n_points: int = 500) -> dict:
    """Compute strategy metrics.

    Returns dict with keys: net_premium, max_profit, max_loss, breakevens,
    payoff_curve (S_range, payoff arrays).
    """
    if S_min is None:
        strikes = [l.strike for l in legs if l.option_type != "stock"]
        S_min = min(strikes + [S_current]) * 0.7
    if S_max is None:
        strikes = [l.strike for l in legs if l.option_type != "stock"]
        S_max = max(strikes + [S_current]) * 1.3

    S_range = np.linspace(S_min, S_max, n_points)
    payoff = payoff_at_expiry(legs, S_range)

    net_premium = sum(
        (-1.0 if l.side == "long" else 1.0) * l.quantity * l.premium
        for l in legs
    )

    # Find breakevens (zero-crossings)
    sign_changes = np.where(np.diff(np.sign(payoff)))[0]
    breakevens = []
    for idx in sign_changes:
        # Linear interpolation
        x0, x1 = S_range[idx], S_range[idx + 1]
        y0, y1 = payoff[idx], payoff[idx + 1]
        if y1 != y0:
            breakevens.append(float(x0 - y0 * (x1 - x0) / (y1 - y0)))

    return {
        "net_premium": float(net_premium),
        "max_profit": float(payoff.max()),
        "max_loss": float(payoff.min()),
        "breakevens": breakevens,
        "S_range": S_range,
        "payoff": payoff,
    }


# ---------------------------------------------------------------------------
# Pre-built strategy constructors
# ---------------------------------------------------------------------------

def bull_call_spread(K_low: float, K_high: float,
                     premium_low: float, premium_high: float,
                     quantity: int = 1) -> list[Leg]:
    return [
        Leg("call", K_low, premium_low, "long", quantity),
        Leg("call", K_high, premium_high, "short", quantity),
    ]


def bear_put_spread(K_low: float, K_high: float,
                    premium_low: float, premium_high: float,
                    quantity: int = 1) -> list[Leg]:
    return [
        Leg("put", K_high, premium_high, "long", quantity),
        Leg("put", K_low, premium_low, "short", quantity),
    ]


def straddle(K: float, call_premium: float, put_premium: float,
             side: PositionSide = "long", quantity: int = 1) -> list[Leg]:
    return [
        Leg("call", K, call_premium, side, quantity),
        Leg("put", K, put_premium, side, quantity),
    ]


def strangle(K_put: float, K_call: float,
             put_premium: float, call_premium: float,
             side: PositionSide = "long", quantity: int = 1) -> list[Leg]:
    return [
        Leg("call", K_call, call_premium, side, quantity),
        Leg("put", K_put, put_premium, side, quantity),
    ]


def butterfly(K_low: float, K_mid: float, K_high: float,
              premium_low: float, premium_mid: float, premium_high: float,
              quantity: int = 1) -> list[Leg]:
    """Long butterfly spread using calls."""
    return [
        Leg("call", K_low, premium_low, "long", quantity),
        Leg("call", K_mid, premium_mid, "short", 2 * quantity),
        Leg("call", K_high, premium_high, "long", quantity),
    ]


def collar(S_entry: float, K_put: float, K_call: float,
           put_premium: float, call_premium: float,
           quantity: int = 1) -> list[Leg]:
    """Protective collar: long stock + long put + short call."""
    return [
        Leg("stock", S_entry, 0.0, "long", quantity),
        Leg("put", K_put, put_premium, "long", quantity),
        Leg("call", K_call, call_premium, "short", quantity),
    ]


def iron_condor(K_put_low: float, K_put_high: float,
                K_call_low: float, K_call_high: float,
                premium_put_low: float, premium_put_high: float,
                premium_call_low: float, premium_call_high: float,
                quantity: int = 1) -> list[Leg]:
    """Iron condor: bear call spread + bull put spread."""
    return [
        Leg("put", K_put_low, premium_put_low, "short", quantity),
        Leg("put", K_put_high, premium_put_high, "long", quantity),
        Leg("call", K_call_low, premium_call_low, "short", quantity),
        Leg("call", K_call_high, premium_call_high, "long", quantity),
    ]
