"""
Gold Arbitrage Strategy - Source modules.
"""
from .data_loader import load_quotes, prepare_synchronized_data
from .indicators import calculate_spread, calculate_zscore
from .backtest import Backtest, Trade, Position
from .visualization import plot_equity_plotly, plot_strategy_dashboard

__all__ = [
    "load_quotes",
    "prepare_synchronized_data",
    "calculate_spread",
    "calculate_zscore",
    "Backtest",
    "Trade",
    "Position",
    "plot_equity_plotly",
    "plot_strategy_dashboard",
]
