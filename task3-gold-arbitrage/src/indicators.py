"""
Technical indicators for Gold Arbitrage Strategy.
"""
import pandas as pd
import numpy as np


def calculate_tradeable_spreads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate spreads based on actual tradeable prices (bid/ask).

    LONG_SPREAD: buy B3 at ask, sell MOEX at bid -> spread_long = ask_b3 - bid_moex
    SHORT_SPREAD: sell B3 at bid, buy MOEX at ask -> spread_short = bid_b3 - ask_moex

    Args:
        df: DataFrame with bid/ask prices for both exchanges

    Returns:
        DataFrame with spread_long and spread_short columns
    """
    df = df.copy()
    # Spread for LONG position (buy B3 at ask, sell MOEX at bid)
    df["spread_long"] = df["ask_b3"] - df["bid_moex"]
    # Spread for SHORT position (sell B3 at bid, buy MOEX at ask)
    df["spread_short"] = df["bid_b3"] - df["ask_moex"]
    return df


def calculate_zscore_dual(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Calculate rolling Z-scores for both spread directions.

    Args:
        df: DataFrame with spread_long and spread_short columns
        window: Rolling window size

    Returns:
        DataFrame with zscore_long and zscore_short columns
    """
    df = df.copy()

    # Z-score for long spread
    rolling_mean_long = df["spread_long"].rolling(window=window, min_periods=window).mean()
    rolling_std_long = df["spread_long"].rolling(window=window, min_periods=window).std()
    rolling_std_long = rolling_std_long.replace(0, np.nan)
    df["zscore_long"] = (df["spread_long"] - rolling_mean_long) / rolling_std_long

    # Z-score for short spread
    rolling_mean_short = df["spread_short"].rolling(window=window, min_periods=window).mean()
    rolling_std_short = df["spread_short"].rolling(window=window, min_periods=window).std()
    rolling_std_short = rolling_std_short.replace(0, np.nan)
    df["zscore_short"] = (df["spread_short"] - rolling_mean_short) / rolling_std_short

    return df


def add_indicators(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Add spread and Z-score indicators to DataFrame.

    Uses tradeable spreads (bid/ask) instead of mid prices for realistic backtesting.

    Args:
        df: DataFrame with bid/ask prices
        window: Z-score rolling window

    Returns:
        DataFrame with added indicator columns
    """
    df = calculate_tradeable_spreads(df)
    df = calculate_zscore_dual(df, window)
    return df
