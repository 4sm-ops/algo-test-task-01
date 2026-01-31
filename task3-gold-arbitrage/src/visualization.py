"""
Visualization module for Gold Arbitrage Strategy.
Interactive charts using Plotly with light theme.
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from typing import Optional

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import StrategyConfig


def plot_equity_plotly(
    df: pd.DataFrame,
    equity_curve: pd.Series,
    config: StrategyConfig,
    result_metrics: dict,
    output_path: Path,
    title: str = "Gold Arbitrage Strategy - Equity Curve",
) -> None:
    """
    Create interactive equity curve visualization with Plotly.

    Args:
        df: DataFrame with timestamp column 'ts'
        equity_curve: Series with cumulative PnL values
        config: Strategy configuration for legend
        result_metrics: Dict with backtest metrics (net_pnl, sharpe_ratio, etc.)
        output_path: Path to save HTML file
        title: Chart title
    """
    # Prepare time index for equity curve
    # Sample equity to match df length or create time-based index
    if len(equity_curve) > len(df):
        step = len(equity_curve) // len(df)
        equity_sampled = equity_curve.iloc[::step][:len(df)]
        time_index = df["ts"].iloc[:len(equity_sampled)]
    else:
        time_index = df["ts"].iloc[:len(equity_curve)]
        equity_sampled = equity_curve

    # Create figure with subplots
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=("Equity Curve", "Drawdown"),
    )

    # 1. Equity Curve
    fig.add_trace(
        go.Scatter(
            x=time_index,
            y=equity_sampled.values,
            mode="lines",
            name="Equity",
            line=dict(color="#2E86AB", width=2),
            fill="tozeroy",
            fillcolor="rgba(46, 134, 171, 0.2)",
            hovertemplate="<b>Time:</b> %{x}<br><b>PnL:</b> %{y:.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # Add zero line
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="#888888",
        line_width=1,
        row=1,
        col=1,
    )

    # 2. Drawdown
    rolling_max = equity_sampled.cummax()
    drawdown = equity_sampled - rolling_max

    fig.add_trace(
        go.Scatter(
            x=time_index,
            y=drawdown.values,
            mode="lines",
            name="Drawdown",
            line=dict(color="#E94F37", width=1.5),
            fill="tozeroy",
            fillcolor="rgba(233, 79, 55, 0.2)",
            hovertemplate="<b>Time:</b> %{x}<br><b>Drawdown:</b> %{y:.2f}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # Strategy parameters annotation
    params_text = (
        f"<b>Strategy Parameters:</b><br>"
        f"Entry: ±{config.entry_threshold}σ | "
        f"Exit: ±{config.exit_threshold}σ | "
        f"Stop: ±{config.stop_loss_threshold}σ<br>"
        f"Window: {config.zscore_window} ticks | "
        f"Commission: {config.commission_per_contract:.2f} BRL/contract"
    )

    # Results annotation
    results_text = (
        f"<b>Results:</b><br>"
        f"Net PnL: {result_metrics.get('net_pnl', 0):.2f} | "
        f"Trades: {result_metrics.get('num_trades', 0)} | "
        f"Win Rate: {result_metrics.get('win_rate', 0):.1%}<br>"
        f"Sharpe: {result_metrics.get('sharpe_ratio', 0):.2f} | "
        f"Calmar: {result_metrics.get('calmar_ratio', 0):.2f} | "
        f"VaR 95%: {result_metrics.get('var_95', 0):.0f}<br>"
        f"Max DD: {result_metrics.get('max_drawdown', 0):.2f} | "
        f"PF: {result_metrics.get('profit_factor', 0):.2f} | "
        f"ROI/Margin: {result_metrics.get('roi_on_margin', 0):.1f}%"
    )

    # Update layout with light theme
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            x=0.5,
            xanchor="center",
            font=dict(size=20, color="#333333"),
        ),
        template="plotly_white",
        paper_bgcolor="#FAFAFA",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Arial, sans-serif", size=12, color="#333333"),
        hovermode="x unified",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255, 255, 255, 0.8)",
            bordercolor="#DDDDDD",
            borderwidth=1,
        ),
        # Annotations
        annotations=[
            dict(
                text=params_text,
                xref="paper",
                yref="paper",
                x=0,
                y=-0.15,
                xanchor="left",
                yanchor="top",
                showarrow=False,
                font=dict(size=11, color="#555555"),
                align="left",
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor="#DDDDDD",
                borderwidth=1,
                borderpad=8,
            ),
            dict(
                text=results_text,
                xref="paper",
                yref="paper",
                x=1,
                y=-0.15,
                xanchor="right",
                yanchor="top",
                showarrow=False,
                font=dict(size=11, color="#555555"),
                align="right",
                bgcolor="rgba(255, 255, 255, 0.9)",
                bordercolor="#DDDDDD",
                borderwidth=1,
                borderpad=8,
            ),
        ],
        margin=dict(l=60, r=60, t=100, b=120),
    )

    # Update axes
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor="#EEEEEE",
        linecolor="#CCCCCC",
        tickfont=dict(size=10),
    )

    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor="#EEEEEE",
        linecolor="#CCCCCC",
        tickfont=dict(size=10),
        title_font=dict(size=12),
    )

    fig.update_yaxes(title_text="Cumulative PnL", row=1, col=1)
    fig.update_yaxes(title_text="Drawdown", row=2, col=1)
    fig.update_xaxes(title_text="Time", row=2, col=1)

    # Save to HTML
    fig.write_html(
        output_path,
        include_plotlyjs=True,
        full_html=True,
        config={
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "displaylogo": False,
        },
    )


def plot_strategy_dashboard(
    df: pd.DataFrame,
    equity_curve: pd.Series,
    config: StrategyConfig,
    result_metrics: dict,
    output_path: Path,
) -> None:
    """
    Create comprehensive strategy dashboard with multiple charts.

    Args:
        df: DataFrame with prices and indicators
        equity_curve: Series with cumulative PnL
        config: Strategy configuration
        result_metrics: Backtest metrics
        output_path: Path to save HTML
    """
    # Subsample data for plotting
    plot_df = df.copy()
    if len(plot_df) > 5000:
        step = len(plot_df) // 5000
        plot_df = plot_df.iloc[::step]

    # Create 4-row subplot
    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.25, 0.25, 0.25, 0.25],
        subplot_titles=(
            "Mid Prices (B3 vs MOEX)",
            "Price Spread",
            "Z-Score",
            "Equity Curve",
        ),
    )

    # 1. Mid Prices
    fig.add_trace(
        go.Scatter(
            x=plot_df["ts"],
            y=plot_df["mid_b3"],
            mode="lines",
            name="B3 (GLDG26)",
            line=dict(color="#2E86AB", width=1.5),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df["ts"],
            y=plot_df["mid_moex"],
            mode="lines",
            name="MOEX (GOLD-3.26)",
            line=dict(color="#A23B72", width=1.5),
        ),
        row=1,
        col=1,
    )

    # 2. Spreads (tradeable)
    fig.add_trace(
        go.Scatter(
            x=plot_df["ts"],
            y=plot_df["spread_long"],
            mode="lines",
            name="Spread Long",
            line=dict(color="#3498DB", width=1.5),
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df["ts"],
            y=plot_df["spread_short"],
            mode="lines",
            name="Spread Short",
            line=dict(color="#E74C3C", width=1.5),
        ),
        row=2,
        col=1,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#888888", row=2, col=1)

    # 3. Z-Scores with thresholds
    fig.add_trace(
        go.Scatter(
            x=plot_df["ts"],
            y=plot_df["zscore_long"],
            mode="lines",
            name="Z-Score Long",
            line=dict(color="#3498DB", width=1.5),
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df["ts"],
            y=plot_df["zscore_short"],
            mode="lines",
            name="Z-Score Short",
            line=dict(color="#E74C3C", width=1.5),
        ),
        row=3,
        col=1,
    )
    # Entry thresholds
    fig.add_hline(
        y=config.entry_threshold,
        line_dash="dash",
        line_color="#E74C3C",
        annotation_text=f"Entry +{config.entry_threshold}σ",
        row=3,
        col=1,
    )
    fig.add_hline(
        y=-config.entry_threshold,
        line_dash="dash",
        line_color="#E74C3C",
        row=3,
        col=1,
    )
    # Exit thresholds
    fig.add_hline(
        y=config.exit_threshold,
        line_dash="dot",
        line_color="#27AE60",
        row=3,
        col=1,
    )
    fig.add_hline(
        y=-config.exit_threshold,
        line_dash="dot",
        line_color="#27AE60",
        row=3,
        col=1,
    )
    fig.add_hline(y=0, line_dash="solid", line_color="#888888", row=3, col=1)

    # 4. Equity Curve
    equity_time = plot_df["ts"].iloc[:len(equity_curve)]
    if len(equity_curve) > len(plot_df):
        step = len(equity_curve) // len(plot_df)
        equity_plot = equity_curve.iloc[::step][:len(plot_df)]
    else:
        equity_plot = equity_curve[:len(plot_df)]

    fig.add_trace(
        go.Scatter(
            x=equity_time[:len(equity_plot)],
            y=equity_plot.values,
            mode="lines",
            name="Equity",
            line=dict(color="#2E86AB", width=2),
            fill="tozeroy",
            fillcolor="rgba(46, 134, 171, 0.2)",
        ),
        row=4,
        col=1,
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#888888", row=4, col=1)

    # Layout
    params_text = (
        f"Entry: ±{config.entry_threshold}σ | Exit: ±{config.exit_threshold}σ | "
        f"Stop: ±{config.stop_loss_threshold}σ | Window: {config.zscore_window}"
    )
    results_text = (
        f"Net PnL: {result_metrics.get('net_pnl', 0):.0f} | "
        f"Trades: {result_metrics.get('num_trades', 0)} | "
        f"Win: {result_metrics.get('win_rate', 0):.1%} | "
        f"Sharpe: {result_metrics.get('sharpe_ratio', 0):.2f} | "
        f"Calmar: {result_metrics.get('calmar_ratio', 0):.2f} | "
        f"ROI/Margin: {result_metrics.get('roi_on_margin', 0):.1f}%"
    )

    fig.update_layout(
        title=dict(
            text=f"<b>Gold Arbitrage Strategy Dashboard</b><br>"
            f"<span style='font-size:12px;color:#666'>{params_text}</span><br>"
            f"<span style='font-size:12px;color:#666'>{results_text}</span>",
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
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="right",
            x=0.99,
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="#DDDDDD",
            borderwidth=1,
        ),
        hovermode="x unified",
        margin=dict(l=60, r=120, t=120, b=40),
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
    fig.update_yaxes(title_text="Spread", row=2, col=1)
    fig.update_yaxes(title_text="Z-Score", row=3, col=1)
    fig.update_yaxes(title_text="PnL", row=4, col=1)

    fig.write_html(
        output_path,
        include_plotlyjs=True,
        full_html=True,
        config={"displaylogo": False},
    )
