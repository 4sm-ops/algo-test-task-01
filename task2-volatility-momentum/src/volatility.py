"""
Volatility indicators for trading algorithms.

Implements:
- Realized Volatility (RV): sum of squared returns
- EWMA Volatility: exponentially weighted moving average
"""
import pandas as pd
import numpy as np


def realized_volatility(
    returns: pd.Series,
    window: int,
) -> pd.Series:
    """
    Calculate Realized Volatility (RV).

    RV = sqrt(sum(returns[t-n:t]^2))

    This is the standard measure for high-frequency volatility estimation.
    It captures the actual variation in returns over the window.

    Args:
        returns: Series of log returns
        window: Rolling window size (in ticks)

    Returns:
        Series with realized volatility values
    """
    returns_sq = returns ** 2
    rv = returns_sq.rolling(window=window, min_periods=window).sum()
    return np.sqrt(rv)


def ewma_volatility(
    returns: pd.Series,
    decay: float = 0.94,
) -> pd.Series:
    """
    Calculate EWMA (Exponentially Weighted Moving Average) Volatility.

    Uses the RiskMetrics model:
    sigma^2[t] = lambda * sigma^2[t-1] + (1-lambda) * return[t]^2

    EWMA adapts quickly to recent changes, making it suitable for
    trading systems that need responsive volatility estimates.

    Args:
        returns: Series of log returns
        decay: Decay factor lambda (default 0.94 from RiskMetrics)
               Higher decay = more weight on history
               Lower decay = more weight on recent data

    Returns:
        Series with EWMA volatility values
    """
    returns_sq = returns ** 2

    # Convert decay to span for pandas ewm
    # span = 2/(1-lambda) - 1, so for lambda=0.94, span ~= 32
    span = (2 / (1 - decay)) - 1

    ewma_var = returns_sq.ewm(span=span, adjust=False).mean()
    return np.sqrt(ewma_var)


def add_volatility_indicators(
    df: pd.DataFrame,
    windows: list[int],
    ewma_decay: float = 0.94,
) -> pd.DataFrame:
    """
    Add volatility indicators to DataFrame.

    Args:
        df: DataFrame with 'log_return' column
        windows: List of window sizes for RV calculation
        ewma_decay: Decay factor for EWMA

    Returns:
        DataFrame with added volatility columns:
        - rv_{window}: Realized volatility for each window
        - ewma_vol: EWMA volatility
    """
    df = df.copy()

    # Check if log_return exists
    if "log_return" not in df.columns:
        raise ValueError("DataFrame must have 'log_return' column")

    returns = df["log_return"]

    # Realized volatility for each window
    for window in windows:
        df[f"rv_{window}"] = realized_volatility(returns, window)

    # EWMA volatility
    df["ewma_vol"] = ewma_volatility(returns, ewma_decay)

    return df


def get_volatility_summary(df: pd.DataFrame, windows: list[int]) -> dict:
    """
    Get summary statistics for volatility indicators.

    Args:
        df: DataFrame with volatility columns
        windows: List of window sizes used

    Returns:
        Dictionary with summary stats
    """
    summary = {}

    for window in windows:
        col = f"rv_{window}"
        if col in df.columns:
            summary[f"rv_{window}_mean"] = df[col].mean()
            summary[f"rv_{window}_median"] = df[col].median()
            summary[f"rv_{window}_max"] = df[col].max()
            summary[f"rv_{window}_q95"] = df[col].quantile(0.95)

    if "ewma_vol" in df.columns:
        summary["ewma_vol_mean"] = df["ewma_vol"].mean()
        summary["ewma_vol_median"] = df["ewma_vol"].median()
        summary["ewma_vol_max"] = df["ewma_vol"].max()
        summary["ewma_vol_q95"] = df["ewma_vol"].quantile(0.95)

    return summary
