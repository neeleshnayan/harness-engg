"""Portfolio optimization via PyPortfolioOpt & skfolio-style Purged Cross Validation.

Calculates optimal weights for a set of scoped assets based on historical data.
Methods supported:
- hrp: Hierarchical Risk Parity (robust, no return estimates required, Lopez de Prado)
- max_sharpe: Tangency Mean-Variance Optimization
- min_volatility: Minimum Variance Optimization
- purged_cv: Purged & Embargoed K-Fold Cross Validation for out-of-sample backtest anti-overfitting
"""

import numpy as np
import pandas as pd
from pypfopt import expected_returns, risk_models, HRPOpt
from pypfopt.efficient_frontier import EfficientFrontier

from app.fund.marketdata import fetch_daily_bars, BarsError


def purged_cross_validation(df: pd.DataFrame, method: str = "hrp", n_splits: int = 5, purge_days: int = 5) -> dict:
    """
    Perform skfolio-style Purged & Embargoed K-Fold Cross Validation.
    Prevents backtest lookahead & serial correlation leakage.
    Returns OOS Sharpe, OOS Return, OOS Max Drawdown, and Probability of Backtest Overfitting (PBO).
    """
    if df.empty or len(df) < (n_splits * 10):
        return {
            "oos_sharpe": 0.0,
            "oos_annual_return": 0.0,
            "oos_max_drawdown": 0.0,
            "pbo": 0.0,
            "folds": [],
        }

    returns_df = df.pct_change().dropna()
    n_obs = len(returns_df)
    if n_obs < (n_splits * 5):
        return {
            "oos_sharpe": 0.0,
            "oos_annual_return": 0.0,
            "oos_max_drawdown": 0.0,
            "pbo": 0.0,
            "folds": [],
        }

    fold_size = n_obs // n_splits
    oos_returns = []
    fold_results = []
    is_sharpes = []
    oos_sharpes = []

    for k in range(n_splits):
        test_start = k * fold_size
        test_end = (k + 1) * fold_size if k < n_splits - 1 else n_obs

        # Mask test period and purge/embargo windows
        train_mask = np.ones(n_obs, dtype=bool)
        train_mask[max(0, test_start - purge_days): min(n_obs, test_end + purge_days)] = False

        train_returns = returns_df.iloc[train_mask]
        test_returns = returns_df.iloc[test_start:test_end]

        if len(train_returns) < 10 or len(test_returns) < 5:
            continue

        try:
            if method == "hrp":
                hrp = HRPOpt(train_returns)
                w_dict = hrp.optimize()
                cleaned_weights = {k: float(v) for k, v in w_dict.items()}
            elif method == "min_volatility":
                S = risk_models.sample_cov(train_returns, returns_data=True)
                ef = EfficientFrontier(None, S)
                ef.min_volatility()
                cleaned_weights = {k: float(v) for k, v in ef.clean_weights().items()}
            else:
                mu = expected_returns.mean_historical_return(train_returns, returns_data=True)
                S = risk_models.sample_cov(train_returns, returns_data=True)
                ef = EfficientFrontier(mu, S)
                ef.max_sharpe()
                cleaned_weights = {k: float(v) for k, v in ef.clean_weights().items()}

            weights_arr = np.array([cleaned_weights.get(c, 0.0) for c in returns_df.columns])

            # Calculate In-Sample (IS) metrics
            is_ret = train_returns.values @ weights_arr
            is_mean = np.mean(is_ret) * 252
            is_vol = np.std(is_ret) * np.sqrt(252) + 1e-8
            is_sharpe = float(is_mean / is_vol)
            is_sharpes.append(is_sharpe)

            # Calculate Out-Of-Sample (OOS) metrics
            oos_ret = test_returns.values @ weights_arr
            oos_returns.extend(oos_ret.tolist())

            oos_mean = np.mean(oos_ret) * 252
            oos_vol = np.std(oos_ret) * np.sqrt(252) + 1e-8
            oos_sharpe = float(oos_mean / oos_vol)
            oos_sharpes.append(oos_sharpe)

            fold_results.append({
                "fold": k + 1,
                "is_sharpe": round(is_sharpe, 2),
                "oos_sharpe": round(oos_sharpe, 2),
                "weights": {c: round(float(cleaned_weights.get(c, 0.0)), 4) for c in returns_df.columns},
            })
        except Exception:
            continue

    if not oos_returns:
        return {
            "oos_sharpe": 0.0,
            "oos_annual_return": 0.0,
            "oos_max_drawdown": 0.0,
            "pbo": 0.0,
            "folds": [],
        }

    all_oos = np.array(oos_returns)
    total_mean = np.mean(all_oos) * 252
    total_vol = np.std(all_oos) * np.sqrt(252) + 1e-8
    total_sharpe = float(total_mean / total_vol)

    cum = np.cumprod(1 + all_oos)
    peak = np.maximum.accumulate(cum)
    dd = (cum - peak) / peak
    max_dd = float(np.min(dd)) if len(dd) > 0 else 0.0

    # Probability of Backtest Overfitting (PBO): proportion of folds where OOS Sharpe degraded < 0.5 * IS Sharpe
    degraded = sum(1 for is_s, oos_s in zip(is_sharpes, oos_sharpes) if oos_s < (is_s * 0.5))
    pbo = float(degraded / len(is_sharpes)) if is_sharpes else 0.0

    return {
        "oos_sharpe": round(total_sharpe, 2),
        "oos_annual_return": round(float(total_mean), 4),
        "oos_max_drawdown": round(max_dd, 4),
        "pbo": round(pbo, 2),
        "folds": fold_results,
    }


def optimize_portfolio(symbols: list[str], lookback_days: int = 365, method: str = "hrp") -> dict:
    """
    Calculate optimal weights, efficient frontier, correlation, and skfolio-style cross validation.
    Methods supported:
    - 'hrp': Hierarchical Risk Parity (Default - robust, no return estimates needed)
    - 'max_sharpe': Tangency Mean-Variance Optimization
    - 'min_volatility': Minimum Variance Optimization
    """
    if not symbols:
        return {"weights": {}, "frontier_points": [], "correlation": {}, "cv_metrics": {}}

    prices = {}
    for sym in symbols:
        try:
            bars = fetch_daily_bars(sym, lookback_days=lookback_days)
            if not bars.dates or not bars.closes:
                continue
            series = pd.Series(bars.closes, index=pd.to_datetime(bars.dates))
            prices[sym] = series
        except BarsError:
            continue

    if not prices:
        return {
            "weights": {sym: 1.0 / len(symbols) for sym in symbols},
            "frontier_points": [],
            "correlation": {},
            "cv_metrics": {},
        }

    # Build dataframe, ffill and bfill to handle missing data
    df = pd.DataFrame(prices)
    df = df.dropna(how="all").ffill().bfill()

    try:
        corr = df.pct_change().corr().fillna(0).to_dict()

        if method == "hrp":
            returns_df = df.pct_change().dropna()
            hrp = HRPOpt(returns_df)
            raw_weights = hrp.optimize()
            cleaned_weights = {k: float(v) for k, v in raw_weights.items()}
        else:
            mu = expected_returns.mean_historical_return(df)
            S = risk_models.sample_cov(df)
            ef = EfficientFrontier(mu, S)
            if method == "min_volatility":
                ef.min_volatility()
            else:
                ef.max_sharpe()
            cleaned_weights = {k: float(v) for k, v in ef.clean_weights().items()}

        # Compute skfolio-style Purged Cross-Validation
        cv_metrics = purged_cross_validation(df, method=method, n_splits=5, purge_days=5)

        # Compute efficient frontier points
        frontier_points = []
        try:
            mu = expected_returns.mean_historical_return(df)
            S = risk_models.sample_cov(df)
            min_ret = float(mu.min())
            max_ret = float(mu.max())
            if min_ret < max_ret:
                target_returns = np.linspace(min_ret, max_ret, 20)
                for target in target_returns:
                    try:
                        ef_sweep = EfficientFrontier(mu, S)
                        ef_sweep.efficient_return(target)
                        w = ef_sweep.clean_weights()
                        ret, vol, sharpe = ef_sweep.portfolio_performance()
                        frontier_points.append({
                            "target_return": float(target),
                            "return": float(ret),
                            "volatility": float(vol),
                            "sharpe": float(sharpe),
                            "weights": {sym: float(w.get(sym, 0.0)) for sym in symbols},
                        })
                    except Exception:
                        pass
        except Exception:
            pass

        # Ensure all original symbols are in the output
        weights_result = {sym: round(float(cleaned_weights.get(sym, 0.0)), 4) for sym in symbols}

        return {
            "method": method,
            "weights": weights_result,
            "frontier_points": frontier_points,
            "correlation": corr,
            "cv_metrics": cv_metrics,
        }
    except Exception as e:
        # Fallback to equal weight on error
        return {
            "method": method,
            "weights": {sym: round(1.0 / len(symbols), 4) for sym in symbols},
            "frontier_points": [],
            "correlation": {},
            "cv_metrics": {},
        }


def optimize_return_streams(df: pd.DataFrame, method: str = "hrp") -> dict:
    """
    Optimize weights given a DataFrame of cumulative equity curves or price series for child strategies.
    Supported methods: equal, risk_parity, hrp, max_sharpe, min_volatility.
    """
    if df.empty or len(df.columns) == 0:
        return {
            "weights": {},
            "method": method,
            "expected": {"sharpe": 0.0, "vol": 0.0, "ret": 0.0},
            "cv": {"pbo": 0.0, "oos_sharpe": 0.0},
        }

    cols = list(df.columns)
    N = len(cols)
    if N == 1:
        w_dict = {cols[0]: 1.0}
    elif method == "equal":
        w_dict = {c: round(1.0 / N, 4) for c in cols}
    else:
        df_clean = df.dropna(how="all").ffill().bfill()
        returns_df = df_clean.pct_change().dropna()
        if returns_df.empty or len(returns_df) < 5:
            w_dict = {c: round(1.0 / N, 4) for c in cols}
        elif method == "risk_parity":
            vols = returns_df.std() * (252 ** 0.5)
            vols = vols.replace(0, 1e-8)
            inv_vols = 1.0 / vols
            raw_w = inv_vols / inv_vols.sum()
            w_dict = {c: round(float(raw_w.get(c, 0.0)), 4) for c in cols}
        elif method == "hrp":
            try:
                hrp = HRPOpt(returns_df)
                raw_w = hrp.optimize()
                w_dict = {c: round(float(raw_w.get(c, 0.0)), 4) for c in cols}
            except Exception:
                w_dict = {c: round(1.0 / N, 4) for c in cols}
        else:  # min_volatility or max_sharpe
            try:
                mu = expected_returns.mean_historical_return(df_clean)
                S = risk_models.sample_cov(df_clean)
                ef = EfficientFrontier(mu, S)
                if method == "min_volatility":
                    ef.min_volatility()
                else:
                    ef.max_sharpe()
                raw_w = ef.clean_weights()
                w_dict = {c: round(float(raw_w.get(c, 0.0)), 4) for c in cols}
            except Exception:
                w_dict = {c: round(1.0 / N, 4) for c in cols}

    # Normalize weights sum if non-zero
    w_sum = sum(w_dict.values())
    if w_sum > 0:
        w_dict = {k: round(v / w_sum, 4) for k, v in w_dict.items()}

    # Compute expected blended metrics & CV metrics
    df_clean = df.dropna(how="all").ffill().bfill()
    returns_df = df_clean.pct_change().dropna()
    expected = {"sharpe": 0.0, "vol": 0.0, "ret": 0.0}
    if not returns_df.empty:
        w_arr = np.array([w_dict.get(c, 0.0) for c in returns_df.columns])
        blend_rets = returns_df.values @ w_arr
        ann_ret = float(np.mean(blend_rets) * 252)
        ann_vol = float(np.std(blend_rets) * (252 ** 0.5) + 1e-8)
        sharpe = float(ann_ret / ann_vol) if ann_vol > 0 else 0.0
        expected = {
            "sharpe": round(sharpe, 2),
            "vol": round(ann_vol, 4),
            "ret": round(ann_ret, 4),
        }

    cv_metrics = purged_cross_validation(df_clean, method=method, n_splits=5, purge_days=5)

    return {
        "weights": w_dict,
        "method": method,
        "expected": expected,
        "cv": {
            "pbo": cv_metrics.get("pbo", 0.0),
            "oos_sharpe": cv_metrics.get("oos_sharpe", 0.0),
        },
    }

