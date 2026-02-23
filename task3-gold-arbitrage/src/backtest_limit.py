"""
Backtesting engine for Gold Arbitrage Strategy with LIMIT ORDERS on B3.

Key difference from backtest.py (market orders):
- B3 leg uses limit orders placed inside the spread (at mid-price)
- MOEX leg executes at market at the moment B3 fill happens (not at signal time)
- Fill probability modeled via "price touch" — limit order fills when ask/bid reaches limit price

This reduces round-trip cost from ~28 pts (crossing spread) to ~4 pts (MOEX spread only).
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
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
    entry_fill_time_ms: float = 0.0  # Time from signal to B3 fill (ms)
    exit_fill_time_ms: float = 0.0

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
    roi_on_margin: float
    # Limit order specific
    limit_orders_attempted: int = 0
    limit_orders_filled: int = 0
    limit_fill_rate: float = 0.0
    avg_fill_time_ms: float = 0.0


class BacktestLimit:
    """
    Backtesting engine with limit orders on B3.

    Instead of crossing the spread on B3 (market orders), we place limit orders
    inside the B3 spread (at mid-price by default). This dramatically reduces
    transaction costs but introduces fill risk.

    Fill model: "Price Touch" — a limit BUY at price P fills when ask_b3 <= P
    after the latency delay. This is optimistic (doesn't model queue position).
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
        # Limit order params
        limit_order_offset: float = 0.0,
        limit_order_timeout_ms: int = 5000,
        limit_order_price_mode: str = "mid",
        max_b3_spread_for_entry: float = 30.0,
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

        # Limit order params
        self.limit_order_offset = limit_order_offset
        self.limit_order_timeout_ms = limit_order_timeout_ms
        self.limit_order_price_mode = limit_order_price_mode
        self.max_b3_spread_for_entry = max_b3_spread_for_entry

        self.position = Position()
        self.trades: List[Trade] = []
        self.equity: List[float] = []

        # Stats
        self.limit_attempts = 0
        self.limit_fills = 0
        self.fill_times_ms: List[float] = []

    def _check_liquidity(self, row: pd.Series) -> bool:
        """Check if there's enough liquidity on both sides."""
        return (
            row["bid_qty_b3"] >= self.min_liquidity
            and row["ask_qty_b3"] >= self.min_liquidity
            and row["bid_qty_moex"] >= self.min_liquidity
            and row["ask_qty_moex"] >= self.min_liquidity
        )

    def _check_b3_spread(self, row: pd.Series) -> bool:
        """Check if B3 spread is narrow enough for entry."""
        b3_spread = row["ask_b3"] - row["bid_b3"]
        return b3_spread <= self.max_b3_spread_for_entry

    def _calculate_commission(self) -> float:
        """Calculate commission for one leg (entry or exit).
        Commission is 0.10 BRL per contract. Each leg has 2 contracts (B3 + MOEX).
        """
        return self.commission_per_contract * self.position_size * 2

    def _calculate_limit_price(
        self, bid_b3: float, ask_b3: float, is_buy: bool
    ) -> float:
        """
        Calculate limit order price for B3.

        Args:
            bid_b3: Current best bid on B3
            ask_b3: Current best ask on B3
            is_buy: True if buying B3 (limit below ask), False if selling (limit above bid)

        Returns:
            Limit order price
        """
        mid = (bid_b3 + ask_b3) / 2

        if self.limit_order_price_mode == "mid":
            return mid
        elif self.limit_order_price_mode == "passive":
            # Join the queue at best price (most passive)
            return bid_b3 if is_buy else ask_b3
        elif self.limit_order_price_mode == "aggressive":
            # Offset from mid toward the crossing side
            offset = self.limit_order_offset
            return (mid + offset) if is_buy else (mid - offset)
        return mid

    def _find_limit_fill(
        self,
        df: pd.DataFrame,
        signal_idx: int,
        signal_time: pd.Timestamp,
        limit_price: float,
        is_buy: bool,
    ) -> Optional[Tuple[float, int, pd.Series]]:
        """
        Scan forward for limit order fill on B3.

        Fill model: "Price Touch"
        - BUY limit at P fills when ask_b3 <= P (someone willing to sell at our price)
        - SELL limit at P fills when bid_b3 >= P (someone willing to buy at our price)
        - Fill only after latency delay (order needs time to reach exchange)
        - Fill only within timeout window

        Caveat: This model does NOT account for queue position or adverse selection.
        In reality, fill rate would be lower.

        Args:
            df: Full DataFrame
            signal_idx: Index where signal occurred
            signal_time: Timestamp of signal
            limit_price: Our limit order price
            is_buy: True for limit buy, False for limit sell

        Returns:
            (fill_price, fill_idx, fill_row) or None if no fill within timeout
        """
        order_active_time = signal_time + pd.Timedelta(milliseconds=self.b3_latency_ms)
        deadline = order_active_time + pd.Timedelta(milliseconds=self.limit_order_timeout_ms)

        max_scan = min(signal_idx + 5000, len(df))

        for i in range(signal_idx + 1, max_scan):
            row = df.iloc[i]
            ts = row["ts"]

            # Order not yet at exchange
            if ts < order_active_time:
                continue

            # Timeout — cancel
            if ts > deadline:
                return None

            # Check fill condition
            if is_buy and row["ask_b3"] <= limit_price and row["ask_qty_b3"] >= self.position_size:
                fill_time_ms = (ts - signal_time).total_seconds() * 1000
                return (limit_price, i, row, fill_time_ms)
            elif not is_buy and row["bid_b3"] >= limit_price and row["bid_qty_b3"] >= self.position_size:
                fill_time_ms = (ts - signal_time).total_seconds() * 1000
                return (limit_price, i, row, fill_time_ms)

        return None

    def _open_position(
        self,
        fill_row: pd.Series,
        position_type: PositionType,
        b3_fill_price: float,
    ) -> None:
        """Open a new position.

        B3 fills at limit price.
        MOEX executes at market at the moment of B3 fill (not at signal time).
        """
        if position_type == PositionType.LONG_SPREAD:
            entry_zscore = fill_row["zscore_long"]
            entry_moex_price = fill_row["bid_moex"]  # MOEX sell at fill time
            entry_b3_price = b3_fill_price
            entry_spread = entry_b3_price - entry_moex_price
        else:  # SHORT_SPREAD
            entry_zscore = fill_row["zscore_short"]
            entry_moex_price = fill_row["ask_moex"]  # MOEX buy at fill time
            entry_b3_price = b3_fill_price
            entry_spread = entry_b3_price - entry_moex_price

        self.position = Position(
            type=position_type,
            entry_time=fill_row["ts"],
            entry_zscore=entry_zscore,
            entry_spread=entry_spread,
            entry_b3_price=entry_b3_price,
            entry_moex_price=entry_moex_price,
        )

    def _close_position(
        self, fill_row: pd.Series, b3_fill_price: float, fill_time_ms: float = 0.0
    ) -> Trade:
        """Close current position.

        B3 fills at limit price.
        MOEX executes at market at the moment of B3 fill.
        """
        if self.position.type == PositionType.LONG_SPREAD:
            exit_b3 = b3_fill_price
            exit_moex = fill_row["ask_moex"]  # Buy back MOEX at fill time
            exit_spread = exit_b3 - exit_moex
            exit_zscore = fill_row["zscore_short"]
            pnl = (exit_b3 - self.position.entry_b3_price) - (exit_moex - self.position.entry_moex_price)
        else:  # SHORT_SPREAD
            exit_b3 = b3_fill_price
            exit_moex = fill_row["bid_moex"]  # Sell MOEX at fill time
            exit_spread = exit_b3 - exit_moex
            exit_zscore = fill_row["zscore_long"]
            pnl = (self.position.entry_b3_price - exit_b3) - (self.position.entry_moex_price - exit_moex)

        pnl *= self.position_size

        # Commission for entry and exit (4 contracts total)
        commission = self._calculate_commission() * 2

        trade = Trade(
            entry_time=self.position.entry_time,
            exit_time=fill_row["ts"],
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
            exit_fill_time_ms=fill_time_ms,
        )

        self.trades.append(trade)
        self.position = Position()

        return trade

    def run(self, df: pd.DataFrame) -> BacktestResult:
        """
        Run backtest with limit orders on B3.

        Flow:
        1. Z-score crosses threshold → signal
        2. Calculate limit price for B3 (mid-price)
        3. Scan forward for fill within timeout
        4. If filled: MOEX executes at market at B3 fill time
        5. If not filled: cancel, wait for next signal
        """
        self.position = Position()
        self.trades = []
        self.equity = [0.0]
        self.limit_attempts = 0
        self.limit_fills = 0
        self.fill_times_ms = []

        cumulative_pnl = 0.0
        skip_until_idx = 0  # Skip ticks while waiting for fill

        df_list = df.reset_index(drop=True)

        for idx in range(len(df_list)):
            row = df_list.iloc[idx]

            # Skip if we're inside a fill scan window
            if idx < skip_until_idx:
                self.equity.append(cumulative_pnl)
                continue

            # Skip rows with NaN zscore
            if pd.isna(row["zscore_long"]) or pd.isna(row["zscore_short"]):
                self.equity.append(cumulative_pnl)
                continue

            zscore_long = row["zscore_long"]
            zscore_short = row["zscore_short"]
            has_liquidity = self._check_liquidity(row)

            # --- ENTRY ---
            if self.position.is_flat() and has_liquidity and self._check_b3_spread(row):
                if zscore_long < -self.entry_threshold:
                    # LONG spread: buy B3 (limit), sell MOEX (market at fill time)
                    limit_price = self._calculate_limit_price(
                        row["bid_b3"], row["ask_b3"], is_buy=True
                    )
                    self.limit_attempts += 1

                    fill = self._find_limit_fill(
                        df_list, idx, row["ts"], limit_price, is_buy=True
                    )
                    if fill:
                        fill_price, fill_idx, fill_row, fill_time_ms = fill
                        self._open_position(fill_row, PositionType.LONG_SPREAD, fill_price)
                        self.limit_fills += 1
                        self.fill_times_ms.append(fill_time_ms)
                        skip_until_idx = fill_idx + 1

                elif zscore_short > self.entry_threshold:
                    # SHORT spread: sell B3 (limit), buy MOEX (market at fill time)
                    limit_price = self._calculate_limit_price(
                        row["bid_b3"], row["ask_b3"], is_buy=False
                    )
                    self.limit_attempts += 1

                    fill = self._find_limit_fill(
                        df_list, idx, row["ts"], limit_price, is_buy=False
                    )
                    if fill:
                        fill_price, fill_idx, fill_row, fill_time_ms = fill
                        self._open_position(fill_row, PositionType.SHORT_SPREAD, fill_price)
                        self.limit_fills += 1
                        self.fill_times_ms.append(fill_time_ms)
                        skip_until_idx = fill_idx + 1

            # --- EXIT ---
            elif not self.position.is_flat():
                should_exit = False

                if self.position.type == PositionType.LONG_SPREAD:
                    if zscore_short > self.stop_loss_threshold:
                        should_exit = True
                    elif zscore_long > -self.exit_threshold:
                        should_exit = True
                else:  # SHORT_SPREAD
                    if zscore_long < -self.stop_loss_threshold:
                        should_exit = True
                    elif zscore_short < self.exit_threshold:
                        should_exit = True

                if should_exit and has_liquidity:
                    # Exit: B3 limit order
                    is_buy_b3 = self.position.type == PositionType.SHORT_SPREAD
                    limit_price = self._calculate_limit_price(
                        row["bid_b3"], row["ask_b3"], is_buy=is_buy_b3
                    )
                    self.limit_attempts += 1

                    fill = self._find_limit_fill(
                        df_list, idx, row["ts"], limit_price, is_buy=is_buy_b3
                    )
                    if fill:
                        fill_price, fill_idx, fill_row, fill_time_ms = fill
                        trade = self._close_position(fill_row, fill_price, fill_time_ms)
                        cumulative_pnl += trade.net_pnl
                        self.limit_fills += 1
                        self.fill_times_ms.append(fill_time_ms)
                        skip_until_idx = fill_idx + 1

            self.equity.append(cumulative_pnl)

        # Force close any open position at end of data
        if not self.position.is_flat():
            last_row = df.iloc[-1]
            if self.position.type == PositionType.LONG_SPREAD:
                forced_b3_price = last_row["bid_b3"]
            else:
                forced_b3_price = last_row["ask_b3"]
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

        winning_trades = [t for t in self.trades if t.net_pnl > 0]
        win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0

        avg_trade_pnl = net_pnl / num_trades if num_trades > 0 else 0

        rolling_max = equity_series.cummax()
        drawdown = equity_series - rolling_max
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0

        if num_trades > 1:
            trade_returns = [t.net_pnl for t in self.trades]
            sharpe_ratio = (
                np.mean(trade_returns) / np.std(trade_returns) * np.sqrt(252)
                if np.std(trade_returns) > 0
                else 0
            )
        else:
            sharpe_ratio = 0

        gross_profit = sum(t.net_pnl for t in self.trades if t.net_pnl > 0)
        gross_loss = abs(sum(t.net_pnl for t in self.trades if t.net_pnl < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        num_periods = len(df)
        annualized_return = net_pnl * (252 / num_periods) if num_periods > 0 else 0
        calmar_ratio = annualized_return / max_drawdown if max_drawdown > 0 else 0

        if num_trades > 0:
            trade_pnls = [t.net_pnl for t in self.trades]
            var_95 = np.percentile(trade_pnls, 5)
        else:
            var_95 = 0

        total_margin = self.margin_per_trade * self.position_size
        roi_on_margin = (net_pnl / total_margin * 100) if total_margin > 0 else 0

        fill_rate = self.limit_fills / self.limit_attempts if self.limit_attempts > 0 else 0
        avg_fill_time = np.mean(self.fill_times_ms) if self.fill_times_ms else 0

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
            limit_orders_attempted=self.limit_attempts,
            limit_orders_filled=self.limit_fills,
            limit_fill_rate=fill_rate,
            avg_fill_time_ms=avg_fill_time,
        )
