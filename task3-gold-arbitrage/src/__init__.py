"""
Gold Arbitrage Strategy - Source modules.
"""
from .data_loader import load_quotes, prepare_synchronized_data
from .indicators import calculate_tradeable_spreads, calculate_zscore_dual, add_indicators
from .backtest import Backtest, Trade, Position
from .visualization import plot_equity_plotly, plot_strategy_dashboard

__all__ = [
    "load_quotes",
    "prepare_synchronized_data",
    "calculate_tradeable_spreads",
    "calculate_zscore_dual",
    "add_indicators",
    "Backtest",
    "Trade",
    "Position",
    "plot_equity_plotly",
    "plot_strategy_dashboard",
]
