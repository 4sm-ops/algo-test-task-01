"""
Visualization module for Volatility & Momentum indicators.
Interactive charts using Plotly with light theme.
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import IndicatorConfig


def plot_indicators_dashboard(
    df: pd.DataFrame,
    config: IndicatorConfig,
    symbol: str,
    vol_summary: dict,
    mom_summary: dict,
    output_path: Path,
) -> None:
    """
    Create comprehensive indicators dashboard with multiple charts.

    Layout:
    - Row 1: Price (mid)
    - Row 2: Volatility (RV for different windows + EWMA)
    - Row 3: Momentum ROC (different windows)
    - Row 4: Momentum Simple (different windows)

    Args:
        df: DataFrame with price and indicators
        config: Indicator configuration
        symbol: Symbol name
        vol_summary: Volatility summary stats
        mom_summary: Momentum summary stats
        output_path: Path to save HTML
    """
    # Subsample for performance
    plot_df = df.copy()
    if len(plot_df) > 5000:
        step = len(plot_df) // 5000
        plot_df = plot_df.iloc[::step]

    windows = [config.vol_window_short, config.vol_window_medium, config.vol_window_long]

    # Create 4-row subplot
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.25, 0.25, 0.25, 0.25],
        subplot_titles=(
            f"Price ({symbol})",
            "Volatility (Realized & EWMA)",
            "Momentum - ROC (%)",
            "Momentum - Simple (pts)",
        ),
    )

    # Colors
    colors = {
        "price": "#2E86AB",
        "vol_short": "#E94F37",
        "vol_medium": "#F77F00",
        "vol_long": "#3D348B",
        "ewma": "#7B2D8E",
        "mom_short": "#2E86AB",
        "mom_medium": "#27AE60",
        "mom_long": "#E74C3C",
    }

    # 1. Price
    fig.add_trace(
        go.Scatter(
            x=plot_df["ts"],
            y=plot_df["mid"],
            mode="lines",
            name="Price",
            line=dict(color=colors["price"], width=1.5),
            hovertemplate="<b>Time:</b> %{x}<br><b>Price:</b> %{y:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # 2. Volatility
    for i, window in enumerate(windows):
        col_name = f"rv_{window}"
        if col_name in plot_df.columns:
            color_key = ["vol_short", "vol_medium", "vol_long"][i]
            fig.add_trace(
                go.Scatter(
                    x=plot_df["ts"],
                    y=plot_df[col_name],
                    mode="lines",
                    name=f"RV({window})",
                    line=dict(color=colors[color_key], width=1.2),
                    hovertemplate=f"<b>RV({window}):</b> %{{y:.6f}}<extra></extra>",
                ),
                row=2,
                col=1,
            )

    if "ewma_vol" in plot_df.columns:
        fig.add_trace(
            go.Scatter(
                x=plot_df["ts"],
                y=plot_df["ewma_vol"],
                mode="lines",
                name="EWMA",
                line=dict(color=colors["ewma"], width=1.5, dash="dash"),
                hovertemplate="<b>EWMA:</b> %{y:.6f}<extra></extra>",
            ),
            row=2,
            col=1,
        )

    # 3. ROC
    for i, window in enumerate(windows):
        col_name = f"roc_{window}"
        if col_name in plot_df.columns:
            color_key = ["mom_short", "mom_medium", "mom_long"][i]
            # Convert to percentage
            fig.add_trace(
                go.Scatter(
                    x=plot_df["ts"],
                    y=plot_df[col_name] * 100,
                    mode="lines",
                    name=f"ROC({window})",
                    line=dict(color=colors[color_key], width=1.2),
                    hovertemplate=f"<b>ROC({window}):</b> %{{y:.4f}}%<extra></extra>",
                ),
                row=3,
                col=1,
            )
    fig.add_hline(y=0, line_dash="dash", line_color="#888888", row=3, col=1)

    # 4. Simple Momentum
    for i, window in enumerate(windows):
        col_name = f"mom_{window}"
        if col_name in plot_df.columns:
            color_key = ["mom_short", "mom_medium", "mom_long"][i]
            fig.add_trace(
                go.Scatter(
                    x=plot_df["ts"],
                    y=plot_df[col_name],
                    mode="lines",
                    name=f"Mom({window})",
                    line=dict(color=colors[color_key], width=1.2),
                    hovertemplate=f"<b>Mom({window}):</b> %{{y:.2f}}<extra></extra>",
                ),
                row=4,
                col=1,
            )
    fig.add_hline(y=0, line_dash="dash", line_color="#888888", row=4, col=1)

    # Build summary text
    params_text = (
        f"<b>Parameters:</b> "
        f"Windows: {windows[0]}/{windows[1]}/{windows[2]} ticks | "
        f"EWMA λ: {config.ewma_lambda}"
    )

    vol_text = (
        f"<b>Volatility:</b> "
        f"RV({windows[1]}) mean: {vol_summary.get(f'rv_{windows[1]}_mean', 0):.6f} | "
        f"EWMA mean: {vol_summary.get('ewma_vol_mean', 0):.6f}"
    )

    mom_text = (
        f"<b>Momentum:</b> "
        f"ROC({windows[1]}) mean: {mom_summary.get(f'roc_{windows[1]}_mean', 0)*100:.4f}% | "
        f"Positive: {mom_summary.get(f'roc_{windows[1]}_positive_pct', 0)*100:.1f}%"
    )

    # Layout
    fig.update_layout(
        title=dict(
            text=(
                f"<b>Volatility & Momentum Dashboard - {symbol}</b><br>"
                f"<span style='font-size:11px;color:#666'>{params_text}</span><br>"
                f"<span style='font-size:11px;color:#666'>{vol_text}</span><br>"
                f"<span style='font-size:11px;color:#666'>{mom_text}</span>"
            ),
            x=0.5,
            xanchor="center",
        ),
        template="plotly_white",
        paper_bgcolor="#FAFAFA",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", size=11, color="#333333"),
        height=1000,
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=1.12,
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="#DDDDDD",
            borderwidth=1,
        ),
        hovermode="x unified",
        margin=dict(l=60, r=150, t=140, b=40),
    )

    # Update all axes
    for i in range(1, 5):
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor="#EEEEEE",
            row=i,
            col=1,
        )
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor="#EEEEEE",
            row=i,
            col=1,
        )

    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volatility", row=2, col=1)
    fig.update_yaxes(title_text="ROC (%)", row=3, col=1)
    fig.update_yaxes(title_text="Momentum (pts)", row=4, col=1)
    fig.update_xaxes(title_text="Time", row=4, col=1)

    fig.write_html(
        output_path,
        include_plotlyjs=True,
        full_html=True,
        config={"displaylogo": False},
    )


def plot_comparison_dashboard(
    df_b3: pd.DataFrame,
    df_moex: pd.DataFrame,
    config: IndicatorConfig,
    output_path: Path,
) -> None:
    """
    Create comparison dashboard for two symbols.

    Args:
        df_b3: DataFrame for B3 symbol
        df_moex: DataFrame for MOEX symbol
        config: Indicator configuration
        output_path: Path to save HTML
    """
    # Subsample for performance
    step_b3 = max(1, len(df_b3) // 3000)
    step_moex = max(1, len(df_moex) // 3000)
    plot_b3 = df_b3.iloc[::step_b3]
    plot_moex = df_moex.iloc[::step_moex]

    window = config.vol_window_medium

    fig = make_subplots(
        rows=3,
        cols=2,
        shared_xaxes=False,
        vertical_spacing=0.1,
        horizontal_spacing=0.08,
        subplot_titles=(
            "B3 (GLDG26) - Price",
            "MOEX (GOLD-3.26) - Price",
            "B3 - Volatility",
            "MOEX - Volatility",
            "B3 - ROC",
            "MOEX - ROC",
        ),
    )

    # B3 Price
    fig.add_trace(
        go.Scatter(x=plot_b3["ts"], y=plot_b3["mid"], mode="lines",
                   name="B3 Price", line=dict(color="#2E86AB", width=1.2)),
        row=1, col=1,
    )

    # MOEX Price
    fig.add_trace(
        go.Scatter(x=plot_moex["ts"], y=plot_moex["mid"], mode="lines",
                   name="MOEX Price", line=dict(color="#A23B72", width=1.2)),
        row=1, col=2,
    )

    # B3 Volatility
    if f"rv_{window}" in plot_b3.columns:
        fig.add_trace(
            go.Scatter(x=plot_b3["ts"], y=plot_b3[f"rv_{window}"], mode="lines",
                       name=f"B3 RV({window})", line=dict(color="#E94F37", width=1.2)),
            row=2, col=1,
        )
    if "ewma_vol" in plot_b3.columns:
        fig.add_trace(
            go.Scatter(x=plot_b3["ts"], y=plot_b3["ewma_vol"], mode="lines",
                       name="B3 EWMA", line=dict(color="#7B2D8E", width=1.2, dash="dash")),
            row=2, col=1,
        )

    # MOEX Volatility
    if f"rv_{window}" in plot_moex.columns:
        fig.add_trace(
            go.Scatter(x=plot_moex["ts"], y=plot_moex[f"rv_{window}"], mode="lines",
                       name=f"MOEX RV({window})", line=dict(color="#E94F37", width=1.2)),
            row=2, col=2,
        )
    if "ewma_vol" in plot_moex.columns:
        fig.add_trace(
            go.Scatter(x=plot_moex["ts"], y=plot_moex["ewma_vol"], mode="lines",
                       name="MOEX EWMA", line=dict(color="#7B2D8E", width=1.2, dash="dash")),
            row=2, col=2,
        )

    # B3 ROC
    if f"roc_{window}" in plot_b3.columns:
        fig.add_trace(
            go.Scatter(x=plot_b3["ts"], y=plot_b3[f"roc_{window}"] * 100, mode="lines",
                       name=f"B3 ROC({window})", line=dict(color="#27AE60", width=1.2)),
            row=3, col=1,
        )
    fig.add_hline(y=0, line_dash="dash", line_color="#888888", row=3, col=1)

    # MOEX ROC
    if f"roc_{window}" in plot_moex.columns:
        fig.add_trace(
            go.Scatter(x=plot_moex["ts"], y=plot_moex[f"roc_{window}"] * 100, mode="lines",
                       name=f"MOEX ROC({window})", line=dict(color="#27AE60", width=1.2)),
            row=3, col=2,
        )
    fig.add_hline(y=0, line_dash="dash", line_color="#888888", row=3, col=2)

    fig.update_layout(
        title=dict(
            text="<b>B3 vs MOEX: Volatility & Momentum Comparison</b>",
            x=0.5,
            xanchor="center",
        ),
        template="plotly_white",
        paper_bgcolor="#FAFAFA",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", size=11, color="#333333"),
        height=900,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.08,
            xanchor="center",
            x=0.5,
        ),
        margin=dict(l=60, r=60, t=80, b=100),
    )

    for i in range(1, 4):
        for j in range(1, 3):
            fig.update_xaxes(showgrid=True, gridcolor="#EEEEEE", row=i, col=j)
            fig.update_yaxes(showgrid=True, gridcolor="#EEEEEE", row=i, col=j)

    fig.write_html(
        output_path,
        include_plotlyjs=True,
        full_html=True,
        config={"displaylogo": False},
    )
