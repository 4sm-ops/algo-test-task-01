"""
Momentum indicators for trading algorithms.

Implements:
- Rate of Change (ROC): percentage price change
- Simple Momentum: absolute price difference
"""
import pandas as pd
import numpy as np


def roc(
    price: pd.Series,
    window: int,
) -> pd.Series:
    """
    Calculate Rate of Change (ROC).

    ROC = (price[t] / price[t-n]) - 1

    Measures the percentage change in price over n periods.
    Positive values indicate upward momentum, negative - downward.

    Args:
        price: Series of prices (typically mid price)
        window: Lookback period (in ticks)

    Returns:
        Series with ROC values (as decimal, e.g., 0.01 = 1%)
    """
    return (price / price.shift(window)) - 1


def simple_momentum(
    price: pd.Series,
    window: int,
) -> pd.Series:
    """
    Calculate Simple Momentum (absolute price difference).

    Momentum = price[t] - price[t-n]

    Measures the absolute change in price over n periods.
    Useful when you need the actual price movement in points.

    Args:
        price: Series of prices (typically mid price)
        window: Lookback period (in ticks)

    Returns:
        Series with momentum values (in price units)
    """
    return price - price.shift(window)


def momentum_signal(
    momentum: pd.Series,
    threshold: float = 0.0,
) -> pd.Series:
    """
    Generate trading signals from momentum.

    Args:
        momentum: Series of momentum values (ROC or simple)
        threshold: Signal threshold (default 0)

    Returns:
        Series with signals: 1 (bullish), -1 (bearish), 0 (neutral)
    """
    signal = pd.Series(0, index=momentum.index)
    signal[momentum > threshold] = 1
    signal[momentum < -threshold] = -1
    return signal


def add_momentum_indicators(
    df: pd.DataFrame,
    windows: list[int],
) -> pd.DataFrame:
    """
    Add momentum indicators to DataFrame.

    Args:
        df: DataFrame with 'mid' column (price)
        windows: List of window sizes for momentum calculation

    Returns:
        DataFrame with added momentum columns:
        - roc_{window}: Rate of Change for each window
        - mom_{window}: Simple momentum for each window
    """
    df = df.copy()

    # Check if mid price exists
    if "mid" not in df.columns:
        raise ValueError("DataFrame must have 'mid' column")

    price = df["mid"]

    # ROC and simple momentum for each window
    for window in windows:
        df[f"roc_{window}"] = roc(price, window)
        df[f"mom_{window}"] = simple_momentum(price, window)

    return df


def get_momentum_summary(df: pd.DataFrame, windows: list[int]) -> dict:
    """
    Get summary statistics for momentum indicators.

    Args:
        df: DataFrame with momentum columns
        windows: List of window sizes used

    Returns:
        Dictionary with summary stats
    """
    summary = {}

    for window in windows:
        roc_col = f"roc_{window}"
        mom_col = f"mom_{window}"

        if roc_col in df.columns:
            roc_vals = df[roc_col].dropna()
            summary[f"roc_{window}_mean"] = roc_vals.mean()
            summary[f"roc_{window}_std"] = roc_vals.std()
            summary[f"roc_{window}_positive_pct"] = (roc_vals > 0).mean()
            # Autocorrelation (momentum persistence)
            if len(roc_vals) > 1:
                summary[f"roc_{window}_autocorr"] = roc_vals.autocorr(lag=1)

        if mom_col in df.columns:
            mom_vals = df[mom_col].dropna()
            summary[f"mom_{window}_mean"] = mom_vals.mean()
            summary[f"mom_{window}_std"] = mom_vals.std()
            summary[f"mom_{window}_positive_pct"] = (mom_vals > 0).mean()

    return summary
