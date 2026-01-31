#!/usr/bin/env python3
"""
Task 2: Volatility & Momentum Algorithm

Main entry point for calculating and visualizing volatility and momentum
indicators for gold futures (GLDG26 on B3, GOLD-3.26 on MOEX).

Context: Trading robot with 400ms latency from market data to order placement.
Volatility and momentum are used for order decisions.

Usage:
    python main.py
"""
from pathlib import Path

from config import (
    DataConfig,
    IndicatorConfig,
    DEFAULT_DATA_CONFIG,
    DEFAULT_INDICATOR_CONFIG,
)
from src.data_loader import load_quotes, prepare_data, get_data_summary
from src.volatility import add_volatility_indicators, get_volatility_summary
from src.momentum import add_momentum_indicators, get_momentum_summary
from src.visualization import plot_indicators_dashboard, plot_comparison_dashboard


def print_section(title: str) -> None:
    """Print formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_summary(summary: dict, title: str) -> None:
    """Print summary dictionary."""
    print(f"\n{title}:")
    for key, value in summary.items():
        if isinstance(value, float):
            if abs(value) < 0.001:
                print(f"  {key}: {value:.6f}")
            else:
                print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")


def save_summary_report(
    data_summary_b3: dict,
    data_summary_moex: dict,
    vol_summary_b3: dict,
    vol_summary_moex: dict,
    mom_summary_b3: dict,
    mom_summary_moex: dict,
    config: IndicatorConfig,
    output_path: Path,
) -> None:
    """Save summary report to markdown file."""
    windows = [config.vol_window_short, config.vol_window_medium, config.vol_window_long]

    with open(output_path, "w") as f:
        f.write("# Volatility & Momentum Analysis Report\n\n")

        f.write("## Configuration\n\n")
        f.write(f"- **Windows (ticks):** {windows[0]} / {windows[1]} / {windows[2]}\n")
        f.write(f"- **EWMA decay (λ):** {config.ewma_lambda}\n")
        f.write(f"- **Data source:** Gold futures (B3 + MOEX)\n\n")

        f.write("## Data Summary\n\n")
        f.write("| Metric | B3 (GLDG26) | MOEX (GOLD-3.26) |\n")
        f.write("|--------|-------------|------------------|\n")
        f.write(f"| Rows | {data_summary_b3['total_rows']:,} | {data_summary_moex['total_rows']:,} |\n")
        f.write(f"| Price Range | {data_summary_b3['price_range'][0]:.2f} - {data_summary_b3['price_range'][1]:.2f} | {data_summary_moex['price_range'][0]:.2f} - {data_summary_moex['price_range'][1]:.2f} |\n")
        f.write(f"| Avg Spread | {data_summary_b3['avg_spread']:.2f} | {data_summary_moex['avg_spread']:.2f} |\n")
        f.write(f"| Return Std | {data_summary_b3['return_std']:.6f} | {data_summary_moex['return_std']:.6f} |\n\n")

        f.write("## Volatility Summary\n\n")
        f.write(f"### Realized Volatility (window={windows[1]})\n\n")
        f.write("| Metric | B3 | MOEX |\n")
        f.write("|--------|-----|------|\n")
        w = windows[1]
        f.write(f"| Mean | {vol_summary_b3.get(f'rv_{w}_mean', 0):.6f} | {vol_summary_moex.get(f'rv_{w}_mean', 0):.6f} |\n")
        f.write(f"| Median | {vol_summary_b3.get(f'rv_{w}_median', 0):.6f} | {vol_summary_moex.get(f'rv_{w}_median', 0):.6f} |\n")
        f.write(f"| Max | {vol_summary_b3.get(f'rv_{w}_max', 0):.6f} | {vol_summary_moex.get(f'rv_{w}_max', 0):.6f} |\n")
        f.write(f"| 95th percentile | {vol_summary_b3.get(f'rv_{w}_q95', 0):.6f} | {vol_summary_moex.get(f'rv_{w}_q95', 0):.6f} |\n\n")

        f.write("### EWMA Volatility\n\n")
        f.write("| Metric | B3 | MOEX |\n")
        f.write("|--------|-----|------|\n")
        f.write(f"| Mean | {vol_summary_b3.get('ewma_vol_mean', 0):.6f} | {vol_summary_moex.get('ewma_vol_mean', 0):.6f} |\n")
        f.write(f"| Median | {vol_summary_b3.get('ewma_vol_median', 0):.6f} | {vol_summary_moex.get('ewma_vol_median', 0):.6f} |\n")
        f.write(f"| Max | {vol_summary_b3.get('ewma_vol_max', 0):.6f} | {vol_summary_moex.get('ewma_vol_max', 0):.6f} |\n\n")

        f.write("## Momentum Summary\n\n")
        f.write(f"### ROC (window={windows[1]})\n\n")
        f.write("| Metric | B3 | MOEX |\n")
        f.write("|--------|-----|------|\n")
        f.write(f"| Mean | {mom_summary_b3.get(f'roc_{w}_mean', 0)*100:.4f}% | {mom_summary_moex.get(f'roc_{w}_mean', 0)*100:.4f}% |\n")
        f.write(f"| Std | {mom_summary_b3.get(f'roc_{w}_std', 0)*100:.4f}% | {mom_summary_moex.get(f'roc_{w}_std', 0)*100:.4f}% |\n")
        f.write(f"| % Positive | {mom_summary_b3.get(f'roc_{w}_positive_pct', 0)*100:.1f}% | {mom_summary_moex.get(f'roc_{w}_positive_pct', 0)*100:.1f}% |\n")
        f.write(f"| Autocorrelation | {mom_summary_b3.get(f'roc_{w}_autocorr', 0):.3f} | {mom_summary_moex.get(f'roc_{w}_autocorr', 0):.3f} |\n\n")

        f.write("## Output Files\n\n")
        f.write("| File | Description |\n")
        f.write("|------|-------------|\n")
        f.write("| `indicators_b3.html` | B3 indicators dashboard |\n")
        f.write("| `indicators_moex.html` | MOEX indicators dashboard |\n")
        f.write("| `comparison.html` | B3 vs MOEX comparison |\n")
        f.write("| `indicators_summary.md` | This report |\n\n")

        f.write("## Interpretation\n\n")
        f.write("### Volatility\n")
        f.write("- Higher volatility indicates larger price movements\n")
        f.write("- EWMA adapts faster to recent changes (useful for 400ms latency)\n")
        f.write("- Consider reducing position size when volatility is high\n\n")

        f.write("### Momentum\n")
        f.write("- Positive ROC = upward price movement\n")
        f.write("- Autocorrelation > 0 suggests momentum persistence (trend following)\n")
        f.write("- Autocorrelation < 0 suggests mean reversion\n")


def main():
    """Main entry point."""
    print_section("Task 2: Volatility & Momentum Algorithm")

    # Configuration
    data_config = DEFAULT_DATA_CONFIG
    indicator_config = DEFAULT_INDICATOR_CONFIG

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    windows = [
        indicator_config.vol_window_short,
        indicator_config.vol_window_medium,
        indicator_config.vol_window_long,
    ]

    print(f"Configuration:")
    print(f"  Data: {data_config.csv_path}")
    print(f"  Symbols: {data_config.symbol_b3}, {data_config.symbol_moex}")
    print(f"  Windows: {windows}")
    print(f"  EWMA λ: {indicator_config.ewma_lambda}")

    # Load data
    print_section("Loading Data")
    csv_path = Path(__file__).parent / data_config.csv_path
    df_raw = load_quotes(csv_path, data_config)
    print(f"Loaded {len(df_raw):,} rows")

    # Prepare data for each symbol
    print_section("Preparing Data")

    df_b3 = prepare_data(df_raw, data_config.symbol_b3, data_config)
    data_summary_b3 = get_data_summary(df_b3, data_config.symbol_b3)
    print_summary(data_summary_b3, f"B3 ({data_config.symbol_b3})")

    df_moex = prepare_data(df_raw, data_config.symbol_moex, data_config)
    data_summary_moex = get_data_summary(df_moex, data_config.symbol_moex)
    print_summary(data_summary_moex, f"MOEX ({data_config.symbol_moex})")

    # Calculate indicators for B3
    print_section("Calculating Indicators - B3")
    df_b3 = add_volatility_indicators(df_b3, windows, indicator_config.ewma_lambda)
    df_b3 = add_momentum_indicators(df_b3, windows)

    vol_summary_b3 = get_volatility_summary(df_b3, windows)
    mom_summary_b3 = get_momentum_summary(df_b3, windows)

    print_summary(vol_summary_b3, "Volatility Summary (B3)")
    print_summary(mom_summary_b3, "Momentum Summary (B3)")

    # Calculate indicators for MOEX
    print_section("Calculating Indicators - MOEX")
    df_moex = add_volatility_indicators(df_moex, windows, indicator_config.ewma_lambda)
    df_moex = add_momentum_indicators(df_moex, windows)

    vol_summary_moex = get_volatility_summary(df_moex, windows)
    mom_summary_moex = get_momentum_summary(df_moex, windows)

    print_summary(vol_summary_moex, "Volatility Summary (MOEX)")
    print_summary(mom_summary_moex, "Momentum Summary (MOEX)")

    # Generate visualizations
    print_section("Generating Visualizations")

    # B3 dashboard
    b3_output = output_dir / "indicators_b3.html"
    plot_indicators_dashboard(
        df_b3,
        indicator_config,
        data_config.symbol_b3,
        vol_summary_b3,
        mom_summary_b3,
        b3_output,
    )
    print(f"Created: {b3_output}")

    # MOEX dashboard
    moex_output = output_dir / "indicators_moex.html"
    plot_indicators_dashboard(
        df_moex,
        indicator_config,
        data_config.symbol_moex,
        vol_summary_moex,
        mom_summary_moex,
        moex_output,
    )
    print(f"Created: {moex_output}")

    # Comparison dashboard
    comparison_output = output_dir / "comparison.html"
    plot_comparison_dashboard(
        df_b3,
        df_moex,
        indicator_config,
        comparison_output,
    )
    print(f"Created: {comparison_output}")

    # Save summary report
    report_output = output_dir / "indicators_summary.md"
    save_summary_report(
        data_summary_b3,
        data_summary_moex,
        vol_summary_b3,
        vol_summary_moex,
        mom_summary_b3,
        mom_summary_moex,
        indicator_config,
        report_output,
    )
    print(f"Created: {report_output}")

    print_section("Complete")
    print("Output files are in the 'output/' directory.")
    print("\nOpen in browser:")
    print(f"  - {b3_output}")
    print(f"  - {moex_output}")
    print(f"  - {comparison_output}")


if __name__ == "__main__":
    main()
