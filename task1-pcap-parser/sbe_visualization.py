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
    Create a demonstration chart showing 4 types of calendar spread.

    Uses synthetic data to illustrate the concept since WDOF25 has insufficient data.

    Spread types (as specified by task author):
    - Ask-Ask: front_ask - back_ask
    - Bid-Bid: front_bid - back_bid
    - Ask-Bid: front_ask - back_bid
    - Bid-Ask: front_bid - back_ask
    """
    print(f"\nCreating calendar spread demo (4 spread types)...")

    np.random.seed(42)
    n_points = 1000

    # Generate synthetic data
    time = pd.date_range(start='2024-11-18 10:00', periods=n_points, freq='s')

    # Front month (WDOZ24) - more volatile
    base_price = 5900
    front_noise = np.cumsum(np.random.randn(n_points) * 2)
    front_mid = base_price + front_noise
    front_spread_half = 0.5 + np.abs(np.random.randn(n_points) * 0.2)
    front_bid = front_mid - front_spread_half
    front_ask = front_mid + front_spread_half

    # Back month (WDOF25) - follows front with slight lag and contango
    back_mid = front_mid + 15 + np.random.randn(n_points) * 0.5
    back_spread_half = 0.7 + np.abs(np.random.randn(n_points) * 0.3)
    back_bid = back_mid - back_spread_half
    back_ask = back_mid + back_spread_half

    # Calculate 4 spread types
    spread_ask_ask = front_ask - back_ask  # Ask-Ask
    spread_bid_bid = front_bid - back_bid  # Bid-Bid
    spread_ask_bid = front_ask - back_bid  # Ask-Bid (worst for buyer)
    spread_bid_ask = front_bid - back_ask  # Bid-Ask (worst for seller)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            'Contract Prices: WDOZ24 vs WDOF25 (Synthetic Demo)',
            'Calendar Spreads: 4 Types',
            'Spread Comparison'
        ),
        row_heights=[0.35, 0.4, 0.25]
    )

    # Panel 1: Contract prices (bid/ask for both)
    fig.add_trace(
        go.Scatter(x=time, y=front_ask, name='WDOZ24 Ask',
                   line=dict(color='#2196F3', width=1, dash='dot')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=front_bid, name='WDOZ24 Bid',
                   line=dict(color='#2196F3', width=1.5)),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=back_ask, name='WDOF25 Ask',
                   line=dict(color='#FF9800', width=1, dash='dot')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=back_bid, name='WDOF25 Bid',
                   line=dict(color='#FF9800', width=1.5)),
        row=1, col=1
    )

    # Panel 2: All 4 spread types
    fig.add_trace(
        go.Scatter(x=time, y=spread_ask_ask, name='Ask-Ask',
                   line=dict(color='#E91E63', width=1.5)),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=spread_bid_bid, name='Bid-Bid',
                   line=dict(color='#9C27B0', width=1.5)),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=spread_ask_bid, name='Ask-Bid',
                   line=dict(color='#00BCD4', width=1.5)),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=spread_bid_ask, name='Bid-Ask',
                   line=dict(color='#4CAF50', width=1.5)),
        row=2, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # Panel 3: Spread range (min/max of all spreads)
    spread_max = np.maximum.reduce([spread_ask_ask, spread_bid_bid, spread_ask_bid, spread_bid_ask])
    spread_min = np.minimum.reduce([spread_ask_ask, spread_bid_bid, spread_ask_bid, spread_bid_ask])
    spread_mid = (spread_ask_ask + spread_bid_bid) / 2

    fig.add_trace(
        go.Scatter(x=time, y=spread_max, name='Spread Max',
                   line=dict(color='rgba(76, 175, 80, 0.5)', width=1),
                   showlegend=False),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=spread_min, name='Spread Min',
                   line=dict(color='rgba(76, 175, 80, 0.5)', width=1),
                   fill='tonexty',
                   fillcolor='rgba(76, 175, 80, 0.2)',
                   showlegend=False),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=spread_mid, name='Mid Spread',
                   line=dict(color='#4CAF50', width=2)),
        row=3, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)

    fig.update_layout(
        title=dict(
            text='<b>WDO Calendar Spread — 4 Types (Synthetic Demo)</b><br>' +
                 '<sup>Ask-Ask, Bid-Bid, Ask-Bid, Bid-Ask as specified by task author</sup>',
            x=0.5
        ),
        height=900,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        annotations=[
            dict(
                text='<i>Synthetic data for demonstration. ' +
                     'Spread types: Ask-Ask (front_ask - back_ask), Bid-Bid (front_bid - back_bid), ' +
                     'Ask-Bid (front_ask - back_bid), Bid-Ask (front_bid - back_ask)</i>',
                xref='paper', yref='paper',
                x=0.5, y=-0.06,
                showarrow=False,
                font=dict(size=10, color='gray')
            )
        ]
    )

    fig.update_yaxes(title_text="Price (BRL)", row=1, col=1)
    fig.update_yaxes(title_text="Spread (points)", row=2, col=1)
    fig.update_yaxes(title_text="Range", row=3, col=1)

    fig.write_html(output_path)
    print(f"  Demo chart saved: {output_path}")

    print(f"\n  Spread Statistics (synthetic):")
    print(f"    Ask-Ask: mean={np.mean(spread_ask_ask):.2f}, std={np.std(spread_ask_ask):.2f}")
    print(f"    Bid-Bid: mean={np.mean(spread_bid_bid):.2f}, std={np.std(spread_bid_bid):.2f}")
    print(f"    Ask-Bid: mean={np.mean(spread_ask_bid):.2f}, std={np.std(spread_ask_bid):.2f}")
    print(f"    Bid-Ask: mean={np.mean(spread_bid_ask):.2f}, std={np.std(spread_bid_ask):.2f}")


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
