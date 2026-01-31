"""
Configuration parameters for Volatility & Momentum indicators.
"""
from dataclasses import dataclass


@dataclass
class IndicatorConfig:
    """Indicator calculation parameters."""

    # Volatility windows (in ticks)
    vol_window_short: int = 50
    vol_window_medium: int = 200
    vol_window_long: int = 1000

    # EWMA decay factor (RiskMetrics standard = 0.94)
    ewma_lambda: float = 0.94

    # Momentum windows (in ticks)
    mom_window_short: int = 50
    mom_window_medium: int = 200
    mom_window_long: int = 1000

    # Annualization factor (for display purposes)
    # Assuming ~1000 ticks per minute for HFT data
    ticks_per_day: int = 1_000_000


@dataclass
class DataConfig:
    """Data loading parameters."""

    csv_path: str = "../quotes_202512260854-GOLD.csv"
    separator: str = ";"

    # Symbols
    symbol_b3: str = "GLDG26"
    symbol_moex: str = "GOLD-3.26"

    # Column names (after cleaning)
    col_timestamp: str = "ts"
    col_symbol: str = "symbol"
    col_bid_price: str = "bid_price"
    col_bid_qty: str = "bid_qty"
    col_ask_price: str = "ask_price"
    col_ask_qty: str = "ask_qty"


# Default instances
DEFAULT_INDICATOR_CONFIG = IndicatorConfig()
DEFAULT_DATA_CONFIG = DataConfig()
