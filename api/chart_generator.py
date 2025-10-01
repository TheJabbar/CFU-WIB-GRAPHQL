import pandas as pd
from typing import List, Tuple
from loguru import logger
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import calendar

class ChartGenerator:
    """A class for generating interactive Plotly charts."""

    @staticmethod
    def create_trend_chart(data: List[Tuple], chart_type: str = "trend") -> str:
        """
        Generates a polished, responsive trend chart using Plotly.
        Returns the Plotly figure as a JSON string.
        """
        try:
            df, period_text = ChartGenerator._data_to_dataframe(data, chart_type)
            if df is None or df.empty:
                logger.warning("DataFrame is empty, cannot create chart.")
                return None

            # Handle different chart types
            if chart_type == "external_revenue_trend":
                # For external revenue trend, we only have one metric to display
                unit_name = df["unit_name"].iloc[0] if "unit_name" in df.columns else "Unknown Unit"
                
                fig = go.Figure()
                
                # Add traces for the external revenue data
                styles = {
                    'actual_mtd':    {'name': 'Actual',    'color': '#0d6efd', 'dash': 'solid', 'symbol': 'circle'},
                    'target_mtd':    {'name': 'Target',    'color': '#ffc107', 'dash': 'dash',  'symbol': 'diamond'},
                    'prev_year_mtd': {'name': 'Prev Year', 'color': '#6f42c1', 'dash': 'dot',   'symbol': 'cross'}
                }

                for col_name, style in styles.items():
                    if col_name in df.columns:
                        fig.add_trace(go.Scatter(
                            x=df['period_str'], y=df[col_name],
                            name=style['name'], mode='lines+markers',
                            line=dict(color=style['color'], width=2.5),
                            marker=dict(symbol=style['symbol'], size=8),
                            opacity=0.9,
                            hovertemplate='<b>%{y:,.0f}</b><extra></extra>'
                        ))
                
                fig.update_layout(
                    title_text=f'<b>External Revenue Trend - {unit_name}</b>',
                    title_x=0.5, title_y=0.96,
                    title_font_size=20,
                    autosize=True,
                    template='plotly_white',
                    font=dict(family="Segoe UI, Arial, sans-serif", size=12, color="#444"),
                    paper_bgcolor='white',
                    plot_bgcolor='#F8F9FA',
                    
                    legend=dict(
                        title_text='<b>Legend</b>', orientation="v",
                        yanchor="top", y=1, xanchor="left", x=1.05,
                        font_size=11, bgcolor='rgba(255, 255, 255, 0.9)',
                        bordercolor="#E0E0E0", borderwidth=1
                    ),
                    margin=dict(l=90, r=160, t=110, b=80),
                    hovermode='x unified',
                    hoverlabel=dict(
                        bgcolor="white", font_size=12,
                        bordercolor="#CCCCCC", font_family="Segoe UI, Arial, sans-serif"
                    ),
                    annotations=[
                        dict(
                            text=f"Period: {period_text}",
                            showarrow=False, xref='paper', yref='paper',
                            x=0.5, y=-0.15, xanchor='center', yanchor='top',
                            font=dict(size=10, color="gray")
                        )
                    ]
                )
                
                fig.update_xaxes(
                    type='category', showgrid=True, gridwidth=1, gridcolor='#E0E0E0',
                    showline=True, linewidth=1, linecolor='#B0B0B0',
                    automargin=True
                )
                fig.update_yaxes(
                    title_text="",
                    showgrid=True, gridwidth=1, gridcolor='#E0E0E0',
                    showline=True, linewidth=1, linecolor='#B0B0B0',
                    automargin=True
                )

                return fig.to_json()
            else:
                # Handle comparison_trend and trend chart types (existing logic)
                metrics_map = {
                    'REVENUE': 'Revenue',
                    'COE': 'Cost of Expenses (COE)',
                    'EBITDA': 'EBITDA',
                    'NET INCOME': 'Net Income'
                }
                metrics_keys = list(metrics_map.keys())
                subplot_titles = [f'<b>{v}</b>' for v in metrics_map.values()]
                unit_name = df["unit_name"].iloc[0] if "unit_name" in df.columns else "Unknown Unit"
                
                fig = make_subplots(
                    rows=2, cols=2,
                    subplot_titles=subplot_titles,
                    vertical_spacing=0.3,
                    horizontal_spacing=0.1
                )

                for i, metric_key in enumerate(metrics_keys):
                    row, col = i // 2 + 1, i % 2 + 1
                    # Check if metric_type column exists before filtering
                    if 'metric_type' in df.columns:
                        metric_data = df[df['metric_type'] == metric_key]
                    else:
                        # For simple trend charts without metric_type, use all data
                        metric_data = df
                    
                    if not metric_data.empty:
                        ChartGenerator._add_traces_to_subplot(fig, metric_data, row, col, show_legend=(i == 0))

                # Define annotations manually for robustness
                annotations = [
                    dict(text=subplot_titles[0], x=0.225, y=0.95, xref='paper', yref='paper', showarrow=False, font=dict(size=14)),
                    dict(text=subplot_titles[1], x=0.775, y=0.95, xref='paper', yref='paper', showarrow=False, font=dict(size=14)),
                    dict(text=subplot_titles[2], x=0.225, y=0.5, xref='paper', yref='paper', showarrow=False, font=dict(size=14)), # <-- Turunkan posisi Y
                    dict(text=subplot_titles[3], x=0.775, y=0.5, xref='paper', yref='paper', showarrow=False, font=dict(size=14)), # <-- Turunkan posisi Y
                    # Period Annotation
                    dict(text=f"Period: {period_text}", x=0.5, y=-0.30, xref='paper', yref='paper', showarrow=False, font=dict(size=10, color="gray")) # <-- Turunkan posisi Y
                ]

                fig.update_layout(
                    title_text=f'<b>Interactive Performance Analysis - {unit_name}</b>',
                    title_x=0.5, title_y=0.96,
                    title_font_size=20,
                    autosize=True,
                    height=750,
                    template='plotly_white',
                    font=dict(family="Segoe UI, Arial, sans-serif", size=12, color="#444"),
                    paper_bgcolor='white',
                    plot_bgcolor='#F8F9FA',
                    legend=dict(
                        title_text='<b>Legend</b>', orientation="v",
                        yanchor="top", y=1, xanchor="left", x=1.05,
                        font_size=11, bgcolor='rgba(255, 255, 255, 0.9)',
                        bordercolor="#E0E0E0", borderwidth=1
                    ),
                    margin=dict(l=90, r=160, t=110, b=90),
                    hovermode='x unified',
                    hoverlabel=dict(
                        bgcolor="white", font_size=12,
                        bordercolor="#CCCCCC", font_family="Segoe UI, Arial, sans-serif"
                    ),
                    annotations=annotations 
                )
                
                fig.update_xaxes(
                    type='category', showgrid=True, gridwidth=1, gridcolor='#E0E0E0',
                    showline=True, linewidth=1, linecolor='#B0B0B0',
                    automargin=True
                )
                fig.update_yaxes(
                    title_text="",
                    showgrid=True, gridwidth=1, gridcolor='#E0E0E0',
                    showline=True, linewidth=1, linecolor='#B0B0B0',
                    automargin=True
                )

                return fig.to_json()

        except Exception as e:
            logger.error(f"Error creating final revised Plotly chart: {e}")
            return None

    @staticmethod
    def _data_to_dataframe(data: List[Tuple], chart_type: str):
        """Converts raw tuple data into a processed Pandas DataFrame."""
        cols = []
        if chart_type == "comparison_trend":
            cols = ['period', 'unit_name', 'metric_type', 'actual_mtd', 'target_mtd', 'prev_year_mtd']
        elif chart_type == "external_revenue_trend":
            cols = ['period', 'unit_name', 'actual_mtd', 'target_mtd', 'prev_year_mtd']
        elif chart_type == "trend":
            cols = ['period', 'unit_name', 'metric_type', 'actual_mtd']
        
        if not cols or (data and len(data[0]) != len(cols)):
            logger.error(f"Column mismatch for chart_type '{chart_type}'.")
            return None, None

        df = pd.DataFrame(data, columns=cols)
        df['period_str'] = df['period'].apply(lambda x: f"{str(x)[:4]}-{str(x)[4:]}")
        
        # Extract period range for the footer annotation
        min_p = df['period'].min()
        max_p = df['period'].max()
        min_month = calendar.month_name[int(str(min_p)[4:])]
        min_year = str(min_p)[:4]
        max_month = calendar.month_name[int(str(max_p)[4:])]
        max_year = str(max_p)[:4]
        period_text = f"{min_month} {min_year} - {max_month} {max_year}"

        return df, period_text

    @staticmethod
    def _add_traces_to_subplot(fig: go.Figure, df: pd.DataFrame, row: int, col: int, show_legend: bool):
        """Adds all relevant traces (Actual, Target, etc.) to a given subplot."""
        
        def format_hover(value):
            """Formats large numbers into T/B/M for hover labels."""
            if abs(value) >= 1e12: return f'{value/1e12:.2f} T'
            if abs(value) >= 1e9: return f'{value/1e9:.2f} M'
            if abs(value) >= 1e6: return f'{value/1e6:.2f} Jt'
            return f'{value:,.0f}'

        styles = {
            'actual_mtd':    {'name': 'Actual',    'color': '#0d6efd', 'dash': 'solid', 'symbol': 'circle'},
            'target_mtd':    {'name': 'Target',    'color': '#ffc107', 'dash': 'dash',  'symbol': 'diamond'},
            'prev_year_mtd': {'name': 'Prev Year', 'color': '#6f42c1', 'dash': 'dot',   'symbol': 'cross'}
        }

        for col_name, style in styles.items():
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['period_str'], y=df[col_name],
                    name=style['name'], mode='lines+markers',
                    line=dict(color=style['color'], width=2.5),
                    marker=dict(symbol=style['symbol'], size=8),
                    opacity=0.9,
                    hovertemplate='<b>%{customdata}</b><extra></extra>',
                    customdata=[format_hover(y) for y in df[col_name]],
                    legendgroup=style['name'], showlegend=show_legend
                ), row=row, col=col)