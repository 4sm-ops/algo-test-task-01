"""
Technical indicators for Gold Arbitrage Strategy.
"""
import pandas as pd
import numpy as np


def calculate_spread(df: pd.DataFrame) -> pd.Series:
    """
    Calculate spread between B3 and MOEX mid prices.

    Args:
        df: DataFrame with mid_b3 and mid_moex columns

    Returns:
        Series with spread values
    """
    return df["mid_b3"] - df["mid_moex"]


def calculate_zscore(
    spread: pd.Series,
    window: int,
) -> pd.Series:
    """
    Calculate rolling Z-score of spread.

    Z-score = (spread - rolling_mean) / rolling_std

    Args:
        spread: Series with spread values
        window: Rolling window size

    Returns:
        Series with Z-score values
    """
    rolling_mean = spread.rolling(window=window, min_periods=window).mean()
    rolling_std = spread.rolling(window=window, min_periods=window).std()

    # Avoid division by zero
    rolling_std = rolling_std.replace(0, np.nan)

    zscore = (spread - rolling_mean) / rolling_std

    return zscore


def add_indicators(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Add spread and Z-score indicators to DataFrame.

    Args:
        df: DataFrame with mid prices
        window: Z-score rolling window

    Returns:
        DataFrame with added indicator columns
    """
    df = df.copy()
    df["spread"] = calculate_spread(df)
    df["zscore"] = calculate_zscore(df["spread"], window)
    return df
