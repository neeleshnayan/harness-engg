"""Portfolio optimization via PyPortfolioOpt.

Calculates optimal weights for a set of scoped assets based on historical data.
Objectives supported: max_sharpe, min_volatility.
"""

import pandas as pd
from pypfopt import expected_returns, risk_models
from pypfopt.efficient_frontier import EfficientFrontier

from app.fund.marketdata import fetch_daily_bars, BarsError

def optimize_portfolio(symbols: list[str], lookback_days: int = 365, method: str = "max_sharpe") -> dict:
    """Calculate optimal weights, efficient frontier, and correlation for the given symbols using PyPortfolioOpt."""
    if not symbols:
        return {"weights": {}, "frontier_points": [], "correlation": {}}
        
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
            "correlation": {}
        }
        
    # Build dataframe, ffill and bfill to handle missing data
    df = pd.DataFrame(prices)
    df = df.dropna(how="all").ffill().bfill()
    
    try:
        # Calculate expected returns and sample covariance matrix
        mu = expected_returns.mean_historical_return(df)
        S = risk_models.sample_cov(df)
        
        # Optimize
        ef = EfficientFrontier(mu, S)
        if method == "max_sharpe":
            ef.max_sharpe()
        elif method == "min_volatility":
            ef.min_volatility()
        else:
            raise ValueError(f"Unknown optimization method: {method}")
            
        cleaned_weights = ef.clean_weights()
        
        # Calculate correlation matrix
        corr = df.pct_change().corr()
        correlation = corr.to_dict()

        # Compute efficient frontier points
        import numpy as np
        frontier_points = []
        min_ret = mu.min()
        max_ret = mu.max()
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
                        "weights": {sym: w.get(sym, 0.0) for sym in symbols}
                    })
                except Exception:
                    pass

        # Ensure all original symbols are in the output
        weights_result = {sym: cleaned_weights.get(sym, 0.0) for sym in symbols}
        
        return {
            "weights": weights_result,
            "frontier_points": frontier_points,
            "correlation": correlation
        }
    except Exception as e:
        # Fallback to equal weight on error
        return {
            "weights": {sym: 1.0 / len(symbols) for sym in symbols},
            "frontier_points": [],
            "correlation": {}
        }
