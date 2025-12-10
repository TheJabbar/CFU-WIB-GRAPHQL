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
                    'real_mtd':      {'name': 'Actual',    'color': '#0d6efd', 'dash': 'solid', 'symbol': 'circle'},
                    'target_mtd':    {'name': 'Target',    'color': '#ffc107', 'dash': 'dash',  'symbol': 'diamond'},
                    'prev_year':     {'name': 'Prev Year', 'color': '#6f42c1', 'dash': 'dot',   'symbol': 'cross'}
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
                # Handle comparison_trend and trend chart types (Dynamic Layout)
                unit_name = df["unit_name"].iloc[0] if "unit_name" in df.columns else "Unknown Unit"
                
                # 1. Identify metrics present in the data
                if 'metric_type' in df.columns:
                    # Get unique metrics and sort them by priority
                    unique_metrics = df['metric_type'].unique().tolist()
                    priority = ['REVENUE', 'COE', 'EBITDA', 'NET INCOME', 'EBIT', 'EBT']
                    present_metrics = sorted(unique_metrics, key=lambda x: priority.index(x) if x in priority else 999)
                else:
                    present_metrics = ["Trend"]

                num_metrics = len(present_metrics)

                # 2. Determine Grid Layout
                if num_metrics <= 1:
                    rows, cols = 1, 1
                    height = 500
                    vertical_spacing = 0
                else:
                    cols = 2
                    rows = (num_metrics + 1) // 2
                    height = 350 * rows
                    vertical_spacing = 0.15

                subplot_titles = [f'<b>{m}</b>' for m in present_metrics]

                fig = make_subplots(
                    rows=rows, cols=cols,
                    subplot_titles=subplot_titles,
                    vertical_spacing=vertical_spacing,
                    horizontal_spacing=0.1
                )

                # 3. Add Traces
                for i, metric_key in enumerate(present_metrics):
                    row = i // cols + 1
                    col = i % cols + 1
                    
                    if 'metric_type' in df.columns:
                        metric_data = df[df['metric_type'] == metric_key]
                    else:
                        metric_data = df
                    
                    if not metric_data.empty:
                        ChartGenerator._add_traces_to_subplot(fig, metric_data, row, col, show_legend=(i == 0))

                # 4. Update Layout
                fig.update_layout(
                    title_text=f'<b>Interactive Performance Analysis - {unit_name}</b>',
                    title_x=0.5, title_y=0.98,
                    title_font_size=20,
                    autosize=True,
                    height=height,
                    template='plotly_white',
                    font=dict(family="Segoe UI, Arial, sans-serif", size=12, color="#444"),
                    paper_bgcolor='white',
                    plot_bgcolor='#F8F9FA',
                    legend=dict(
                        title_text='<b>Legend</b>', orientation="v",
                        yanchor="top", y=1, xanchor="left", x=1.02,
                        font_size=11, bgcolor='rgba(255, 255, 255, 0.9)',
                        bordercolor="#E0E0E0", borderwidth=1
                    ),
                    margin=dict(l=50, r=100, t=80, b=80),
                    hovermode='x unified',
                    hoverlabel=dict(
                        bgcolor="white", font_size=12,
                        bordercolor="#CCCCCC", font_family="Segoe UI, Arial, sans-serif"
                    )
                )
                
                # Add period annotation at the bottom
                fig.add_annotation(
                    text=f"Period: {period_text}",
                    xref="paper", yref="paper",
                    x=0.5, y=-0.15 if num_metrics == 1 else -0.05,
                    showarrow=False,
                    font=dict(size=10, color="gray")
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
            # Flexible column matching for comparison trend
            if data and isinstance(data[0], dict):
                keys = data[0].keys()
                # Check for actual/real aliases
                actual_col = 'real_mtd' if 'real_mtd' in keys else 'actual'
                
                # Check for target aliases
                target_col = 'target_mtd' if 'target_mtd' in keys else 'target'

                # Check for prev_year/prev_month aliases
                prev_col = 'prev_year'
                if 'prev_month' in keys:
                    prev_col = 'prev_month'
                elif 'prev_year_mtd' in keys:
                    prev_col = 'prev_year_mtd'
                
                cols = ['period', 'unit_name', 'metric_type', 'category_l3', 'category_l4', actual_col, target_col, prev_col]
                
                # Normalize column names in the dataframe later
            else:
                # Fallback for tuples - assuming standard order from prompt
                cols = ['period', 'unit_name', 'metric_type', 'category_l3', 'category_l4', 'real_mtd', 'target_mtd', 'prev_year']

        elif chart_type == "external_revenue_trend":
            cols = ['period', 'unit_name', 'real_mtd', 'target_mtd', 'prev_year']
        elif chart_type == "trend":
            cols = ['period', 'unit_name', 'metric_type', 'category_l3', 'category_l4', 'real_mtd']
        
        if not cols:
            logger.error(f"Unknown chart_type '{chart_type}'.")
            return None, None

        # Handle list of dicts (from sqlite3.Row) or list of tuples
        if data and isinstance(data[0], dict):
            try:
                df = pd.DataFrame(data)
                
                # Normalize column names to standard expected names for plotting
                rename_map = {}
                if 'actual' in df.columns: rename_map['actual'] = 'real_mtd'
                if 'target' in df.columns: rename_map['target'] = 'target_mtd'
                if 'prev_year_mtd' in df.columns: rename_map['prev_year_mtd'] = 'prev_year'
                # Note: we keep 'prev_month' as is, to distinguish in legend
                
                if rename_map:
                    df = df.rename(columns=rename_map)
                
                # Ensure all required columns exist (after renaming)
                # We need at least real_mtd and target_mtd. Prev is optional-ish but good to have.
                if 'real_mtd' not in df.columns:
                     logger.error(f"Missing 'real_mtd' (or alias) in data columns: {df.columns}")
                     return None, None
                     
                # Filter to keep only relevant columns + period_str calculation
                # We don't strictly filter 'cols' here because 'cols' might have dynamic names
                # Just proceed with the DF we have.
                
            except Exception as e:
                logger.error(f"Error converting dict data to DataFrame: {e}")
                return None, None
        else:
            # Fallback for tuples
            if data and len(data[0]) != len(cols):
                logger.error(f"Column mismatch for chart_type '{chart_type}'. Expected {len(cols)}, got {len(data[0])}.")
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
            'real_mtd':      {'name': 'Actual',    'color': '#0d6efd', 'dash': 'solid', 'symbol': 'circle'},
            'target_mtd':    {'name': 'Target',    'color': '#ffc107', 'dash': 'dash',  'symbol': 'diamond'},
            'prev_year':     {'name': 'Prev Year', 'color': '#6f42c1', 'dash': 'dot',   'symbol': 'cross'},
            'prev_month':    {'name': 'Prev Month', 'color': '#6f42c1', 'dash': 'dot',   'symbol': 'cross'}
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