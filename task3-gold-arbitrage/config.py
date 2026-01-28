"""
Configuration parameters for Gold Arbitrage Strategy.
"""
from dataclasses import dataclass


@dataclass
class StrategyConfig:
    """Strategy parameters."""

    # Symbols
    symbol_b3: str = "GLDG26"
    symbol_moex: str = "GOLD-3.26"

    # Z-score parameters
    zscore_window: int = 1000  # Rolling window for mean/std
    entry_threshold: float = 2.0  # Enter when |z| > threshold
    exit_threshold: float = 0.5  # Exit when |z| < threshold
    stop_loss_threshold: float = 4.0  # Stop loss when |z| > threshold

    # Position sizing
    position_size: int = 1  # Contracts per leg

    # Costs
    commission_pct: float = 0.0001  # 0.01% per trade

    # Risk management
    max_positions: int = 1
    min_liquidity: float = 1.0  # Minimum qty on bid/ask


@dataclass
class DataConfig:
    """Data loading parameters."""

    csv_path: str = "quotes_202512260854-GOLD.csv"
    separator: str = ";"

    # Column names (after cleaning)
    col_timestamp: str = "ts"
    col_symbol: str = "symbol"
    col_bid_price: str = "bid_price"
    col_bid_qty: str = "bid_qty"
    col_ask_price: str = "ask_price"
    col_ask_qty: str = "ask_qty"


# Default instances
DEFAULT_STRATEGY_CONFIG = StrategyConfig()
DEFAULT_DATA_CONFIG = DataConfig()
