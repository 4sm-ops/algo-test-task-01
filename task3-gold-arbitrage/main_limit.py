#!/usr/bin/env python3
"""
Gold Arbitrage Strategy: Limit Orders Comparison

Runs both market-order and limit-order backtests side by side,
then prints a comparison table.

Usage:
    python main_limit.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
from datetime import datetime

from config import DEFAULT_STRATEGY_CONFIG, DEFAULT_DATA_CONFIG
from src.data_loader import load_quotes, prepare_synchronized_data, get_data_summary
from src.indicators import add_indicators
from src.backtest import Backtest
from src.backtest_limit import BacktestLimit


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def main():
    config = DEFAULT_STRATEGY_CONFIG

    print_section("GOLD ARBITRAGE: MARKET vs LIMIT ORDERS")
    print(f"B3 Symbol:   {config.symbol_b3}")
    print(f"MOEX Symbol: {config.symbol_moex}")

    # Setup paths
    base_dir = Path(__file__).parent
    data_path = base_dir.parent / DEFAULT_DATA_CONFIG.csv_path
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    if not data_path.exists():
        print(f"\nError: Data file not found: {data_path}")
        sys.exit(1)

    # Load and prepare data (shared between both backtests)
    print_section("LOADING DATA")
    df_raw = load_quotes(data_path)
    print(f"Loaded {len(df_raw):,} rows")

    df = prepare_synchronized_data(
        df_raw,
        symbol_b3=config.symbol_b3,
        symbol_moex=config.symbol_moex,
    )
    print(f"Synchronized: {len(df):,} rows")

    summary = get_data_summary(df)
    print(f"B3 avg spread:   {summary['b3_avg_spread']:.2f} pts")
    print(f"MOEX avg spread: {summary['moex_avg_spread']:.2f} pts")

    df = add_indicators(df, window=config.zscore_window)

    # ==========================================
    # Backtest 1: MARKET ORDERS (original)
    # ==========================================
    print_section("BACKTEST 1: MARKET ORDERS")
    print(f"B3 execution: cross spread (ask/bid) after {config.b3_latency_ms}ms")

    bt_market = Backtest(
        entry_threshold=config.entry_threshold,
        exit_threshold=config.exit_threshold,
        stop_loss_threshold=config.stop_loss_threshold,
        commission_per_contract=config.commission_per_contract,
        position_size=config.position_size,
        min_liquidity=config.min_liquidity,
        b3_latency_ms=config.b3_latency_ms,
        margin_b3=config.margin_b3,
        margin_moex=config.margin_moex,
    )
    result_market = bt_market.run(df)

    print(f"Trades:     {result_market.num_trades}")
    print(f"Net PnL:    {result_market.net_pnl:.2f}")
    print(f"Avg PnL:    {result_market.avg_trade_pnl:.2f}")
    print(f"Win rate:   {result_market.win_rate:.1%}")
    print(f"Sharpe:     {result_market.sharpe_ratio:.2f}")

    # ==========================================
    # Backtest 2: LIMIT ORDERS on B3
    # ==========================================
    print_section("BACKTEST 2: LIMIT ORDERS ON B3")
    print(f"B3 execution: limit @ {config.limit_order_price_mode} (timeout {config.limit_order_timeout_ms}ms)")
    print(f"MOEX execution: market @ fill time")
    print(f"Max B3 spread: {config.max_b3_spread_for_entry} pts")

    bt_limit = BacktestLimit(
        entry_threshold=config.entry_threshold,
        exit_threshold=config.exit_threshold,
        stop_loss_threshold=config.stop_loss_threshold,
        commission_per_contract=config.commission_per_contract,
        position_size=config.position_size,
        min_liquidity=config.min_liquidity,
        b3_latency_ms=config.b3_latency_ms,
        margin_b3=config.margin_b3,
        margin_moex=config.margin_moex,
        limit_order_offset=config.limit_order_offset,
        limit_order_timeout_ms=config.limit_order_timeout_ms,
        limit_order_price_mode=config.limit_order_price_mode,
        max_b3_spread_for_entry=config.max_b3_spread_for_entry,
    )
    result_limit = bt_limit.run(df)

    print(f"Trades:     {result_limit.num_trades}")
    print(f"Net PnL:    {result_limit.net_pnl:.2f}")
    print(f"Avg PnL:    {result_limit.avg_trade_pnl:.2f}")
    print(f"Win rate:   {result_limit.win_rate:.1%}")
    print(f"Sharpe:     {result_limit.sharpe_ratio:.2f}")
    print(f"")
    print(f"Limit orders attempted: {result_limit.limit_orders_attempted}")
    print(f"Limit orders filled:    {result_limit.limit_orders_filled}")
    print(f"Fill rate:              {result_limit.limit_fill_rate:.1%}")
    if result_limit.avg_fill_time_ms > 0:
        print(f"Avg fill time:          {result_limit.avg_fill_time_ms:.0f} ms")

    # ==========================================
    # COMPARISON TABLE
    # ==========================================
    print_section("COMPARISON: MARKET vs LIMIT ORDERS")

    rows = [
        ("Trades", f"{result_market.num_trades}", f"{result_limit.num_trades}"),
        ("Net PnL", f"{result_market.net_pnl:.2f}", f"{result_limit.net_pnl:.2f}"),
        ("Avg PnL/trade", f"{result_market.avg_trade_pnl:.2f}", f"{result_limit.avg_trade_pnl:.2f}"),
        ("Win rate", f"{result_market.win_rate:.1%}", f"{result_limit.win_rate:.1%}"),
        ("Max drawdown", f"{result_market.max_drawdown:.2f}", f"{result_limit.max_drawdown:.2f}"),
        ("Sharpe", f"{result_market.sharpe_ratio:.2f}", f"{result_limit.sharpe_ratio:.2f}"),
        ("Profit factor", f"{result_market.profit_factor:.2f}", f"{result_limit.profit_factor:.2f}"),
        ("ROI on margin", f"{result_market.roi_on_margin:.1f}%", f"{result_limit.roi_on_margin:.1f}%"),
        ("Fill rate", "100% (market)", f"{result_limit.limit_fill_rate:.1%}"),
    ]

    print(f"{'Metric':<20} {'Market Orders':<20} {'Limit Orders':<20}")
    print("-" * 60)
    for metric, market_val, limit_val in rows:
        print(f"{metric:<20} {market_val:<20} {limit_val:<20}")

    # ==========================================
    # SAVE COMPARISON REPORT
    # ==========================================
    report_path = output_dir / "comparison_report.md"
    with open(report_path, "w") as f:
        f.write("# Market Orders vs Limit Orders: Comparison Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Parameters\n\n")
        f.write(f"- Entry threshold: {config.entry_threshold}σ\n")
        f.write(f"- Exit threshold: {config.exit_threshold}σ\n")
        f.write(f"- Stop loss: {config.stop_loss_threshold}σ\n")
        f.write(f"- Z-score window: {config.zscore_window} ticks\n")
        f.write(f"- B3 latency: {config.b3_latency_ms} ms\n")
        f.write(f"- Limit price mode: {config.limit_order_price_mode}\n")
        f.write(f"- Limit timeout: {config.limit_order_timeout_ms} ms\n")
        f.write(f"- Max B3 spread: {config.max_b3_spread_for_entry} pts\n\n")

        f.write("## Results\n\n")
        f.write(f"| Metric | Market Orders | Limit Orders |\n")
        f.write(f"|--------|--------------|-------------|\n")
        for metric, market_val, limit_val in rows:
            f.write(f"| {metric} | {market_val} | {limit_val} |\n")

        f.write("\n## Fill Model\n\n")
        f.write("**Price Touch model:** A limit BUY at price P fills when `ask_b3 ≤ P` ")
        f.write("after the latency delay, within the timeout window.\n\n")
        f.write("**Limitations:**\n")
        f.write("- Does NOT model queue position (optimistic)\n")
        f.write("- Does NOT account for adverse selection\n")
        f.write("- MOEX executes at market at B3 fill time (not signal time)\n")

        if result_limit.limit_orders_attempted > 0:
            f.write(f"\n## Limit Order Statistics\n\n")
            f.write(f"- Orders attempted: {result_limit.limit_orders_attempted}\n")
            f.write(f"- Orders filled: {result_limit.limit_orders_filled}\n")
            f.write(f"- Fill rate: {result_limit.limit_fill_rate:.1%}\n")
            if result_limit.avg_fill_time_ms > 0:
                f.write(f"- Avg fill time: {result_limit.avg_fill_time_ms:.0f} ms\n")

    print(f"\nComparison report saved to: {report_path}")

    # Save limit order trades
    if result_limit.trades:
        records = []
        for trade in result_limit.trades:
            records.append({
                "entry_time": trade.entry_time,
                "exit_time": trade.exit_time,
                "position_type": trade.position_type.name,
                "entry_zscore": trade.entry_zscore,
                "exit_zscore": trade.exit_zscore,
                "entry_spread": trade.entry_spread,
                "exit_spread": trade.exit_spread,
                "entry_b3_price": trade.entry_b3_price,
                "entry_moex_price": trade.entry_moex_price,
                "exit_b3_price": trade.exit_b3_price,
                "exit_moex_price": trade.exit_moex_price,
                "pnl": trade.pnl,
                "commission": trade.commission,
                "net_pnl": trade.net_pnl,
                "exit_fill_time_ms": trade.exit_fill_time_ms,
            })
        trades_df = pd.DataFrame(records)
        trades_path = output_dir / "trades_limit.csv"
        trades_df.to_csv(trades_path, index=False)
        print(f"Limit trades saved to: {trades_path}")

    print_section("DONE")


if __name__ == "__main__":
    main()
