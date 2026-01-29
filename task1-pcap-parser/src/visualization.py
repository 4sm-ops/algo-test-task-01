#!/usr/bin/env python3
"""
WDO Futures Visualization.

Creates interactive charts for WDO price data.
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_wdo_chart(csv_path: str, output_path: str):
    """
    Create interactive chart for WDO futures prices.

    Since WDOF25 has insufficient data for calendar spread calculation,
    this chart shows WDOZ24 price movement and notes the data limitation.
    """
    df = pd.read_csv(csv_path)
    df['datetime'] = pd.to_datetime(df['timestamp_s'], unit='s')
    df = df.sort_values('timestamp_ns')

    # Get WDOZ24 data (front month with most data)
    wdoz24 = df[df['symbol'] == 'WDOZ24'].copy()
    wdof25 = df[df['symbol'] == 'WDOF25'].copy()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.15,
        subplot_titles=(
            'WDO Futures: WDOZ24 (December 2024)',
            'Price Change from Start'
        ),
        row_heights=[0.6, 0.4]
    )

    # Panel 1: WDOZ24 price
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

    # Add WDOF25 point if available
    if len(wdof25) > 0:
        fig.add_trace(
            go.Scatter(
                x=wdof25['datetime'],
                y=wdof25['price'],
                name='WDOF25 (sparse)',
                mode='markers',
                marker=dict(color='#FF9800', size=10, symbol='diamond'),
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
            text='<b>WDO Mini Dollar Futures - B3 Exchange</b><br>' +
                 '<sup>Data from PCAP file (18 Nov 2024)</sup>',
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
                text='<b>Note:</b> Calendar spread unavailable - WDOF25 data too sparse',
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

    # Save
    fig.write_html(output_path)
    print(f"Chart saved to: {output_path}")

    # Statistics
    print("\n" + "=" * 60)
    print("WDO Data Summary")
    print("=" * 60)
    print(f"\nWDOZ24 (December 2024):")
    print(f"  Records: {len(wdoz24):,}")
    print(f"  Price range: {wdoz24['price'].min():.2f} - {wdoz24['price'].max():.2f}")
    print(f"  Start: {wdoz24['datetime'].iloc[0]}")
    print(f"  End: {wdoz24['datetime'].iloc[-1]}")

    if len(wdof25) > 0:
        print(f"\nWDOF25 (January 2025):")
        print(f"  Records: {len(wdof25)}")
        print(f"  Price: {wdof25['price'].iloc[0]:.2f}")

    print("\n" + "=" * 60)
    print("Calendar Spread Note")
    print("=" * 60)
    print("""
Calendar spread calculation requires synchronized price data
for both front-month (WDOZ24) and back-month (WDOF25) contracts.

In this dataset:
- WDOZ24: 8,522 price points (active trading)
- WDOF25: 1 price point only (insufficient for spread)

This is typical for futures markets where:
1. Front-month contracts are much more liquid
2. Deferred contracts may have minimal activity
3. Data capture timing affects available quotes

For a proper calendar spread analysis, data should be captured
during active trading hours when both contracts are quoted.
""")


def create_calendar_spread_demo(output_path: str):
    """
    Create a demonstration chart showing what calendar spread looks like.

    Uses synthetic data to illustrate the concept.
    """
    import numpy as np

    # Generate synthetic data for demonstration
    np.random.seed(42)
    n_points = 1000

    # Base time series
    t = np.arange(n_points)
    time = pd.date_range(start='2024-11-18 10:00', periods=n_points, freq='s')

    # Front month (WDOZ24) - more volatile
    base_price = 5900
    front_noise = np.cumsum(np.random.randn(n_points) * 2)
    front_price = base_price + front_noise

    # Back month (WDOF25) - follows front with slight lag
    back_price = front_price + 15 + np.random.randn(n_points) * 0.5  # Slight contango

    # Spread
    spread = front_price - back_price

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=(
            'Contract Prices: WDOZ24 vs WDOF25',
            'Calendar Spread: WDOZ24 - WDOF25'
        ),
        row_heights=[0.5, 0.5]
    )

    # Prices
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

    # Spread
    colors = ['green' if s >= 0 else 'red' for s in spread]
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
                 '<sup>Synthetic data for illustration purposes</sup>',
            x=0.5
        ),
        height=700,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        annotations=[
            dict(
                text='<i>This is synthetic data demonstrating calendar spread concept</i>',
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
    print(f"Demo chart saved to: {output_path}")


if __name__ == '__main__':
    output_dir = Path('/Users/rustamabdullin/personal/algo-test-task-01/task1-pcap-parser/output')
    prices_file = output_dir / 'wdo_prices_incr.csv'

    # Create main chart with real data
    if prices_file.exists():
        create_wdo_chart(str(prices_file), str(output_dir / 'wdo_prices.html'))

    # Create demo chart showing calendar spread concept
    create_calendar_spread_demo(str(output_dir / 'wdo_spread_demo.html'))
