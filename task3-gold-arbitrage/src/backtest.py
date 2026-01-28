"""
Backtesting engine for Gold Arbitrage Strategy.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class PositionType(Enum):
    """Position type in spread trade."""
    NONE = 0
    LONG_SPREAD = 1   # Long B3, Short MOEX
    SHORT_SPREAD = -1  # Short B3, Long MOEX


@dataclass
class Trade:
    """Single trade record."""
    entry_time: pd.Timestamp
    exit_time: Optional[pd.Timestamp]
    position_type: PositionType
    entry_zscore: float
    exit_zscore: Optional[float]
    entry_spread: float
    exit_spread: Optional[float]
    entry_b3_price: float
    entry_moex_price: float
    exit_b3_price: Optional[float]
    exit_moex_price: Optional[float]
    pnl: float = 0.0
    commission: float = 0.0

    @property
    def net_pnl(self) -> float:
        return self.pnl - self.commission

    @property
    def is_closed(self) -> bool:
        return self.exit_time is not None


@dataclass
class Position:
    """Current position state."""
    type: PositionType = PositionType.NONE
    entry_time: Optional[pd.Timestamp] = None
    entry_zscore: float = 0.0
    entry_spread: float = 0.0
    entry_b3_price: float = 0.0
    entry_moex_price: float = 0.0

    def is_flat(self) -> bool:
        return self.type == PositionType.NONE


@dataclass
class BacktestResult:
    """Backtest results summary."""
    trades: List[Trade]
    equity_curve: pd.Series
    total_pnl: float
    total_commission: float
    net_pnl: float
    num_trades: int
    win_rate: float
    avg_trade_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float


class Backtest:
    """
    Backtesting engine for spread arbitrage strategy.
    """

    def __init__(
        self,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        stop_loss_threshold: float = 4.0,
        commission_pct: float = 0.0001,
        position_size: int = 1,
        min_liquidity: float = 1.0,
    ):
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.stop_loss_threshold = stop_loss_threshold
        self.commission_pct = commission_pct
        self.position_size = position_size
        self.min_liquidity = min_liquidity

        self.position = Position()
        self.trades: List[Trade] = []
        self.equity: List[float] = []

    def _check_liquidity(self, row: pd.Series) -> bool:
        """Check if there's enough liquidity on both sides."""
        return (
            row["bid_qty_b3"] >= self.min_liquidity
            and row["ask_qty_b3"] >= self.min_liquidity
            and row["bid_qty_moex"] >= self.min_liquidity
            and row["ask_qty_moex"] >= self.min_liquidity
        )

    def _calculate_commission(self, b3_price: float, moex_price: float) -> float:
        """Calculate commission for a trade (one leg)."""
        notional = (b3_price + moex_price) * self.position_size
        return notional * self.commission_pct

    def _open_position(
        self,
        row: pd.Series,
        position_type: PositionType,
    ) -> None:
        """Open a new position."""
        self.position = Position(
            type=position_type,
            entry_time=row["ts"],
            entry_zscore=row["zscore"],
            entry_spread=row["spread"],
            entry_b3_price=row["ask_b3"] if position_type == PositionType.LONG_SPREAD else row["bid_b3"],
            entry_moex_price=row["bid_moex"] if position_type == PositionType.LONG_SPREAD else row["ask_moex"],
        )

    def _close_position(self, row: pd.Series) -> Trade:
        """Close current position and record trade."""
        if self.position.type == PositionType.LONG_SPREAD:
            exit_b3 = row["bid_b3"]  # Sell B3
            exit_moex = row["ask_moex"]  # Buy back MOEX
            pnl = (exit_b3 - self.position.entry_b3_price) - (exit_moex - self.position.entry_moex_price)
        else:  # SHORT_SPREAD
            exit_b3 = row["ask_b3"]  # Buy back B3
            exit_moex = row["bid_moex"]  # Sell MOEX
            pnl = (self.position.entry_b3_price - exit_b3) - (self.position.entry_moex_price - exit_moex)

        pnl *= self.position_size

        # Commission for entry and exit (4 legs total)
        commission = (
            self._calculate_commission(self.position.entry_b3_price, self.position.entry_moex_price)
            + self._calculate_commission(exit_b3, exit_moex)
        )

        trade = Trade(
            entry_time=self.position.entry_time,
            exit_time=row["ts"],
            position_type=self.position.type,
            entry_zscore=self.position.entry_zscore,
            exit_zscore=row["zscore"],
            entry_spread=self.position.entry_spread,
            exit_spread=row["spread"],
            entry_b3_price=self.position.entry_b3_price,
            entry_moex_price=self.position.entry_moex_price,
            exit_b3_price=exit_b3,
            exit_moex_price=exit_moex,
            pnl=pnl,
            commission=commission,
        )

        self.trades.append(trade)
        self.position = Position()

        return trade

    def run(self, df: pd.DataFrame) -> BacktestResult:
        """
        Run backtest on prepared data.

        Args:
            df: DataFrame with prices and indicators (zscore column required)

        Returns:
            BacktestResult with all metrics
        """
        self.position = Position()
        self.trades = []
        self.equity = [0.0]

        cumulative_pnl = 0.0

        for idx, row in df.iterrows():
            # Skip rows with NaN zscore
            if pd.isna(row["zscore"]):
                self.equity.append(cumulative_pnl)
                continue

            zscore = row["zscore"]
            has_liquidity = self._check_liquidity(row)

            # Check for signals
            if self.position.is_flat() and has_liquidity:
                # Entry signals
                if zscore > self.entry_threshold:
                    # Spread too high -> SHORT spread (sell B3, buy MOEX)
                    self._open_position(row, PositionType.SHORT_SPREAD)
                elif zscore < -self.entry_threshold:
                    # Spread too low -> LONG spread (buy B3, sell MOEX)
                    self._open_position(row, PositionType.LONG_SPREAD)

            elif not self.position.is_flat():
                # Exit signals
                should_exit = False

                # Stop loss
                if abs(zscore) > self.stop_loss_threshold:
                    should_exit = True

                # Take profit / mean reversion
                elif self.position.type == PositionType.LONG_SPREAD and zscore > -self.exit_threshold:
                    should_exit = True
                elif self.position.type == PositionType.SHORT_SPREAD and zscore < self.exit_threshold:
                    should_exit = True

                if should_exit and has_liquidity:
                    trade = self._close_position(row)
                    cumulative_pnl += trade.net_pnl

            self.equity.append(cumulative_pnl)

        # Force close any open position at the end
        if not self.position.is_flat():
            last_row = df.iloc[-1]
            trade = self._close_position(last_row)
            cumulative_pnl += trade.net_pnl
            self.equity[-1] = cumulative_pnl

        return self._calculate_results(df)

    def _calculate_results(self, df: pd.DataFrame) -> BacktestResult:
        """Calculate backtest metrics."""
        equity_series = pd.Series(self.equity, index=range(len(self.equity)))

        total_pnl = sum(t.pnl for t in self.trades)
        total_commission = sum(t.commission for t in self.trades)
        net_pnl = sum(t.net_pnl for t in self.trades)
        num_trades = len(self.trades)

        # Win rate
        winning_trades = [t for t in self.trades if t.net_pnl > 0]
        win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0

        # Average trade
        avg_trade_pnl = net_pnl / num_trades if num_trades > 0 else 0

        # Max drawdown
        rolling_max = equity_series.cummax()
        drawdown = equity_series - rolling_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0

        # Sharpe ratio (simplified, using trade returns)
        if num_trades > 1:
            trade_returns = [t.net_pnl for t in self.trades]
            sharpe_ratio = (
                np.mean(trade_returns) / np.std(trade_returns) * np.sqrt(252)
                if np.std(trade_returns) > 0
                else 0
            )
        else:
            sharpe_ratio = 0

        # Profit factor
        gross_profit = sum(t.net_pnl for t in self.trades if t.net_pnl > 0)
        gross_loss = abs(sum(t.net_pnl for t in self.trades if t.net_pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        return BacktestResult(
            trades=self.trades,
            equity_curve=equity_series,
            total_pnl=total_pnl,
            total_commission=total_commission,
            net_pnl=net_pnl,
            num_trades=num_trades,
            win_rate=win_rate,
            avg_trade_pnl=avg_trade_pnl,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
        )
