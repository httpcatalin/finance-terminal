"""
ARIMA and Seasonal ARIMA forecasting for option pricing inputs.

Provides:
  - Price forecasting (ARIMA / SARIMA on log-prices)
  - Volatility forecasting (ARIMA on realised-vol series)
  - Auto order selection via pmdarima
  - Integration helpers that feed forecasted σ into BSM / binomial

References:
  - Box-Jenkins methodology
  - Hamilton, "Time Series Analysis"
"""

from __future__ import annotations

import math
import warnings
from typing import Literal

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Auto order selection
# ---------------------------------------------------------------------------

def auto_arima_order(
    series: np.ndarray,
    seasonal: bool = False,
    m: int = 5,
    max_p: int = 5,
    max_q: int = 5,
    max_d: int = 2,
) -> dict:
    """Grid-search for best (p,d,q) / (P,D,Q,m) by AIC.

    Uses statsmodels directly — no pmdarima dependency.
    Returns dict with keys: order, seasonal_order (if seasonal), aic.
    """
    from statsmodels.tsa.stattools import adfuller

    # Auto-detect d via ADF test
    d = 0
    tmp = series.copy()
    for _ in range(max_d):
        try:
            pval = adfuller(tmp, maxlag=min(20, len(tmp) // 3))[1]
        except Exception:
            break
        if pval < 0.05:
            break
        tmp = np.diff(tmp)
        d += 1

    best_aic = np.inf
    best_order = (0, d, 0)
    best_seasonal = (0, 0, 0, m) if seasonal else None
    best_model = None

    # Reduced grid for speed
    p_range = range(min(max_p, 4) + 1)
    q_range = range(min(max_q, 4) + 1)

    if seasonal:
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        P_range = range(2)
        D_range = range(2)
        Q_range = range(2)

        for p in p_range:
            for q in q_range:
                for P in P_range:
                    for D in D_range:
                        for Q in Q_range:
                            if p + q + P + Q == 0:
                                continue
                            try:
                                with warnings.catch_warnings():
                                    warnings.simplefilter("ignore")
                                    mdl = SARIMAX(
                                        series, order=(p, d, q),
                                        seasonal_order=(P, D, Q, m),
                                        enforce_stationarity=False,
                                        enforce_invertibility=False,
                                    ).fit(disp=False, maxiter=50)
                                if mdl.aic < best_aic:
                                    best_aic = mdl.aic
                                    best_order = (p, d, q)
                                    best_seasonal = (P, D, Q, m)
                                    best_model = mdl
                            except Exception:
                                continue
    else:
        from statsmodels.tsa.arima.model import ARIMA as _ARIMA

        for p in p_range:
            for q in q_range:
                if p + q == 0:
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        mdl = _ARIMA(series, order=(p, d, q)).fit()
                    if mdl.aic < best_aic:
                        best_aic = mdl.aic
                        best_order = (p, d, q)
                        best_model = mdl
                except Exception:
                    continue

    result = {
        "order": best_order,
        "aic": best_aic,
        "model": best_model,
    }
    if seasonal:
        result["seasonal_order"] = best_seasonal
    return result


# ---------------------------------------------------------------------------
# ARIMA fit + forecast
# ---------------------------------------------------------------------------

def fit_arima(
    series: np.ndarray,
    order: tuple[int, int, int] | None = None,
) -> dict:
    """Fit a non-seasonal ARIMA(p,d,q) model.

    If *order* is None, auto-selects via pmdarima.
    Returns dict: order, aic, fitted_model.
    """
    if order is None:
        auto = auto_arima_order(series, seasonal=False)
        order = auto["order"]

    from statsmodels.tsa.arima.model import ARIMA

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ARIMA(series, order=order).fit()

    return {
        "order": order,
        "aic": model.aic,
        "bic": model.bic,
        "fitted_model": model,
    }


def fit_sarima(
    series: np.ndarray,
    order: tuple[int, int, int] | None = None,
    seasonal_order: tuple[int, int, int, int] | None = None,
    m: int = 5,
) -> dict:
    """Fit a Seasonal ARIMA(p,d,q)(P,D,Q,m) model.

    m=5 for weekly seasonality in trading days; m=21 for monthly.
    Auto-selects orders if not provided.
    """
    if order is None or seasonal_order is None:
        auto = auto_arima_order(series, seasonal=True, m=m)
        order = order or auto["order"]
        seasonal_order = seasonal_order or auto.get("seasonal_order", (0, 0, 0, m))

    from statsmodels.tsa.statespace.sarimax import SARIMAX

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(series, order=order, seasonal_order=seasonal_order,
                        enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)

    return {
        "order": order,
        "seasonal_order": seasonal_order,
        "aic": model.aic,
        "bic": model.bic,
        "fitted_model": model,
    }


# ---------------------------------------------------------------------------
# Forecasting
# ---------------------------------------------------------------------------

def forecast(
    fitted: dict,
    steps: int = 30,
    alpha: float = 0.05,
) -> dict:
    """Produce point forecast + confidence interval from a fitted model.

    Returns: forecast (array), conf_lower, conf_upper, steps.
    """
    model = fitted["fitted_model"]
    fc = model.get_forecast(steps=steps)
    mean = fc.predicted_mean.values if hasattr(fc.predicted_mean, "values") else np.asarray(fc.predicted_mean)
    ci = fc.conf_int(alpha=alpha)
    if hasattr(ci, "values"):
        ci = ci.values
    lower = ci[:, 0]
    upper = ci[:, 1]

    return {
        "forecast": mean,
        "conf_lower": lower,
        "conf_upper": upper,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Price forecasting (log-price space)
# ---------------------------------------------------------------------------

def forecast_prices(
    prices: np.ndarray,
    steps: int = 30,
    seasonal: bool = False,
    m: int = 5,
    order: tuple | None = None,
    seasonal_order: tuple | None = None,
) -> dict:
    """Forecast future prices using ARIMA on log-prices.

    Working in log space ensures forecasts stay positive and yields
    normally-distributed residuals (closer to assumption).

    Returns: forecast_prices, conf_lower, conf_upper, model_info.
    """
    prices = np.asarray(prices, dtype=float)
    log_prices = np.log(prices)

    if seasonal:
        fitted = fit_sarima(log_prices, order=order, seasonal_order=seasonal_order, m=m)
    else:
        fitted = fit_arima(log_prices, order=order)

    fc = forecast(fitted, steps=steps)

    return {
        "prices": prices,
        "forecast_prices": np.exp(fc["forecast"]),
        "conf_lower": np.exp(fc["conf_lower"]),
        "conf_upper": np.exp(fc["conf_upper"]),
        "steps": steps,
        "order": fitted["order"],
        "seasonal_order": fitted.get("seasonal_order"),
        "aic": fitted["aic"],
    }


# ---------------------------------------------------------------------------
# Volatility forecasting
# ---------------------------------------------------------------------------

def forecast_volatility(
    returns: np.ndarray,
    steps: int = 30,
    window: int = 21,
    seasonal: bool = False,
    m: int = 5,
) -> dict:
    """Forecast realised volatility series using ARIMA.

    Computes rolling realised vol, then fits ARIMA and extrapolates.
    Returns annualised vol forecast.
    """
    returns = np.asarray(returns, dtype=float)
    if len(returns) < window + 30:
        raise ValueError(f"Need at least {window + 30} returns, got {len(returns)}")

    # Rolling realised vol (annualised)
    rv = pd.Series(returns).rolling(window).std().dropna().values * math.sqrt(252)

    if seasonal:
        fitted = fit_sarima(rv, m=m)
    else:
        fitted = fit_arima(rv)

    fc = forecast(fitted, steps=steps)

    # Clamp to non-negative
    fv = np.clip(fc["forecast"], 0, None)
    fl = np.clip(fc["conf_lower"], 0, None)
    fu = np.clip(fc["conf_upper"], 0, None)

    return {
        "historical_vol": rv,
        "forecast_vol": fv,
        "conf_lower": fl,
        "conf_upper": fu,
        "steps": steps,
        "order": fitted["order"],
        "seasonal_order": fitted.get("seasonal_order"),
        "aic": fitted["aic"],
        "mean_forecast_vol": float(np.mean(fv)),
    }


# ---------------------------------------------------------------------------
# Integration: forecast σ for option pricing
# ---------------------------------------------------------------------------

def arima_sigma_for_pricing(
    returns: np.ndarray,
    T_years: float = 30 / 252,
    seasonal: bool = False,
) -> float:
    """Return an annualised σ estimate using ARIMA vol forecast,
    averaged over the option's life.

    Can be plugged directly into BSM / binomial as the sigma parameter.
    """
    horizon_days = max(int(T_years * 252), 5)
    res = forecast_volatility(returns, steps=horizon_days, seasonal=seasonal)
    return float(res["mean_forecast_vol"])
