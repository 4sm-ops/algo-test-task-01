"""
Data loading and preprocessing for Volatility & Momentum indicators.
"""
import csv
import pandas as pd
import numpy as np
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import DataConfig, DEFAULT_DATA_CONFIG


def load_quotes(
    csv_path: str | Path,
    config: DataConfig = DEFAULT_DATA_CONFIG,
) -> pd.DataFrame:
    """
    Load and clean quotes from CSV file.

    Args:
        csv_path: Path to CSV file
        config: Data configuration

    Returns:
        Cleaned DataFrame with quotes
    """
    df = pd.read_csv(
        csv_path,
        sep=config.separator,
        quoting=csv.QUOTE_NONE,
    )

    # Clean column names (remove quotes and whitespace)
    df.columns = [col.replace('"', '').strip() for col in df.columns]

    # Parse timestamp
    df[config.col_timestamp] = pd.to_datetime(df[config.col_timestamp])

    # Remove duplicates
    df = df.drop_duplicates()

    # Filter out zero prices
    mask = (df[config.col_bid_price] > 0) & (df[config.col_ask_price] > 0)
    df = df[mask].copy()

    # Sort by timestamp
    df = df.sort_values(config.col_timestamp).reset_index(drop=True)

    return df


def prepare_data(
    df: pd.DataFrame,
    symbol: str,
    config: DataConfig = DEFAULT_DATA_CONFIG,
) -> pd.DataFrame:
    """
    Prepare data for a single symbol.

    Args:
        df: Raw quotes DataFrame
        symbol: Symbol to filter
        config: Data configuration

    Returns:
        DataFrame with mid price and returns
    """
    # Filter by symbol
    df_symbol = df[df[config.col_symbol] == symbol].copy()

    if len(df_symbol) == 0:
        raise ValueError(f"No data found for symbol: {symbol}")

    # Calculate mid price
    df_symbol["mid"] = (
        df_symbol[config.col_bid_price] + df_symbol[config.col_ask_price]
    ) / 2

    # Calculate log returns
    df_symbol["log_return"] = np.log(df_symbol["mid"] / df_symbol["mid"].shift(1))

    # Rename timestamp column
    df_symbol = df_symbol.rename(columns={config.col_timestamp: "ts"})

    # Keep relevant columns
    df_symbol = df_symbol[
        ["ts", "mid", "log_return", config.col_bid_price, config.col_ask_price]
    ].copy()
    df_symbol = df_symbol.rename(columns={
        config.col_bid_price: "bid",
        config.col_ask_price: "ask",
    })

    return df_symbol.reset_index(drop=True)


def get_data_summary(df: pd.DataFrame, symbol: str) -> dict:
    """
    Get summary statistics for loaded data.

    Args:
        df: Prepared DataFrame
        symbol: Symbol name

    Returns:
        Dictionary with summary stats
    """
    return {
        "symbol": symbol,
        "total_rows": len(df),
        "date_range": (df["ts"].min(), df["ts"].max()),
        "price_range": (df["mid"].min(), df["mid"].max()),
        "avg_spread": (df["ask"] - df["bid"]).mean(),
        "avg_return": df["log_return"].mean(),
        "return_std": df["log_return"].std(),
    }
