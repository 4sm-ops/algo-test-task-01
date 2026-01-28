#!/usr/bin/env python3
"""
Gold Arbitrage Strategy: B3 (GLDG26) vs MOEX (GOLD-3.26)

Main script for running backtest and generating reports.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from config import StrategyConfig, DataConfig, DEFAULT_STRATEGY_CONFIG, DEFAULT_DATA_CONFIG
from src.data_loader import load_quotes, prepare_synchronized_data, get_data_summary
from src.indicators import add_indicators
from src.backtest import Backtest, BacktestResult, PositionType
from src.visualization import plot_equity_plotly, plot_strategy_dashboard


def print_section(title: str) -> None:
    """Print section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_data_summary(summary: dict) -> None:
    """Print data summary statistics."""
    print_section("DATA SUMMARY")
    print(f"Total rows:        {summary['total_rows']:,}")
    print(f"Date range:        {summary['date_range'][0]} to {summary['date_range'][1]}")
    print(f"B3 price range:    {summary['b3_price_range'][0]:.2f} - {summary['b3_price_range'][1]:.2f}")
    print(f"MOEX price range:  {summary['moex_price_range'][0]:.2f} - {summary['moex_price_range'][1]:.2f}")
    print(f"B3 avg spread:     {summary['b3_avg_spread']:.2f}")
    print(f"MOEX avg spread:   {summary['moex_avg_spread']:.2f}")


def print_backtest_results(result: BacktestResult) -> None:
    """Print backtest results."""
    print_section("BACKTEST RESULTS")
    print(f"Number of trades:  {result.num_trades}")
    print(f"Win rate:          {result.win_rate:.1%}")
    print(f"Total PnL:         {result.total_pnl:.2f}")
    print(f"Total commission:  {result.total_commission:.2f}")
    print(f"Net PnL:           {result.net_pnl:.2f}")
    print(f"Avg trade PnL:     {result.avg_trade_pnl:.2f}")
    print(f"Max drawdown:      {result.max_drawdown:.2f}")
    print(f"Sharpe ratio:      {result.sharpe_ratio:.2f}")
    print(f"Profit factor:     {result.profit_factor:.2f}")


def print_trade_list(trades: list, max_trades: int = 20) -> None:
    """Print list of trades."""
    print_section(f"TRADES (showing first {min(len(trades), max_trades)})")

    if not trades:
        print("No trades executed.")
        return

    print(f"{'#':<4} {'Entry Time':<20} {'Type':<12} {'Entry Z':<8} {'Exit Z':<8} {'PnL':<10} {'Net PnL':<10}")
    print("-" * 80)

    for i, trade in enumerate(trades[:max_trades]):
        pos_type = "LONG" if trade.position_type == PositionType.LONG_SPREAD else "SHORT"
        entry_time = trade.entry_time.strftime("%Y-%m-%d %H:%M")
        exit_z = f"{trade.exit_zscore:.2f}" if trade.exit_zscore else "N/A"
        print(
            f"{i+1:<4} {entry_time:<20} {pos_type:<12} "
            f"{trade.entry_zscore:<8.2f} {exit_z:<8} "
            f"{trade.pnl:<10.2f} {trade.net_pnl:<10.2f}"
        )

    if len(trades) > max_trades:
        print(f"... and {len(trades) - max_trades} more trades")


def plot_results(
    df: pd.DataFrame,
    result: BacktestResult,
    config: StrategyConfig,
    output_dir: Path,
) -> None:
    """Generate and save plots."""
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

    # Subsample for plotting if too many points
    plot_df = df.copy()
    if len(plot_df) > 10000:
        step = len(plot_df) // 10000
        plot_df = plot_df.iloc[::step]

    # 1. Mid prices
    ax1 = axes[0]
    ax1.plot(plot_df["ts"], plot_df["mid_b3"], label="B3 (GLDG26)", alpha=0.8)
    ax1.plot(plot_df["ts"], plot_df["mid_moex"], label="MOEX (GOLD-3.26)", alpha=0.8)
    ax1.set_ylabel("Price")
    ax1.set_title("Gold Futures Mid Prices")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 2. Spread
    ax2 = axes[1]
    ax2.plot(plot_df["ts"], plot_df["spread"], color="purple", alpha=0.8)
    ax2.axhline(y=0, color="black", linestyle="--", alpha=0.5)
    ax2.set_ylabel("Spread (B3 - MOEX)")
    ax2.set_title("Price Spread")
    ax2.grid(True, alpha=0.3)

    # 3. Z-score with entry/exit thresholds
    ax3 = axes[2]
    ax3.plot(plot_df["ts"], plot_df["zscore"], color="blue", alpha=0.8)
    ax3.axhline(y=config.entry_threshold, color="red", linestyle="--", label=f"Entry ({config.entry_threshold})")
    ax3.axhline(y=-config.entry_threshold, color="red", linestyle="--")
    ax3.axhline(y=config.exit_threshold, color="green", linestyle=":", label=f"Exit ({config.exit_threshold})")
    ax3.axhline(y=-config.exit_threshold, color="green", linestyle=":")
    ax3.axhline(y=0, color="black", linestyle="-", alpha=0.3)
    ax3.set_ylabel("Z-score")
    ax3.set_title("Spread Z-score")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. Equity curve
    ax4 = axes[3]
    equity_index = pd.date_range(
        start=df["ts"].iloc[0],
        periods=len(result.equity_curve),
        freq="s",
    )[:len(result.equity_curve)]
    ax4.plot(range(len(result.equity_curve)), result.equity_curve.values, color="green")
    ax4.fill_between(
        range(len(result.equity_curve)),
        0,
        result.equity_curve.values,
        alpha=0.3,
        color="green",
    )
    ax4.set_ylabel("Cumulative PnL")
    ax4.set_title("Equity Curve")
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save plot
    output_path = output_dir / "backtest_results.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved to: {output_path}")

    plt.close()


def save_trades_csv(trades: list, output_dir: Path) -> None:
    """Save trades to CSV file."""
    if not trades:
        return

    records = []
    for trade in trades:
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
        })

    df = pd.DataFrame(records)
    output_path = output_dir / "trades.csv"
    df.to_csv(output_path, index=False)
    print(f"Trades saved to: {output_path}")


def save_summary_report(
    summary: dict,
    result: BacktestResult,
    config: StrategyConfig,
    output_dir: Path,
) -> None:
    """Save summary report to markdown file."""
    output_path = output_dir / "backtest_report.md"

    with open(output_path, "w") as f:
        f.write("# Gold Arbitrage Backtest Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Strategy Parameters\n\n")
        f.write(f"- Entry threshold: {config.entry_threshold} σ\n")
        f.write(f"- Exit threshold: {config.exit_threshold} σ\n")
        f.write(f"- Stop loss: {config.stop_loss_threshold} σ\n")
        f.write(f"- Z-score window: {config.zscore_window} ticks\n")
        f.write(f"- Commission: {config.commission_pct:.4%}\n\n")

        f.write("## Data Summary\n\n")
        f.write(f"- Total rows: {summary['total_rows']:,}\n")
        f.write(f"- Date range: {summary['date_range'][0]} to {summary['date_range'][1]}\n")
        f.write(f"- B3 avg spread: {summary['b3_avg_spread']:.2f}\n")
        f.write(f"- MOEX avg spread: {summary['moex_avg_spread']:.2f}\n\n")

        f.write("## Results\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Number of trades | {result.num_trades} |\n")
        f.write(f"| Win rate | {result.win_rate:.1%} |\n")
        f.write(f"| Total PnL | {result.total_pnl:.2f} |\n")
        f.write(f"| Total commission | {result.total_commission:.2f} |\n")
        f.write(f"| Net PnL | {result.net_pnl:.2f} |\n")
        f.write(f"| Avg trade PnL | {result.avg_trade_pnl:.2f} |\n")
        f.write(f"| Max drawdown | {result.max_drawdown:.2f} |\n")
        f.write(f"| Sharpe ratio | {result.sharpe_ratio:.2f} |\n")
        f.write(f"| Profit factor | {result.profit_factor:.2f} |\n\n")

        f.write("## Charts\n\n")
        f.write("![Backtest Results](backtest_results.png)\n")

    print(f"Report saved to: {output_path}")


def main():
    """Main entry point."""
    print_section("GOLD ARBITRAGE STRATEGY BACKTEST")
    print(f"B3 Symbol:   {DEFAULT_STRATEGY_CONFIG.symbol_b3}")
    print(f"MOEX Symbol: {DEFAULT_STRATEGY_CONFIG.symbol_moex}")

    # Setup paths
    base_dir = Path(__file__).parent
    data_path = base_dir.parent / DEFAULT_DATA_CONFIG.csv_path
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # Check if data file exists
    if not data_path.exists():
        print(f"\nError: Data file not found: {data_path}")
        print("Please ensure the CSV file is in the project root directory.")
        sys.exit(1)

    # Load data
    print_section("LOADING DATA")
    print(f"Loading: {data_path}")

    df_raw = load_quotes(data_path)
    print(f"Loaded {len(df_raw):,} rows (after dedup and filtering)")

    # Prepare synchronized data
    print("Synchronizing data...")
    df = prepare_synchronized_data(
        df_raw,
        symbol_b3=DEFAULT_STRATEGY_CONFIG.symbol_b3,
        symbol_moex=DEFAULT_STRATEGY_CONFIG.symbol_moex,
    )
    print(f"Synchronized data: {len(df):,} rows")

    # Get data summary
    summary = get_data_summary(df)
    print_data_summary(summary)

    # Add indicators
    print_section("CALCULATING INDICATORS")
    df = add_indicators(df, window=DEFAULT_STRATEGY_CONFIG.zscore_window)
    valid_rows = df["zscore"].notna().sum()
    print(f"Z-score window: {DEFAULT_STRATEGY_CONFIG.zscore_window}")
    print(f"Valid rows with indicators: {valid_rows:,}")

    # Run backtest
    print_section("RUNNING BACKTEST")
    backtest = Backtest(
        entry_threshold=DEFAULT_STRATEGY_CONFIG.entry_threshold,
        exit_threshold=DEFAULT_STRATEGY_CONFIG.exit_threshold,
        stop_loss_threshold=DEFAULT_STRATEGY_CONFIG.stop_loss_threshold,
        commission_pct=DEFAULT_STRATEGY_CONFIG.commission_pct,
        position_size=DEFAULT_STRATEGY_CONFIG.position_size,
        min_liquidity=DEFAULT_STRATEGY_CONFIG.min_liquidity,
    )

    result = backtest.run(df)

    # Print results
    print_backtest_results(result)
    print_trade_list(result.trades)

    # Generate outputs
    print_section("GENERATING OUTPUTS")
    plot_results(df, result, DEFAULT_STRATEGY_CONFIG, output_dir)
    save_trades_csv(result.trades, output_dir)
    save_summary_report(summary, result, DEFAULT_STRATEGY_CONFIG, output_dir)

    # Generate interactive Plotly charts
    result_metrics = {
        "net_pnl": result.net_pnl,
        "num_trades": result.num_trades,
        "win_rate": result.win_rate,
        "sharpe_ratio": result.sharpe_ratio,
        "max_drawdown": result.max_drawdown,
        "profit_factor": result.profit_factor,
    }

    plot_equity_plotly(
        df=df,
        equity_curve=result.equity_curve,
        config=DEFAULT_STRATEGY_CONFIG,
        result_metrics=result_metrics,
        output_path=output_dir / "equity_interactive.html",
    )
    print(f"Interactive equity chart saved to: {output_dir / 'equity_interactive.html'}")

    plot_strategy_dashboard(
        df=df,
        equity_curve=result.equity_curve,
        config=DEFAULT_STRATEGY_CONFIG,
        result_metrics=result_metrics,
        output_path=output_dir / "strategy_dashboard.html",
    )
    print(f"Strategy dashboard saved to: {output_dir / 'strategy_dashboard.html'}")

    print_section("DONE")
    print(f"All outputs saved to: {output_dir}")


if __name__ == "__main__":
    main()
