"""
Command handlers — all registered commands for the option pricing terminal.

Each handler receives (ticker, params, flags, session, cache) and prints
results to stdout.
"""

from __future__ import annotations

import math
import concurrent.futures
from typing import Any

import numpy as np

from .command_registry import CommandRegistry, ParsedCommand
from .session import Session
from ..data.cache import DataCache, resolve_defaults

registry = CommandRegistry()


# ===================================================================
# Helpers
# ===================================================================

def _f(v, d=4):
    return f"{v:.{d}f}" if isinstance(v, float) else str(v)


def _print_stale(stale: list[str]):
    if stale:
        print(f"  ⚠ Stale data: {', '.join(stale)}")


def _print_params(p: dict):
    skip = {"_stale", "_positional", "option_type", "exercise"}
    parts = [f"{k}={_f(v)}" for k, v in p.items() if k not in skip and not k.startswith("_")]
    print(f"  Params: {', '.join(parts)}")


# ===================================================================
# SET — set session ticker
# ===================================================================

@registry.register("SET", description="Set the session ticker context")
def cmd_set(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    session.set_ticker(ticker)
    print(f"  Session ticker set to {session.ticker}")


# ===================================================================
# BSM — Black-Scholes-Merton pricing
# ===================================================================

@registry.register(
    "BSM",
    aliases=["bsm", "bs"],
    params={"K": float, "T": float, "sigma": float, "r": float, "q": float},
    description="Black-Scholes-Merton option pricing",
)
def cmd_bsm(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.bsm import bsm_price, check_bounds, put_call_parity_check
    from ..option_pricing.greeks import all_greeks
    from ..option_pricing.option_pricing import print_pricing_report, price_option

    p = resolve_defaults(ticker, params, cache)
    _print_stale(p.get("_stale", []))
    _print_params(p)

    opt_type = p.get("option_type", "call")
    exercise = p.get("exercise", "european")

    result = price_option(
        S=p["S"], K=p["K"], T=p["T"], r=p["r"], sigma=p["sigma"],
        option_type=opt_type, exercise=exercise, q=p["q"],
    )
    print_pricing_report(result)

    # Greek sweep chart
    greek_flag = None
    for f in flags:
        if f in ("delta", "gamma", "theta", "vega", "rho"):
            greek_flag = f
            break

    if "graph" in flags or greek_flag:
        from ..utils.chart_engine import plot_greek
        gname = greek_flag or "delta"
        vs = p.get("vs", "spot") if isinstance(p.get("vs"), str) else "spot"
        print(f"  Plotting {gname} vs {vs}...")
        plot_greek(gname, p["S"], p["K"], p["T"], p["r"], p["sigma"], p["q"], vs=vs)


# ===================================================================
# BIN — Binomial tree pricing
# ===================================================================

@registry.register(
    "BIN",
    aliases=["bin", "binomial", "tree"],
    params={"K": float, "T": float, "steps": int},
    description="Binomial tree option pricing (European & American)",
)
def cmd_bin(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.binomial import binomial_tree, binomial_tree_with_control_variate

    p = resolve_defaults(ticker, params, cache)
    _print_stale(p.get("_stale", []))
    _print_params(p)

    steps = int(p.get("steps", 200))
    opt_type = p.get("option_type", "call")
    exercise = "american" if "american" in flags else "european"

    price = binomial_tree(p["S"], p["K"], p["T"], p["r"], p["sigma"], steps, opt_type, exercise, p["q"])
    print(f"  Binomial ({steps} steps, {exercise}) {opt_type}: {_f(price)}")

    if exercise == "american":
        cv = binomial_tree_with_control_variate(p["S"], p["K"], p["T"], p["r"], p["sigma"], steps, opt_type, p["q"])
        print(f"  With control variate: {_f(cv)}")

    if "graph" in flags:
        from ..option_pricing.binomial import binomial_convergence_test
        from ..utils.chart_engine import plot_binomial_convergence
        conv = binomial_convergence_test(p["S"], p["K"], p["T"], p["r"], p["sigma"], opt_type, p["q"])
        steps_list = [c[0] for c in conv]
        tree_prices = [c[1] for c in conv]
        bsm_ref = conv[0][2]
        plot_binomial_convergence(steps_list, tree_prices, bsm_ref)


# ===================================================================
# MC — Monte Carlo pricing
# ===================================================================

@registry.register(
    "MC",
    aliases=["mc", "montecarlo"],
    params={"K": float, "T": float, "N": int, "B": float},
    description="Monte Carlo option pricing (vanilla, Asian, barrier, lookback)",
)
def cmd_mc(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.monte_carlo import mc_european, mc_asian, mc_barrier, mc_lookback

    p = resolve_defaults(ticker, params, cache)
    _print_stale(p.get("_stale", []))
    N = int(p.get("N", 100_000))
    opt_type = p.get("option_type", "call")

    if "asian" in flags:
        res = mc_asian(p["S"], p["K"], p["T"], p["r"], p["sigma"], opt_type, p["q"], N)
        label = "Asian"
    elif "barrier" in flags:
        B = float(p.get("B", p["S"] * 0.85))
        bt = "down-and-out"
        for f in flags:
            if f in ("down-and-out", "down-and-in", "up-and-out", "up-and-in"):
                bt = f
                break
        res = mc_barrier(p["S"], p["K"], p["T"], p["r"], p["sigma"], B, bt, opt_type, p["q"], N)
        label = f"Barrier ({bt}, B={B})"
    elif "lookback" in flags:
        res = mc_lookback(p["S"], p["T"], p["r"], p["sigma"], opt_type, p["q"], N)
        label = "Lookback"
    else:
        res = mc_european(p["S"], p["K"], p["T"], p["r"], p["sigma"], opt_type, p["q"], N)
        label = "European"

    print(f"  MC {label} {opt_type}: {_f(res['price'])} ± {_f(res['std_error'])}")
    print(f"  95% CI: [{_f(res['ci_95'][0])}, {_f(res['ci_95'][1])}]  ({res['n_paths']} paths)")


# ===================================================================
# GARCH — volatility estimation
# ===================================================================

@registry.register(
    "GARCH",
    aliases=["garch", "vol"],
    params={},
    description="GARCH(1,1) and EWMA volatility estimation",
)
def cmd_garch(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.garch import (
        garch_fit, ewma_volatility, garch_variance_series,
        garch_forecast_term_structure, returns_from_prices,
    )

    try:
        returns, stale = cache.get_log_returns(ticker)
        if stale:
            print("  ⚠ Using stale return data")
    except Exception:
        print(f"  Cannot fetch history for {ticker}, using random data for demo")
        np.random.seed(42)
        returns = np.random.normal(0, 0.01, 500)

    # GARCH fit
    gp = garch_fit(returns)
    print(f"  GARCH(1,1) — ω={gp['omega']:.6f}  α={gp['alpha']:.4f}  β={gp['beta']:.4f}")
    print(f"  Persistence: {gp['persistence']:.4f}  Long-run vol: {gp['long_run_vol']:.2%}")

    # EWMA
    ewma_vols = ewma_volatility(returns)
    ewma_ann = float(ewma_vols[-1] * math.sqrt(252))
    print(f"  EWMA (λ=0.94) latest annualised vol: {ewma_ann:.2%}")

    if "forecast" in flags or "graph" in flags:
        var_series = garch_variance_series(returns, gp["omega"], gp["alpha"], gp["beta"])
        ts = garch_forecast_term_structure(var_series[-1], gp["omega"], gp["alpha"], gp["beta"])
        print(f"  30-day forward vol: {ts[29]:.2%}   90-day: {ts[89]:.2%}   252-day: {ts[-1]:.2%}")

        if "graph" in flags:
            from ..utils.chart_engine import plot_garch_forecast
            plot_garch_forecast(ts, ewma_vol=ewma_ann)


# ===================================================================
# VOL — volatility surface / smile
# ===================================================================

@registry.register(
    "VOL",
    aliases=["volsurface", "smile"],
    params={"expiry": str},
    description="Implied volatility surface / smile from live chain",
)
def cmd_vol(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    try:
        chain, stale = cache.get_options_chain(ticker, params.get("expiry"))
    except Exception as e:
        print(f"  Cannot fetch options chain for {ticker}: {e}")
        return

    if stale:
        print("  ⚠ Using stale options chain data")

    calls = chain["calls"]
    expiry = chain["expiry"]

    # Extract smile from calls
    mask = (calls["impliedVolatility"] > 0.01) & (calls["impliedVolatility"] < 5.0)
    filtered = calls[mask].sort_values("strike")

    if filtered.empty:
        print(f"  No valid IV data in chain for {expiry}")
        return

    strikes = filtered["strike"].values
    ivs = filtered["impliedVolatility"].values

    print(f"  Volatility smile for {ticker} — expiry {expiry}")
    print(f"  {'Strike':>10}  {'IV':>10}")
    step = max(1, len(strikes) // 15)
    for i in range(0, len(strikes), step):
        print(f"  {strikes[i]:>10.2f}  {ivs[i]:>10.2%}")

    if "smile" in flags or "graph" in flags:
        from ..utils.chart_engine import plot_vol_smile
        plot_vol_smile(strikes, ivs, expiry_label=f"({ticker} {expiry})")

    if "surface" in flags:
        # Build surface from multiple expiries
        try:
            expirations, _ = cache.get_options_expirations(ticker)
            # Use up to 6 nearest expiries
            expiries_to_use = expirations[:6]
            all_strikes = None
            rows = []
            mat_list = []
            from datetime import datetime
            today = datetime.now()

            for exp_str in expiries_to_use:
                ch, _ = cache.get_options_chain(ticker, exp_str)
                c = ch["calls"]
                m = (c["impliedVolatility"] > 0.01) & (c["impliedVolatility"] < 5.0)
                c = c[m].sort_values("strike")
                if c.empty:
                    continue
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
                T_years = max((exp_date - today).days / 365.0, 0.01)
                mat_list.append(T_years)
                rows.append(c[["strike", "impliedVolatility"]])
                if all_strikes is None:
                    all_strikes = set(c["strike"].values)
                else:
                    all_strikes &= set(c["strike"].values)

            if all_strikes and len(rows) >= 2:
                common = sorted(all_strikes)
                iv_matrix = np.zeros((len(rows), len(common)))
                for i, row in enumerate(rows):
                    row_indexed = row.set_index("strike")
                    for j, k in enumerate(common):
                        iv_matrix[i, j] = row_indexed.loc[k, "impliedVolatility"]

                from ..utils.chart_engine import plot_vol_surface
                plot_vol_surface(np.array(common), np.array(mat_list), iv_matrix)
            else:
                print("  Not enough common strikes across expiries for surface plot")
        except Exception as e:
            print(f"  Could not build vol surface: {e}")


# ===================================================================
# IV — implied volatility
# ===================================================================

@registry.register(
    "IV",
    aliases=["iv", "impliedvol"],
    params={"K": float, "T": float, "PRICE": float},
    description="Compute implied volatility from a market price",
)
def cmd_iv(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.bsm import implied_volatility

    p = resolve_defaults(ticker, params, cache)
    mkt = float(params.get("PRICE", params.get("price", 0)))
    if mkt <= 0:
        print("  PRICE= is required (market option price)")
        return

    opt_type = p.get("option_type", "call")
    try:
        iv = implied_volatility(mkt, p["S"], p["K"], p["T"], p["r"], opt_type, p["q"])
        print(f"  Implied volatility for {ticker} {opt_type}: {iv:.4f} ({iv*100:.2f}%)")
    except ValueError as e:
        print(f"  IV solve failed: {e}")


# ===================================================================
# STRAT — strategy payoff
# ===================================================================

@registry.register(
    "STRAT",
    aliases=["strat", "strategy"],
    params={"K": float, "K1": float, "K2": float, "K3": float},
    description="Strategy payoff diagrams (bull-spread, straddle, butterfly, etc.)",
)
def cmd_strat(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.strategies import (
        bull_call_spread, bear_put_spread, straddle, strangle,
        butterfly, collar, iron_condor, strategy_summary, Leg,
    )
    from ..option_pricing.bsm import bsm_price

    p = resolve_defaults(ticker, params, cache)
    _print_stale(p.get("_stale", []))

    S, K, T, r, sigma, q = p["S"], p["K"], p["T"], p["r"], p["sigma"], p["q"]

    # Determine strategy type from positional args
    positional = p.get("_positional", [])
    strat_name = positional[0].lower() if positional else "straddle"

    def _prem(strike, opt_type):
        return bsm_price(S, strike, T, r, sigma, opt_type, q)

    K1 = float(p.get("K1", K * 0.95))
    K2 = float(p.get("K2", K * 1.05))
    K3 = float(p.get("K3", K * 1.10))

    if strat_name in ("bull-spread", "bullspread", "bull"):
        legs = bull_call_spread(K1, K2, _prem(K1, "call"), _prem(K2, "call"))
        label = f"Bull Call Spread ({K1}/{K2})"
    elif strat_name in ("bear-spread", "bearspread", "bear"):
        legs = bear_put_spread(K1, K2, _prem(K1, "put"), _prem(K2, "put"))
        label = f"Bear Put Spread ({K1}/{K2})"
    elif strat_name in ("straddle",):
        legs = straddle(K, _prem(K, "call"), _prem(K, "put"))
        label = f"Straddle (K={K})"
    elif strat_name in ("strangle",):
        legs = strangle(K1, K2, _prem(K1, "put"), _prem(K2, "call"))
        label = f"Strangle ({K1}/{K2})"
    elif strat_name in ("butterfly",):
        legs = butterfly(K1, K, K3, _prem(K1, "call"), _prem(K, "call"), _prem(K3, "call"))
        label = f"Butterfly ({K1}/{K}/{K3})"
    elif strat_name in ("collar",):
        legs = collar(S, K1, K2, _prem(K1, "put"), _prem(K2, "call"))
        label = f"Collar (S={S}, {K1}/{K2})"
    else:
        print(f"  Unknown strategy: {strat_name}")
        print("  Available: bull-spread, bear-spread, straddle, strangle, butterfly, collar")
        return

    summary = strategy_summary(legs, S)
    print(f"  Strategy: {label}")
    print(f"  Net premium : {summary['net_premium']:.2f}")
    print(f"  Max profit  : {summary['max_profit']:.2f}")
    print(f"  Max loss    : {summary['max_loss']:.2f}")
    print(f"  Breakevens  : {[f'{b:.2f}' for b in summary['breakevens']]}")

    if "graph" in flags:
        from ..utils.chart_engine import plot_payoff
        plot_payoff(legs, S, T=T, r=r, sigma=sigma, q=q)


# ===================================================================
# COMPARE — model comparison
# ===================================================================

@registry.register(
    "COMPARE",
    aliases=["compare", "cmp"],
    params={"K": float, "T": float},
    description="Compare BSM vs Binomial vs MC vs market price",
)
def cmd_compare(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.bsm import bsm_price
    from ..option_pricing.binomial import binomial_tree
    from ..option_pricing.monte_carlo import mc_european

    p = resolve_defaults(ticker, params, cache)
    _print_stale(p.get("_stale", []))
    _print_params(p)

    S, K, T, r, sigma, q = p["S"], p["K"], p["T"], p["r"], p["sigma"], p["q"]
    opt_type = p.get("option_type", "call")

    # Run all three models in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as exe:
        f_bsm = exe.submit(bsm_price, S, K, T, r, sigma, opt_type, q)
        f_bin = exe.submit(binomial_tree, S, K, T, r, sigma, 200, opt_type, "european", q)
        f_mc = exe.submit(mc_european, S, K, T, r, sigma, opt_type, q, 100_000)

    bsm_p = f_bsm.result()
    bin_p = f_bin.result()
    mc_res = f_mc.result()
    mc_p = mc_res["price"]

    # Try to get market mid
    market_mid = None
    try:
        chain, _ = cache.get_options_chain(ticker)
        side = chain["calls"] if opt_type == "call" else chain["puts"]
        row = side.iloc[(side["strike"] - K).abs().argsort().iloc[0]]
        bid, ask = row.get("bid", 0), row.get("ask", 0)
        if bid > 0 and ask > 0:
            market_mid = (bid + ask) / 2.0
    except Exception:
        pass

    labels = ["BSM", "Binomial", "Monte Carlo"]
    prices = [bsm_p, bin_p, mc_p]

    if market_mid is not None:
        labels.append("Market Mid")
        prices.append(market_mid)

    # Table
    print(f"\n  {'Model':<15} {'Price':>10} {'Δ from BSM':>12}")
    print(f"  {'-'*37}")
    for lbl, pr in zip(labels, prices):
        diff = pr - bsm_p
        pct = diff / bsm_p * 100 if bsm_p else 0
        print(f"  {lbl:<15} {pr:>10.4f} {pct:>+11.2f}%")

    if "graph" in flags:
        from ..utils.chart_engine import plot_model_comparison
        plot_model_comparison(labels, prices, market_mid)


# ===================================================================
# VAR — Value at Risk
# ===================================================================

@registry.register(
    "VAR",
    aliases=["var"],
    params={"conf": float, "horizon": int},
    description="Value at Risk (historical simulation or Monte Carlo)",
)
def cmd_var(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.var import historical_var, mc_var

    p = resolve_defaults(ticker, params, cache)
    conf = float(p.get("conf", 0.99))
    horizon = int(p.get("horizon", 10))

    if "mc" in flags:
        # Monte Carlo VaR
        opt_type = p.get("option_type", "call")
        res = mc_var(p["S"], p["K"], p["T"], p["r"], p["sigma"], opt_type,
                     q=p["q"], confidence=conf, horizon_days=horizon)
        print(f"  MC VaR ({conf*100:.0f}%, {horizon}-day): {_f(res['var'])}")
        print(f"  Expected Shortfall: {_f(res['es'])}")
    else:
        # Historical simulation
        try:
            returns, stale = cache.get_log_returns(ticker)
            if stale:
                print("  ⚠ Using stale return data")
        except Exception:
            print(f"  Cannot fetch history for {ticker}")
            return

        res = historical_var(returns, conf, horizon)
        print(f"  Historical VaR ({conf*100:.0f}%, {horizon}-day): {_f(res['var_Nday'], 6)}")
        print(f"  1-day VaR: {_f(res['var_1day'], 6)}  ES: {_f(res['es_1day'], 6)}")
        print(f"  {horizon}-day ES: {_f(res['es_Nday'], 6)}")

        if "graph" in flags:
            from ..utils.chart_engine import plot_var_histogram
            plot_var_histogram(returns, res["var_1day"], res["es_1day"], conf)


# ===================================================================
# ARIMA — time-series forecasting
# ===================================================================

@registry.register(
    "ARIMA",
    aliases=["arima", "sarima", "forecast"],
    params={"steps": int, "m": int, "window": int},
    description="ARIMA / SARIMA price & volatility forecasting",
)
def cmd_arima(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    from ..option_pricing.arima import forecast_prices, forecast_volatility

    steps = int(params.get("steps", 30))
    m = int(params.get("m", 5))
    seasonal = "seasonal" in flags or "sarima" in flags
    mode_label = "SARIMA" if seasonal else "ARIMA"

    # Fetch history
    try:
        hist, stale = cache.get_history(ticker, period="2y")
        if stale:
            print("  ⚠ Using stale history")
        prices = hist["Close"].dropna().values
    except Exception as e:
        print(f"  Cannot fetch history for {ticker}: {e}")
        return

    if len(prices) < 60:
        print(f"  Insufficient price history ({len(prices)} points, need ≥ 60)")
        return

    # --- Price forecast ---
    if "vol" not in flags:
        print(f"  Fitting {mode_label} on log-prices ({len(prices)} obs, {steps}-step forecast)...")
        try:
            pf = forecast_prices(prices, steps=steps, seasonal=seasonal, m=m)
            print(f"  Order: {pf['order']}" + (f"  Seasonal: {pf['seasonal_order']}" if pf.get('seasonal_order') else ""))
            print(f"  AIC: {pf['aic']:.1f}")
            last = prices[-1]
            fc_end = pf["forecast_prices"][-1]
            pct = (fc_end / last - 1) * 100
            print(f"  Current price : {last:.2f}")
            print(f"  {steps}-day forecast: {fc_end:.2f} ({pct:+.2f}%)")
            print(f"  95% CI: [{pf['conf_lower'][-1]:.2f}, {pf['conf_upper'][-1]:.2f}]")

            if "graph" in flags:
                from ..utils.chart_engine import plot_arima_forecast
                plot_arima_forecast(
                    prices[-120:], pf["forecast_prices"],
                    pf["conf_lower"], pf["conf_upper"],
                    ticker=ticker, target="price",
                )
        except Exception as e:
            print(f"  Price forecast failed: {e}")

    # --- Volatility forecast ---
    if "vol" in flags or "sigma" in flags:
        from ..option_pricing.garch import returns_from_prices
        returns = returns_from_prices(prices)
        window = int(params.get("window", 21))
        print(f"  Fitting {mode_label} on {window}-day realised vol...")
        try:
            vf = forecast_volatility(returns, steps=steps, window=window, seasonal=seasonal, m=m)
            print(f"  Order: {vf['order']}" + (f"  Seasonal: {vf['seasonal_order']}" if vf.get('seasonal_order') else ""))
            print(f"  Current realised vol : {vf['historical_vol'][-1]:.2%}")
            print(f"  Mean forecast vol    : {vf['mean_forecast_vol']:.2%}")
            print(f"  {steps}-day forecast  : {vf['forecast_vol'][-1]:.2%}")

            if "graph" in flags:
                from ..utils.chart_engine import plot_arima_forecast
                plot_arima_forecast(
                    vf["historical_vol"][-120:], vf["forecast_vol"],
                    vf["conf_lower"], vf["conf_upper"],
                    ticker=ticker, target="volatility",
                )
        except Exception as e:
            print(f"  Vol forecast failed: {e}")


# ===================================================================
# CHAIN — print live options chain
# ===================================================================

@registry.register(
    "CHAIN",
    aliases=["chain"],
    params={"expiry": str},
    description="Display live options chain",
)
def cmd_chain(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    expiry = params.get("expiry")
    try:
        chain, stale = cache.get_options_chain(ticker, expiry)
    except Exception as e:
        print(f"  Cannot fetch chain for {ticker}: {e}")
        return

    if stale:
        print("  ⚠ Using stale chain data")

    exp = chain["expiry"]
    print(f"\n  Options chain for {ticker} — expiry {exp}")

    for label, side in [("CALLS", chain["calls"]), ("PUTS", chain["puts"])]:
        print(f"\n  {label}")
        cols = ["strike", "lastPrice", "bid", "ask", "impliedVolatility", "openInterest"]
        available = [c for c in cols if c in side.columns]
        print(f"  {'Strike':>8} {'Last':>8} {'Bid':>8} {'Ask':>8} {'IV':>8} {'OI':>8}")
        print(f"  {'-'*52}")
        display = side[available].head(20)
        for _, row in display.iterrows():
            parts = []
            for c in available:
                v = row.get(c, "")
                if c == "impliedVolatility" and isinstance(v, (int, float)):
                    parts.append(f"{v:>8.2%}")
                elif isinstance(v, float):
                    parts.append(f"{v:>8.2f}")
                else:
                    parts.append(f"{v:>8}")
            print(f"  {''.join(parts)}")


# ===================================================================
# HELP — list commands
# ===================================================================

@registry.register("HELP", aliases=["help", "?"], description="Show available commands")
def cmd_help(ticker: str, params: dict, flags: set, session: Session, cache: DataCache):
    W = 70
    print("\n" + "=" * W)
    print("  FINANCIAL TERMINAL — COMMAND REFERENCE")
    print("=" * W)

    print(f"\n  {'Command':<12} {'Aliases':<25} Description")
    print(f"  {'-'*W}")
    for spec in registry.all_commands():
        aliases = ", ".join(spec.aliases) if spec.aliases else ""
        print(f"  {spec.name:<12} {aliases:<25} {spec.description}")

    print(f"""
{"─" * W}
  OPTION PRICING  —  COMMAND TICKER [KEY=VALUE ...] [--flag ...]
{"─" * W}
  SET GOOG                              Set session ticker (skip ticker on next calls)

  BSM  GOOG K=150 T=0.25               Black-Scholes pricing
  BSM  GOOG K=150 T=0.25 --graph       + Greek charts
  BIN  GOOG K=150 T=0.25 --american    Binomial tree (American)
  BIN  GOOG K=150 T=0.25 steps=500     Custom steps
  MC   GOOG K=150 T=0.25 N=100000      Monte Carlo European
  MC   GOOG K=150 --asian              Asian option
  MC   GOOG K=150 --barrier B=130      Barrier option (up-and-out)
  MC   GOOG --lookback                 Lookback option

  GARCH GOOG --forecast --graph        GARCH vol forecast
  VOL   GOOG --smile                   Implied vol smile
  VOL   GOOG --surface                 Full vol surface heatmap
  IV    GOOG K=150 T=0.25 PRICE=8.5   Implied vol from market price

  STRAT GOOG straddle K=150 --graph    Strategy payoff diagram
  STRAT GOOG bull-spread K1=140 K2=160 Bull spread
  STRAT GOOG butterfly K1=140 K2=150 K3=160

  COMPARE GOOG K=150 T=0.25 --graph   BSM vs BIN vs MC comparison
  VAR   GOOG --hist --graph            Historical VaR
  VAR   GOOG --mc conf=0.99 horizon=10 Monte Carlo VaR
  ARIMA GOOG steps=30 --graph          Price forecast (ARIMA)
  CHAIN GOOG                           Live options chain
  CHAIN GOOG expiry=2026-06-19         Chain filtered by expiry

{"─" * W}
  STOCK ANALYSIS  —  DSL syntax
{"─" * W}
  analyze stock AAPL for 1Y            Historical prices + volatility
  analyze stock GOOGL for 6M           Periods: 1M  6M  1Y  5Y

  show prices for AAPL                 Latest close price
  show income_statement for AAPL       Income statement
  show balance_sheet for MSFT          Balance sheet
  show cash_flow for GOOGL             Cash flow statement

{"─" * W}
  STOCK VALUATION (DCF & MOAT)
{"─" * W}
  calculate dcf for AAPL growth 0.15 years 10
  calculate dcf for GOOGL growth 0.10 discount 0.09 years 10
  calculate dcf for META growth 0.12 years 10 terminal_growth 0.025
  calculate dcf for MSFT growth 0.08 discount auto years 10 terminal_growth 0.03
    Params: growth  discount (or auto)  years  terminal_growth  beta

  show moat for GOOGL                  AI-powered moat / competitive advantage

{"─" * W}
  NEWS & SENTIMENT
{"─" * W}
  news GOOGL                           Today's news + BULLISH/BEARISH/NEUTRAL
  news GOOGL last_week                 Last 7 days
  news AAPL last_month                 Last 30 days
  news META yesterday                  Yesterday only
  news TSLA 2026-04-20                 Specific date (YYYY-MM-DD)
  news MSFT last_week limit 20         Up to 20 articles
    Date ranges: today  yesterday  last_week  last_month  YYYY-MM-DD
{"=" * W}
""")

