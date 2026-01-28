"""
Data loading and preprocessing for Gold Arbitrage Strategy.
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple

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
    # Read CSV with semicolon separator
    # Header has weird quoting: "ts;""symbol""..." - use QUOTE_NONE
    import csv
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


def prepare_synchronized_data(
    df: pd.DataFrame,
    symbol_b3: str,
    symbol_moex: str,
    config: DataConfig = DEFAULT_DATA_CONFIG,
) -> pd.DataFrame:
    """
    Prepare synchronized data for both symbols.

    Creates a merged DataFrame with forward-filled prices for both symbols,
    aligned by timestamp.

    Args:
        df: Raw quotes DataFrame
        symbol_b3: B3 symbol name
        symbol_moex: MOEX symbol name
        config: Data configuration

    Returns:
        DataFrame with synchronized bid/ask for both symbols
    """
    # Split by symbol
    df_b3 = df[df[config.col_symbol] == symbol_b3].copy()
    df_moex = df[df[config.col_symbol] == symbol_moex].copy()

    # Rename columns
    b3_cols = {
        config.col_bid_price: "bid_b3",
        config.col_ask_price: "ask_b3",
        config.col_bid_qty: "bid_qty_b3",
        config.col_ask_qty: "ask_qty_b3",
    }
    moex_cols = {
        config.col_bid_price: "bid_moex",
        config.col_ask_price: "ask_moex",
        config.col_bid_qty: "bid_qty_moex",
        config.col_ask_qty: "ask_qty_moex",
    }

    df_b3 = df_b3.rename(columns=b3_cols)
    df_moex = df_moex.rename(columns=moex_cols)

    # Keep only necessary columns
    df_b3 = df_b3[[config.col_timestamp] + list(b3_cols.values())]
    df_moex = df_moex[[config.col_timestamp] + list(moex_cols.values())]

    # Merge on timestamp (outer join to keep all ticks)
    merged = pd.merge(
        df_b3,
        df_moex,
        on=config.col_timestamp,
        how="outer",
    )

    # Sort by timestamp
    merged = merged.sort_values(config.col_timestamp).reset_index(drop=True)

    # Forward fill prices (carry last known price)
    price_cols = ["bid_b3", "ask_b3", "bid_moex", "ask_moex"]
    qty_cols = ["bid_qty_b3", "ask_qty_b3", "bid_qty_moex", "ask_qty_moex"]

    merged[price_cols] = merged[price_cols].ffill()
    merged[qty_cols] = merged[qty_cols].ffill()

    # Drop rows where we don't have both symbols yet
    merged = merged.dropna(subset=price_cols)

    # Calculate mid prices
    merged["mid_b3"] = (merged["bid_b3"] + merged["ask_b3"]) / 2
    merged["mid_moex"] = (merged["bid_moex"] + merged["ask_moex"]) / 2

    return merged.reset_index(drop=True)


def get_data_summary(df: pd.DataFrame) -> dict:
    """
    Get summary statistics for loaded data.

    Args:
        df: Synchronized DataFrame

    Returns:
        Dictionary with summary stats
    """
    return {
        "total_rows": len(df),
        "date_range": (df["ts"].min(), df["ts"].max()),
        "b3_price_range": (df["mid_b3"].min(), df["mid_b3"].max()),
        "moex_price_range": (df["mid_moex"].min(), df["mid_moex"].max()),
        "b3_avg_spread": (df["ask_b3"] - df["bid_b3"]).mean(),
        "moex_avg_spread": (df["ask_moex"] - df["bid_moex"]).mean(),
    }
