#!/usr/bin/env python3
"""
WDO Calendar Spread Analysis.

Calculates and visualizes the spread between WDO futures of different expiration months.
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def load_prices(csv_path: str) -> pd.DataFrame:
    """Load prices from CSV."""
    df = pd.read_csv(csv_path)
    df['timestamp_s'] = df['timestamp_ns'] / 1e9
    df['datetime'] = pd.to_datetime(df['timestamp_s'], unit='s')
    return df


def calculate_spread(df: pd.DataFrame, front_symbol: str, back_symbol: str) -> pd.DataFrame:
    """
    Calculate calendar spread between two contracts.

    Args:
        df: DataFrame with columns [timestamp_ns, symbol, price]
        front_symbol: Front month contract (e.g., 'WDOZ24')
        back_symbol: Back month contract (e.g., 'WDOF25')

    Returns:
        DataFrame with spread calculation
    """
    # Pivot to get prices side by side
    front = df[df['symbol'] == front_symbol][['timestamp_s', 'price']].copy()
    front = front.rename(columns={'price': 'front_price'})

    back = df[df['symbol'] == back_symbol][['timestamp_s', 'price']].copy()
    back = back.rename(columns={'price': 'back_price'})

    if len(front) == 0 or len(back) == 0:
        print(f"Warning: Missing data - {front_symbol}: {len(front)}, {back_symbol}: {len(back)}")
        return pd.DataFrame()

    # Merge on nearest timestamp (within 1 second tolerance)
    front = front.sort_values('timestamp_s').reset_index(drop=True)
    back = back.sort_values('timestamp_s').reset_index(drop=True)

    # Use merge_asof for time-based join
    merged = pd.merge_asof(
        front, back,
        on='timestamp_s',
        tolerance=1.0,  # 1 second tolerance
        direction='nearest'
    )

    merged = merged.dropna()

    if len(merged) == 0:
        print("Warning: No overlapping timestamps found")
        return pd.DataFrame()

    # Calculate spread (front - back)
    merged['spread'] = merged['front_price'] - merged['back_price']
    merged['datetime'] = pd.to_datetime(merged['timestamp_s'], unit='s')

    return merged


def plot_spread(spread_df: pd.DataFrame, front_symbol: str, back_symbol: str,
                output_path: str):
    """
    Create interactive spread visualization.

    Creates a 2-panel chart:
    - Top: Individual contract prices
    - Bottom: Calendar spread
    """
    if len(spread_df) == 0:
        print("No data to plot")
        return

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=(
            f'Contract Prices: {front_symbol} vs {back_symbol}',
            f'Calendar Spread: {front_symbol} - {back_symbol}'
        ),
        row_heights=[0.5, 0.5]
    )

    # Top panel: Contract prices
    fig.add_trace(
        go.Scatter(
            x=spread_df['datetime'],
            y=spread_df['front_price'],
            name=front_symbol,
            line=dict(color='blue', width=1),
            mode='lines'
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=spread_df['datetime'],
            y=spread_df['back_price'],
            name=back_symbol,
            line=dict(color='orange', width=1),
            mode='lines'
        ),
        row=1, col=1
    )

    # Bottom panel: Spread
    spread_color = 'green' if spread_df['spread'].iloc[-1] >= 0 else 'red'
    fig.add_trace(
        go.Scatter(
            x=spread_df['datetime'],
            y=spread_df['spread'],
            name='Spread',
            line=dict(color=spread_color, width=1.5),
            fill='tozeroy',
            fillcolor='rgba(0, 128, 0, 0.1)' if spread_df['spread'].iloc[-1] >= 0 else 'rgba(255, 0, 0, 0.1)',
            mode='lines'
        ),
        row=2, col=1
    )

    # Add zero line to spread panel
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # Layout
    fig.update_layout(
        title=dict(
            text=f'WDO Calendar Spread: {front_symbol} - {back_symbol}',
            x=0.5
        ),
        height=700,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        hovermode='x unified'
    )

    fig.update_yaxes(title_text="Price (BRL)", row=1, col=1)
    fig.update_yaxes(title_text="Spread (points)", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)

    # Save
    fig.write_html(output_path)
    print(f"Saved chart to: {output_path}")

    # Also show statistics
    print(f"\nSpread Statistics:")
    print(f"  Points: {len(spread_df)}")
    print(f"  Mean spread: {spread_df['spread'].mean():.2f}")
    print(f"  Std spread: {spread_df['spread'].std():.2f}")
    print(f"  Min spread: {spread_df['spread'].min():.2f}")
    print(f"  Max spread: {spread_df['spread'].max():.2f}")


def main():
    """Main analysis function."""
    output_dir = Path('/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/output')
    prices_file = output_dir / 'wdo_prices_incr.csv'

    if not prices_file.exists():
        print(f"Prices file not found: {prices_file}")
        print("Run extract_wdo_prices.py first")
        return

    print("Loading prices...")
    df = load_prices(str(prices_file))
    print(f"Loaded {len(df)} records")

    # Show available symbols
    print("\nAvailable symbols:")
    for symbol in df['symbol'].unique():
        count = len(df[df['symbol'] == symbol])
        print(f"  {symbol}: {count} records")

    # Calculate spread
    front_symbol = 'WDOZ24'
    back_symbol = 'WDOF25'

    print(f"\nCalculating spread: {front_symbol} - {back_symbol}")
    spread_df = calculate_spread(df, front_symbol, back_symbol)

    if len(spread_df) > 0:
        print(f"Found {len(spread_df)} spread points")

        # Plot
        plot_spread(
            spread_df,
            front_symbol,
            back_symbol,
            str(output_dir / 'wdo_spread.html')
        )
    else:
        print("Could not calculate spread - insufficient overlapping data")
        print("\nNote: Calendar spread requires synchronized prices for both contracts.")
        print("If data is sparse, try using snapshot data or a different contract pair.")


if __name__ == '__main__':
    main()
