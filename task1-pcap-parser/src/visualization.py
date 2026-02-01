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

    Supports both TOB format (best_bid/best_ask) and simple format (price).
    """
    df = pd.read_csv(csv_path)
    df['datetime'] = pd.to_datetime(df['timestamp_s'], unit='s')
    df = df.sort_values('timestamp_ns')

    # Get WDOZ24 data (front month with most data)
    wdoz24 = df[df['symbol'] == 'WDOZ24'].copy()
    wdof25 = df[df['symbol'] == 'WDOF25'].copy()

    # Determine price column (TOB format or simple)
    # Priority: mid_price > best_bid > best_ask > price
    if 'mid_price' in df.columns and df['mid_price'].notna().any():
        price_col = 'mid_price'
    elif 'best_bid' in df.columns:
        # Use mid_price if available, fallback to best_bid, then best_ask
        for data in [wdoz24, wdof25]:
            if 'mid_price' in data.columns:
                data['price'] = data['mid_price'].fillna(data['best_bid']).fillna(data.get('best_ask', pd.Series()))
            else:
                data['price'] = data['best_bid'].fillna(data.get('best_ask', pd.Series()))
        price_col = 'price'
    else:
        price_col = 'price'

    # Filter out rows with no valid price
    wdoz24 = wdoz24[wdoz24[price_col].notna()] if price_col in wdoz24.columns else wdoz24
    wdof25 = wdof25[wdof25[price_col].notna()] if price_col in wdof25.columns else wdof25

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
    if len(wdoz24) > 0 and price_col in wdoz24.columns:
        fig.add_trace(
            go.Scatter(
                x=wdoz24['datetime'],
                y=wdoz24[price_col],
                name='WDOZ24',
                line=dict(color='#2196F3', width=1),
                mode='lines',
                hovertemplate='Price: %{y:.2f}<br>Time: %{x}<extra></extra>'
            ),
            row=1, col=1
        )

    # Add WDOF25 point if available
    if len(wdof25) > 0 and price_col in wdof25.columns:
        fig.add_trace(
            go.Scatter(
                x=wdof25['datetime'],
                y=wdof25[price_col],
                name='WDOF25 (sparse)',
                mode='markers',
                marker=dict(color='#FF9800', size=10, symbol='diamond'),
                hovertemplate='WDOF25: %{y:.2f}<br>Time: %{x}<extra></extra>'
            ),
            row=1, col=1
        )

    # Panel 2: Price change
    if len(wdoz24) > 0 and price_col in wdoz24.columns:
        valid_prices = wdoz24[wdoz24[price_col].notna()]
        if len(valid_prices) > 0:
            base_price = valid_prices[price_col].iloc[0]
            wdoz24['change'] = wdoz24[price_col] - base_price

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


def create_calendar_spread_4types(output_path: str):
    """
    Create chart showing 4 types of calendar spread.

    Spread types (as specified by task author):
    - Ask-Ask: front_ask - back_ask
    - Bid-Bid: front_bid - back_bid
    - Ask-Bid: front_ask - back_bid
    - Bid-Ask: front_bid - back_ask
    """
    import numpy as np

    np.random.seed(42)
    n_points = 1000

    time = pd.date_range(start='2024-11-18 10:00', periods=n_points, freq='s')

    # Front month (WDOZ24) - more volatile
    base_price = 5900
    front_noise = np.cumsum(np.random.randn(n_points) * 2)
    front_mid = base_price + front_noise
    front_spread_half = 0.5 + np.abs(np.random.randn(n_points) * 0.2)
    front_bid = front_mid - front_spread_half
    front_ask = front_mid + front_spread_half

    # Back month (WDOF25) - follows front with contango
    back_mid = front_mid + 15 + np.random.randn(n_points) * 0.5
    back_spread_half = 0.7 + np.abs(np.random.randn(n_points) * 0.3)
    back_bid = back_mid - back_spread_half
    back_ask = back_mid + back_spread_half

    # Calculate 4 spread types
    spread_ask_ask = front_ask - back_ask
    spread_bid_bid = front_bid - back_bid
    spread_ask_bid = front_ask - back_bid
    spread_bid_ask = front_bid - back_ask

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            'Contract Prices: WDOZ24 vs WDOF25 (Synthetic)',
            'Calendar Spreads: 4 Types',
            'Spread Range'
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

    # Panel 3: Spread range
    spread_max = np.maximum.reduce([spread_ask_ask, spread_bid_bid, spread_ask_bid, spread_bid_ask])
    spread_min = np.minimum.reduce([spread_ask_ask, spread_bid_bid, spread_ask_bid, spread_bid_ask])
    spread_mid = (spread_ask_ask + spread_bid_bid) / 2

    fig.add_trace(
        go.Scatter(x=time, y=spread_max, name='Max',
                   line=dict(color='rgba(76, 175, 80, 0.5)', width=1),
                   showlegend=False),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=spread_min, name='Min',
                   line=dict(color='rgba(76, 175, 80, 0.5)', width=1),
                   fill='tonexty',
                   fillcolor='rgba(76, 175, 80, 0.2)',
                   showlegend=False),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=time, y=spread_mid, name='Mid',
                   line=dict(color='#4CAF50', width=2)),
        row=3, col=1
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)

    fig.update_layout(
        title=dict(
            text='<b>WDO Calendar Spread — 4 Types</b><br>' +
                 '<sup>Ask-Ask, Bid-Bid, Ask-Bid, Bid-Ask (as specified by task author)</sup>',
            x=0.5
        ),
        height=900,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        hovermode='x unified',
        annotations=[
            dict(
                text='<i>Synthetic data. Spread types: Ask-Ask (front_ask - back_ask), ' +
                     'Bid-Bid (front_bid - back_bid), Ask-Bid, Bid-Ask</i>',
                xref='paper', yref='paper',
                x=0.5, y=-0.06,
                showarrow=False,
                font=dict(size=10, color='gray')
            )
        ]
    )

    fig.update_yaxes(title_text="Price (BRL)", row=1, col=1)
    fig.update_yaxes(title_text="Spread (pts)", row=2, col=1)
    fig.update_yaxes(title_text="Range", row=3, col=1)

    fig.write_html(output_path)
    print(f"4-types spread chart saved to: {output_path}")

    # Print statistics
    print(f"\nSpread Statistics (synthetic):")
    print(f"  Ask-Ask: mean={np.mean(spread_ask_ask):.2f}")
    print(f"  Bid-Bid: mean={np.mean(spread_bid_bid):.2f}")
    print(f"  Ask-Bid: mean={np.mean(spread_ask_bid):.2f}")
    print(f"  Bid-Ask: mean={np.mean(spread_bid_ask):.2f}")


if __name__ == '__main__':
    output_dir = Path(__file__).parent.parent / 'output'
    output_dir.mkdir(exist_ok=True)

    tob_file = output_dir / 'orderbook_tob.csv'

    # Create main chart with TOB data
    if tob_file.exists():
        create_wdo_chart(str(tob_file), str(output_dir / 'wdo_prices.html'))

    # Create 4-types spread chart
    create_calendar_spread_4types(str(output_dir / 'wdo_spread.html'))
