#!/usr/bin/env python3
"""
WDO Futures Visualization (SBE-based data).

Creates interactive charts for WDO price data extracted via sbe-python.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


OUTPUT_DIR = Path(__file__).parent / 'output'


def create_wdo_chart_sbe(csv_path: str, output_path: str):
    """
    Create interactive chart for WDO futures prices.

    Shows WDOZ24 price movement with proper SBE-decoded data.
    """
    print(f"\nCreating WDO chart from: {csv_path}")

    df = pd.read_csv(csv_path)
    df['datetime'] = pd.to_datetime(df['timestamp_s'], unit='s')
    df = df.sort_values('timestamp_ns')

    # Get data by symbol
    wdoz24 = df[df['symbol'] == 'WDOZ24'].copy()
    wdof25 = df[df['symbol'] == 'WDOF25'].copy()

    print(f"  WDOZ24: {len(wdoz24)} points")
    print(f"  WDOF25: {len(wdof25)} points")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=(
            'WDO Futures: WDOZ24 (December 2024) - SBE Decoded',
            'Price Change from Start'
        ),
        row_heights=[0.6, 0.4]
    )

    # Panel 1: WDOZ24 price
    if len(wdoz24) > 0:
        fig.add_trace(
            go.Scatter(
                x=wdoz24['datetime'],
                y=wdoz24['price'],
                name='WDOZ24',
                line=dict(color='#2196F3', width=1),
                mode='lines',
                hovertemplate='Price: %{y:.2f}<br>Time: %{x}<extra></extra>'
            ),
            row=1, col=1
        )

    # Add WDOF25 points if available
    if len(wdof25) > 0:
        fig.add_trace(
            go.Scatter(
                x=wdof25['datetime'],
                y=wdof25['price'],
                name='WDOF25 (sparse)',
                mode='markers',
                marker=dict(color='#FF9800', size=12, symbol='diamond'),
                hovertemplate='WDOF25: %{y:.2f}<br>Time: %{x}<extra></extra>'
            ),
            row=1, col=1
        )

    # Panel 2: Price change
    if len(wdoz24) > 0:
        base_price = wdoz24['price'].iloc[0]
        wdoz24['change'] = wdoz24['price'] - base_price

        fig.add_trace(
            go.Scatter(
                x=wdoz24['datetime'],
                y=wdoz24['change'],
                name='Price Change',
                line=dict(color='#4CAF50', width=1),
                fill='tozeroy',
                fillcolor='rgba(76, 175, 80, 0.2)',
                mode='lines',
                hovertemplate='Change: %{y:+.2f}<extra></extra>'
            ),
            row=2, col=1
        )

        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # Layout
    fig.update_layout(
        title=dict(
            text='<b>WDO Mini Dollar Futures - B3 Exchange (SBE Decoded)</b><br>' +
                 '<sup>Data from PCAP file (18 Nov 2024) - Parsed with sbe-python</sup>',
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
        hovermode='x unified',
        annotations=[
            dict(
                text='<b>Note:</b> Calendar spread unavailable - WDOF25 data too sparse (1 point only)',
                xref='paper', yref='paper',
                x=0.5, y=-0.12,
                showarrow=False,
                font=dict(size=11, color='gray')
            )
        ]
    )

    fig.update_yaxes(title_text="Price (BRL)", row=1, col=1)
    fig.update_yaxes(title_text="Change (points)", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)

    fig.write_html(output_path)
    print(f"  Chart saved: {output_path}")

    # Statistics
    if len(wdoz24) > 0:
        print(f"\n  WDOZ24 Statistics:")
        print(f"    Records: {len(wdoz24):,}")
        print(f"    Price range: {wdoz24['price'].min():.2f} - {wdoz24['price'].max():.2f}")
        print(f"    Start: {wdoz24['datetime'].iloc[0]}")
        print(f"    End: {wdoz24['datetime'].iloc[-1]}")


def create_calendar_spread_demo_sbe(output_path: str):
    """
    Create a demonstration chart showing what calendar spread looks like.

    Uses synthetic data to illustrate the concept since WDOF25 has insufficient data.
    """
    print(f"\nCreating calendar spread demo...")

    np.random.seed(42)
    n_points = 1000

    # Generate synthetic data
    time = pd.date_range(start='2024-11-18 10:00', periods=n_points, freq='s')

    # Front month (WDOZ24) - more volatile
    base_price = 5900
    front_noise = np.cumsum(np.random.randn(n_points) * 2)
    front_price = base_price + front_noise

    # Back month (WDOF25) - follows front with slight lag and contango
    back_price = front_price + 15 + np.random.randn(n_points) * 0.5

    # Spread
    spread = front_price - back_price

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=(
            'Contract Prices: WDOZ24 vs WDOF25 (Synthetic Demo)',
            'Calendar Spread: WDOZ24 - WDOF25'
        ),
        row_heights=[0.5, 0.5]
    )

    # Panel 1: Contract prices
    fig.add_trace(
        go.Scatter(x=time, y=front_price, name='WDOZ24 (Front)',
                   line=dict(color='#2196F3', width=1.5)),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=back_price, name='WDOF25 (Back)',
                   line=dict(color='#FF9800', width=1.5)),
        row=1, col=1
    )

    # Panel 2: Spread
    fig.add_trace(
        go.Scatter(x=time, y=spread, name='Spread',
                   line=dict(color='#4CAF50', width=1.5),
                   fill='tozeroy',
                   fillcolor='rgba(76, 175, 80, 0.2)'),
        row=2, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # Mean spread line
    mean_spread = np.mean(spread)
    fig.add_hline(y=mean_spread, line_dash="dot", line_color="blue",
                  annotation_text=f"Mean: {mean_spread:.1f}", row=2, col=1)

    fig.update_layout(
        title=dict(
            text='<b>WDO Calendar Spread Demonstration</b><br>' +
                 '<sup>Synthetic data for illustration purposes (real WDOF25 data too sparse)</sup>',
            x=0.5
        ),
        height=700,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        annotations=[
            dict(
                text='<i>This is synthetic data demonstrating calendar spread concept. ' +
                     'Real spread requires synchronized quotes for both contracts.</i>',
                xref='paper', yref='paper',
                x=0.5, y=-0.1,
                showarrow=False,
                font=dict(size=10, color='gray')
            )
        ]
    )

    fig.update_yaxes(title_text="Price (BRL)", row=1, col=1)
    fig.update_yaxes(title_text="Spread (points)", row=2, col=1)

    fig.write_html(output_path)
    print(f"  Demo chart saved: {output_path}")

    print(f"\n  Spread Statistics (synthetic):")
    print(f"    Mean: {mean_spread:.2f}")
    print(f"    Std: {np.std(spread):.2f}")
    print(f"    Min: {np.min(spread):.2f}")
    print(f"    Max: {np.max(spread):.2f}")


def main():
    """Create all visualizations."""
    print("=" * 70)
    print("WDO Visualization (SBE-based)")
    print("=" * 70)

    prices_file = OUTPUT_DIR / 'wdo_prices_sbe.csv'

    if prices_file.exists():
        create_wdo_chart_sbe(
            str(prices_file),
            str(OUTPUT_DIR / 'wdo_prices_sbe.html')
        )

    create_calendar_spread_demo_sbe(
        str(OUTPUT_DIR / 'wdo_spread_sbe.html')
    )

    print("\n" + "=" * 70)
    print("Output files:")
    print("=" * 70)
    print(f"  {OUTPUT_DIR / 'wdo_prices_sbe.html'}")
    print(f"  {OUTPUT_DIR / 'wdo_spread_sbe.html'}")


if __name__ == '__main__':
    main()
