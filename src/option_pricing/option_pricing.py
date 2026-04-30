"""
Option Pricing Engine — unified entry point.

Orchestrates BSM, binomial tree, GARCH volatility, Greeks, vol surface,
Monte Carlo, VaR, and strategy payoff calculations.

Run standalone demo:
    python -m src.option_pricing.option_pricing
"""

from __future__ import annotations

import math
import textwrap

import numpy as np

from .bsm import (
    bsm_price,
    blacks_model,
    bsm_discrete_dividends,
    employee_stock_option_price,
    implied_volatility,
    check_bounds,
    put_call_parity_check,
)
from .binomial import (
    binomial_tree,
    binomial_tree_with_control_variate,
    binomial_convergence_test,
)
from .greeks import all_greeks, bsm_pde_check
from .garch import (
    ewma_volatility,
    garch_fit,
    garch_variance_series,
    garch_forecast_term_structure,
    returns_from_prices,
)
from .monte_carlo import mc_european, mc_asian, mc_barrier, mc_lookback
from .var import historical_var, delta_normal_var, delta_gamma_var, mc_var
from .strategies import (
    strategy_summary,
    bull_call_spread,
    bear_put_spread,
    straddle,
    strangle,
    butterfly,
    collar,
    iron_condor,
    Leg,
)


# ---------------------------------------------------------------------------
# Full pricing pipeline
# ---------------------------------------------------------------------------

def price_option(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "call",
    exercise: str = "european",
    q: float = 0.0,
    tree_steps: int = 200,
    mc_paths: int = 100_000,
) -> dict:
    """Run BSM + binomial + Monte Carlo and return a unified result dict."""
    result: dict = {"inputs": dict(S=S, K=K, T=T, r=r, sigma=sigma,
                                   option_type=option_type, exercise=exercise, q=q)}

    # 1) BSM (European only)
    bsm = bsm_price(S, K, T, r, sigma, option_type, q)
    result["bsm_price"] = bsm
    result["bounds_warnings"] = check_bounds(bsm, S, K, T, r, option_type, q)

    # 2) Binomial tree
    tree = binomial_tree(S, K, T, r, sigma, tree_steps, option_type, exercise, q)
    result["binomial_price"] = tree
    if exercise == "american":
        tree_cv = binomial_tree_with_control_variate(S, K, T, r, sigma, tree_steps, option_type, q)
        result["binomial_cv_price"] = tree_cv

    # 3) Monte Carlo (European)
    mc = mc_european(S, K, T, r, sigma, option_type, q, mc_paths)
    result["mc_price"] = mc["price"]
    result["mc_std_error"] = mc["std_error"]
    result["mc_ci_95"] = mc["ci_95"]

    # 4) Greeks
    result["greeks"] = all_greeks(S, K, T, r, sigma, option_type, q)

    # 5) PDE check
    pde_ok, pde_residual = bsm_pde_check(S, K, T, r, sigma, option_type, q)
    result["bsm_pde_check"] = {"satisfied": pde_ok, "residual": pde_residual}

    # 6) Put-call parity
    other = "put" if option_type == "call" else "call"
    other_price = bsm_price(S, K, T, r, sigma, other, q)
    parity_ok, parity_res = put_call_parity_check(
        bsm if option_type == "call" else other_price,
        other_price if option_type == "call" else bsm,
        S, K, T, r, q,
    )
    result["put_call_parity"] = {"satisfied": parity_ok, "residual": parity_res}

    return result


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def _fmt(val, decimals=4):
    if isinstance(val, float):
        return f"{val:.{decimals}f}"
    return str(val)


def print_pricing_report(result: dict) -> None:
    """Print a formatted pricing report to stdout."""
    inp = result["inputs"]
    S_str = f"{inp['S']:.2f}"
    K_str = f"{inp['K']:.2f}"
    T_str = f"{inp['T']:.4f}"
    r_str = f"{inp['r']:.4f}"
    sig_str = f"{inp['sigma']:.4f}"
    q_str = f"{inp['q']:.4f}"
    print(textwrap.dedent(f"""\
    ╔══════════════════════════════════════════════════════╗
    ║            OPTION PRICING REPORT                    ║
    ╠══════════════════════════════════════════════════════╣
    ║  Spot (S)       : {S_str:<12}  Strike (K)  : {K_str:<10}
    ║  Maturity (T)   : {T_str:<12}  Rate (r)    : {r_str:<10}
    ║  Volatility (σ) : {sig_str:<12}  Div yield   : {q_str:<10}
    ║  Type           : {inp['option_type']:<12}  Exercise    : {inp['exercise']:<10}
    ╠══════════════════════════════════════════════════════╣
    ║  BSM Price      : {_fmt(result['bsm_price']):<36}
    ║  Binomial Price : {_fmt(result['binomial_price']):<36}"""))

    if "binomial_cv_price" in result:
        print(f"    ║  Binomial (CV)  : {_fmt(result['binomial_cv_price']):<36}")

    print(f"    ║  MC Price       : {_fmt(result['mc_price'])} ± {_fmt(result['mc_std_error'])}")

    g = result["greeks"]
    print(textwrap.dedent(f"""\
    ╠══════════════════════════════════════════════════════╣
    ║  GREEKS                                             ║
    ║  Delta  : {_fmt(g['delta']):<12}  Gamma : {_fmt(g['gamma']):<14}
    ║  Theta  : {_fmt(g['theta']):<12}  Vega  : {_fmt(g['vega']):<14}
    ║  Rho    : {_fmt(g['rho']):<42}
    ╠══════════════════════════════════════════════════════╣
    ║  BSM PDE Check  : {'✓' if result['bsm_pde_check']['satisfied'] else '✗'}  (residual {_fmt(result['bsm_pde_check']['residual'], 8)})
    ║  Put-Call Parity : {'✓' if result['put_call_parity']['satisfied'] else '✗'}  (residual {_fmt(result['put_call_parity']['residual'], 8)})
    ╚══════════════════════════════════════════════════════╝"""))

    if result["bounds_warnings"]:
        for w in result["bounds_warnings"]:
            print(f"    ⚠  {w}")


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

def run_demo():
    """Run a comprehensive demo of every module."""
    print("=" * 60)
    print("  OPTION PRICING ENGINE — FULL DEMO")
    print("=" * 60)

    # --- 1. Core pricing ---
    print("\n[1] CORE PRICING — European Call on equity")
    result = price_option(S=100, K=105, T=0.5, r=0.05, sigma=0.20,
                          option_type="call", exercise="european")
    print_pricing_report(result)

    # --- 2. American put ---
    print("\n[2] AMERICAN PUT — Binomial tree with control variate")
    result_am = price_option(S=100, K=105, T=0.5, r=0.05, sigma=0.20,
                             option_type="put", exercise="american")
    print_pricing_report(result_am)

    # --- 3. Implied volatility ---
    print("\n[3] IMPLIED VOLATILITY")
    mkt_price = 8.50
    iv = implied_volatility(mkt_price, S=100, K=105, T=0.5, r=0.05, option_type="call")
    print(f"    Market price: {mkt_price}  →  IV: {iv:.4f} ({iv*100:.2f}%)")

    # --- 4. Futures option (Black's model) ---
    print("\n[4] FUTURES OPTION — Black's model")
    fut_price = blacks_model(F=50, K=50, T=0.25, r=0.05, sigma=0.30, option_type="call")
    print(f"    Black's call price (F=50, K=50): {fut_price:.4f}")

    # --- 5. Discrete dividends ---
    print("\n[5] DISCRETE DIVIDENDS")
    divs = [(0.1, 2.0), (0.35, 2.0)]  # two $2 dividends
    dd_price = bsm_discrete_dividends(100, 105, 0.5, 0.05, 0.20, "call", divs)
    print(f"    BSM with discrete divs: {dd_price:.4f}")

    # --- 6. Convergence test ---
    print("\n[6] BINOMIAL CONVERGENCE → BSM")
    conv = binomial_convergence_test(S=100, K=105, T=0.5, r=0.05, sigma=0.20)
    print(f"    {'Steps':>6}  {'Tree':>10}  {'BSM':>10}  {'Diff':>10}")
    for n, tree_p, bsm_p in conv:
        print(f"    {n:>6}  {tree_p:>10.4f}  {bsm_p:>10.4f}  {tree_p - bsm_p:>10.6f}")

    # --- 7. GARCH ---
    print("\n[7] GARCH VOLATILITY ESTIMATION")
    np.random.seed(42)
    fake_returns = np.random.normal(0, 0.01, 500)
    garch_params = garch_fit(fake_returns)
    print(f"    ω={garch_params['omega']:.6f}  α={garch_params['alpha']:.4f}  "
          f"β={garch_params['beta']:.4f}  persistence={garch_params['persistence']:.4f}")
    print(f"    Long-run annualised vol: {garch_params['long_run_vol']:.2%}")

    # --- 8. EWMA ---
    print("\n[8] EWMA VOLATILITY")
    ewma_vols = ewma_volatility(fake_returns)
    print(f"    Latest EWMA daily vol: {ewma_vols[-1]:.6f}  "
          f"(annualised: {ewma_vols[-1] * math.sqrt(252):.2%})")

    # --- 9. Monte Carlo exotics ---
    print("\n[9] MONTE CARLO — Asian option")
    asian = mc_asian(S=100, K=100, T=1, r=0.05, sigma=0.20, seed=42)
    print(f"    Asian call: {asian['price']:.4f} ± {asian['std_error']:.4f}")

    print("\n[10] MONTE CARLO — Barrier option (down-and-out call)")
    barr = mc_barrier(S=100, K=100, T=1, r=0.05, sigma=0.20,
                      barrier=85, barrier_type="down-and-out", seed=42)
    print(f"    Barrier call: {barr['price']:.4f} ± {barr['std_error']:.4f}")

    print("\n[11] MONTE CARLO — Lookback option")
    lb = mc_lookback(S=100, T=1, r=0.05, sigma=0.20, seed=42)
    print(f"    Lookback call: {lb['price']:.4f} ± {lb['std_error']:.4f}")

    # --- 10. VaR ---
    print("\n[12] VALUE AT RISK — Historical simulation")
    hvar = historical_var(fake_returns, confidence=0.99, horizon_days=10)
    print(f"    1-day 99% VaR: {hvar['var_1day']:.6f}  "
          f"10-day: {hvar['var_Nday']:.6f}")
    print(f"    1-day 99% ES:  {hvar['es_1day']:.6f}  "
          f"10-day: {hvar['es_Nday']:.6f}")

    print("\n[13] VALUE AT RISK — Monte Carlo full revaluation")
    mcvar = mc_var(S=100, K=105, T=0.5, r=0.05, sigma=0.20,
                   option_type="call", horizon_days=10, seed=42)
    print(f"    10-day 99% VaR: {mcvar['var']:.4f}  ES: {mcvar['es']:.4f}")

    # --- 11. Strategy payoff ---
    print("\n[14] STRATEGY — Bull call spread")
    legs = bull_call_spread(K_low=100, K_high=110,
                            premium_low=5.0, premium_high=2.0)
    summary = strategy_summary(legs, S_current=105)
    print(f"    Net premium : {summary['net_premium']:.2f}")
    print(f"    Max profit  : {summary['max_profit']:.2f}")
    print(f"    Max loss    : {summary['max_loss']:.2f}")
    print(f"    Breakevens  : {[f'{b:.2f}' for b in summary['breakevens']]}")

    print("\n" + "=" * 60)
    print("  DEMO COMPLETE — all modules operational")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
