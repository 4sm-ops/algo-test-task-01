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
    calmar_ratio: float
    var_95: float
    roi_on_margin: float  # Return on margin capital (%)


class Backtest:
    """
    Backtesting engine for spread arbitrage strategy.
    """

    def __init__(
        self,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        stop_loss_threshold: float = 4.0,
        commission_per_contract: float = 0.10,
        position_size: int = 1,
        min_liquidity: float = 1.0,
        b3_latency_ms: int = 250,
        margin_b3: float = 217.0,
        margin_moex: float = 300.0,
    ):
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.stop_loss_threshold = stop_loss_threshold
        self.commission_per_contract = commission_per_contract
        self.position_size = position_size
        self.min_liquidity = min_liquidity
        self.b3_latency_ms = b3_latency_ms
        self.margin_b3 = margin_b3
        self.margin_moex = margin_moex
        self.margin_per_trade = margin_b3 + margin_moex

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

    def _calculate_commission(self) -> float:
        """Calculate commission for one leg (entry or exit).

        Commission is 0.10 BRL per contract. Each leg has 2 contracts (B3 + MOEX).
        """
        return self.commission_per_contract * self.position_size * 2

    def _find_delayed_b3_price(
        self,
        df: pd.DataFrame,
        signal_idx: int,
        signal_time: pd.Timestamp,
        is_buy: bool,
    ) -> Optional[float]:
        """
        Find B3 price after latency delay.

        Args:
            df: Full DataFrame
            signal_idx: Index where signal occurred
            signal_time: Timestamp of signal
            is_buy: True if buying B3 (use ask), False if selling (use bid)

        Returns:
            B3 price after delay, or None if no tick found
        """
        target_time = signal_time + pd.Timedelta(milliseconds=self.b3_latency_ms)

        # Search forward for first tick after target_time
        for i in range(signal_idx + 1, min(signal_idx + 1000, len(df))):
            if df.iloc[i]["ts"] >= target_time:
                row = df.iloc[i]
                return row["ask_b3"] if is_buy else row["bid_b3"]

        # No tick found within search window
        return None

    def _open_position(
        self,
        row: pd.Series,
        position_type: PositionType,
        delayed_b3_price: float,
    ) -> None:
        """Open a new position with delayed B3 execution.

        MOEX executes instantly at signal time.
        B3 executes after latency delay at delayed_b3_price.
        """
        if position_type == PositionType.LONG_SPREAD:
            entry_zscore = row["zscore_long"]
            entry_moex_price = row["bid_moex"]  # MOEX instant
            entry_b3_price = delayed_b3_price   # B3 delayed
            # Spread is calculated with actual execution prices
            entry_spread = entry_b3_price - entry_moex_price
        else:  # SHORT_SPREAD
            entry_zscore = row["zscore_short"]
            entry_moex_price = row["ask_moex"]  # MOEX instant
            entry_b3_price = delayed_b3_price   # B3 delayed
            entry_spread = entry_b3_price - entry_moex_price

        self.position = Position(
            type=position_type,
            entry_time=row["ts"],
            entry_zscore=entry_zscore,
            entry_spread=entry_spread,
            entry_b3_price=entry_b3_price,
            entry_moex_price=entry_moex_price,
        )

    def _close_position(self, row: pd.Series, delayed_b3_price: float) -> Trade:
        """Close current position and record trade with delayed B3 execution.

        MOEX executes instantly at signal time.
        B3 executes after latency delay at delayed_b3_price.
        """
        if self.position.type == PositionType.LONG_SPREAD:
            exit_b3 = delayed_b3_price  # Sell B3 (delayed)
            exit_moex = row["ask_moex"]  # Buy back MOEX (instant)
            exit_spread = exit_b3 - exit_moex
            exit_zscore = row["zscore_short"]
            pnl = (exit_b3 - self.position.entry_b3_price) - (exit_moex - self.position.entry_moex_price)
        else:  # SHORT_SPREAD
            exit_b3 = delayed_b3_price  # Buy back B3 (delayed)
            exit_moex = row["bid_moex"]  # Sell MOEX (instant)
            exit_spread = exit_b3 - exit_moex
            exit_zscore = row["zscore_long"]
            pnl = (self.position.entry_b3_price - exit_b3) - (self.position.entry_moex_price - exit_moex)

        pnl *= self.position_size

        # Commission for entry and exit (4 contracts total: 2 at entry + 2 at exit)
        commission = self._calculate_commission() * 2

        trade = Trade(
            entry_time=self.position.entry_time,
            exit_time=row["ts"],
            position_type=self.position.type,
            entry_zscore=self.position.entry_zscore,
            exit_zscore=exit_zscore,
            entry_spread=self.position.entry_spread,
            exit_spread=exit_spread,
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

        Models latency: MOEX executes instantly, B3 executes after b3_latency_ms delay.

        Args:
            df: DataFrame with prices and indicators (zscore column required)

        Returns:
            BacktestResult with all metrics
        """
        self.position = Position()
        self.trades = []
        self.equity = [0.0]

        cumulative_pnl = 0.0

        # Convert to list for faster indexing when searching for delayed prices
        df_list = df.reset_index(drop=True)

        for idx in range(len(df_list)):
            row = df_list.iloc[idx]

            # Skip rows with NaN zscore (need both for entry decisions)
            if pd.isna(row["zscore_long"]) or pd.isna(row["zscore_short"]):
                self.equity.append(cumulative_pnl)
                continue

            zscore_long = row["zscore_long"]
            zscore_short = row["zscore_short"]
            has_liquidity = self._check_liquidity(row)

            # Check for signals
            if self.position.is_flat() and has_liquidity:
                # Entry signals - use the spread we would actually trade
                if zscore_long < -self.entry_threshold:
                    # LONG spread: buy B3 at ask (delayed), sell MOEX at bid (instant)
                    delayed_b3_price = self._find_delayed_b3_price(
                        df_list, idx, row["ts"], is_buy=True
                    )
                    if delayed_b3_price is not None:
                        self._open_position(row, PositionType.LONG_SPREAD, delayed_b3_price)

                elif zscore_short > self.entry_threshold:
                    # SHORT spread: sell B3 at bid (delayed), buy MOEX at ask (instant)
                    delayed_b3_price = self._find_delayed_b3_price(
                        df_list, idx, row["ts"], is_buy=False
                    )
                    if delayed_b3_price is not None:
                        self._open_position(row, PositionType.SHORT_SPREAD, delayed_b3_price)

            elif not self.position.is_flat():
                # Exit signals - use the corresponding zscore for exit
                should_exit = False

                if self.position.type == PositionType.LONG_SPREAD:
                    # Exit LONG: sell B3 (delayed), buy MOEX (instant)
                    if zscore_short > self.stop_loss_threshold:
                        should_exit = True  # Stop loss
                    elif zscore_long > -self.exit_threshold:
                        should_exit = True  # Take profit - spread normalized
                else:  # SHORT_SPREAD
                    # Exit SHORT: buy B3 (delayed), sell MOEX (instant)
                    if zscore_long < -self.stop_loss_threshold:
                        should_exit = True  # Stop loss
                    elif zscore_short < self.exit_threshold:
                        should_exit = True  # Take profit - spread normalized

                if should_exit and has_liquidity:
                    # Determine B3 action for exit
                    is_buy_b3 = self.position.type == PositionType.SHORT_SPREAD
                    delayed_b3_price = self._find_delayed_b3_price(
                        df_list, idx, row["ts"], is_buy=is_buy_b3
                    )
                    if delayed_b3_price is not None:
                        trade = self._close_position(row, delayed_b3_price)
                        cumulative_pnl += trade.net_pnl

            self.equity.append(cumulative_pnl)

        # Force close any open position at the end (use last price, no delay)
        if not self.position.is_flat():
            last_row = df.iloc[-1]
            # For forced close, use current B3 price (no delay - end of data)
            if self.position.type == PositionType.LONG_SPREAD:
                forced_b3_price = last_row["bid_b3"]  # Sell B3
            else:
                forced_b3_price = last_row["ask_b3"]  # Buy B3
            trade = self._close_position(last_row, forced_b3_price)
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

        # Calmar ratio = Annualized Return / Max Drawdown
        # Assuming 252 trading days per year
        num_periods = len(df)
        annualized_return = net_pnl * (252 / num_periods) if num_periods > 0 else 0
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        # VaR 95% - 5th percentile of trade PnLs
        if num_trades > 0:
            trade_pnls = [t.net_pnl for t in self.trades]
            var_95 = np.percentile(trade_pnls, 5)
        else:
            var_95 = 0

        # ROI on margin - return on margin capital
        total_margin = self.margin_per_trade * self.position_size
        roi_on_margin = (net_pnl / total_margin * 100) if total_margin > 0 else 0

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
            calmar_ratio=calmar_ratio,
            var_95=var_95,
            roi_on_margin=roi_on_margin,
        )
