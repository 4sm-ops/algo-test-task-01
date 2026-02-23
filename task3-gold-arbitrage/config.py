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
    commission_per_contract: float = 0.10  # 10 centavos BRL per contract

    # Risk management
    max_positions: int = 1
    min_liquidity: float = 1.0  # Minimum qty on bid/ask

    # Latency
    b3_latency_ms: int = 250  # B3 leg execution delay in milliseconds (MOEX is instant)

    # Margin (in USD)
    margin_b3: float = 217.0  # Margin per B3 contract (~1300 BRL)
    margin_moex: float = 300.0  # Margin per MOEX contract (~30,000 RUB)

    # Limit order parameters (used by backtest_limit.py)
    limit_order_offset: float = 0.0  # Offset from mid-price (0 = at mid)
    limit_order_timeout_ms: int = 5000  # Cancel limit order after N ms if not filled
    limit_order_price_mode: str = "mid"  # "mid" | "passive" | "aggressive"
    max_b3_spread_for_entry: float = 30.0  # Skip entry when B3 spread > threshold


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
