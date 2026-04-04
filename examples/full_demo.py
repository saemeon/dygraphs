"""Extensive demo app showcasing all pydygraphs features.

Run with::

    uv run python examples/full_demo.py

Then open http://127.0.0.1:8050 in your browser.
"""

from __future__ import annotations

import dash
import numpy as np
import pandas as pd
from dash import Input, Output, dcc, html

from pydygraphs import (
    Axis,
    Dygraph,
    Event,
    Legend,
    Options,
    RangeSelector,
    Series,
    Shading,
    stacked_bar,
    sync_dygraphs,
)

# =============================================================================
# Data helpers
# =============================================================================


def make_timeseries(
    trend: float, seed: int, start: float, cols: list[str]
) -> pd.DataFrame:
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    data = {}
    for i, col in enumerate(cols):
        data[col] = (
            start + i * 10 + np.cumsum(trend + np.random.randn(120) * 0.5)
        ).round(2)
    return pd.DataFrame(data, index=dates)


def make_contributions_csv(trend: float) -> str:
    np.random.seed(99)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    b = trend * np.ones(120)
    df = pd.DataFrame(
        {
            "Date": dates.strftime("%Y/%m/%d"),
            "Solar": (b + np.random.randn(120) * 0.4 + 0.8).round(2),
            "Wind": (b + np.random.randn(120) * 0.6 + 0.5).round(2),
            "Gas": (b + np.random.randn(120) * 0.3 - 0.3).round(2),
            "Imports": (b + np.random.randn(120) * 0.2 + 0.2).round(2),
            "Curtailment": (-np.abs(np.random.randn(120) * 0.3)).round(2),
        }
    )
    return df.to_csv(index=False)


# =============================================================================
# App
# =============================================================================

app = dash.Dash(__name__)

# ---------------------------------------------------------------------------
# Chart 1: Line chart with all the bells and whistles
# ---------------------------------------------------------------------------

df1 = make_timeseries(0, 42, 15, ["Temperature", "Humidity"])

chart1 = (
    Dygraph(df1, title="Temperature & Humidity")
    .options(
        fill_graph=True,
        draw_points=True,
        stroke_width=2,
        animated_zooms=True,
        colors=["#00d4aa", "#f4a261"],
    )
    .axis("y", label="Value", value_range=(0, 60))
    .series("Temperature", stroke_width=2.5)
    .series("Humidity", fill_graph=False, draw_points=False)
    .legend(show="always")
    .highlight(
        circle_size=5, series_background_alpha=0.2, series_opts={"strokeWidth": 3}
    )
    .range_selector(height=30)
    .roller(roll_period=7)
    .annotation("2024-03-15", "A", tooltip="Spring equinox", series="Temperature")
    .event("2024-02-14", "Valentine's", label_loc="top", color="#f76e8a")
    .shading("2024-01-15", "2024-02-15", color="rgba(200,200,255,0.3)")
    .limit(30.0, "Threshold", color="#e74c3c", stroke_pattern="dotted")
    .crosshair(direction="vertical")
    .unzoom()
)
chart1_component = chart1.to_dash(app=app, component_id="chart-1", height="320px")

# ---------------------------------------------------------------------------
# Chart 2: Multi-series with secondary axis
# ---------------------------------------------------------------------------

df2 = make_timeseries(0, 7, 100, ["Pressure", "Wind Speed"])

chart2 = (
    Dygraph(df2, title="Pressure & Wind Speed")
    .options(stroke_width=2, animated_zooms=True, colors=["#7eb8f7", "#f76e8a"])
    .axis("y", label="Pressure (hPa)")
    .axis("y2", label="Wind (km/h)", independent_ticks=True)
    .series("Pressure", axis="y")
    .series("Wind Speed", axis="y2", stroke_pattern="dashed")
    .legend(show="always")
    .range_selector(height=30)
)
chart2_component = chart2.to_dash(app=app, component_id="chart-2", height="320px")

# ---------------------------------------------------------------------------
# Chart 3: Step plot with annotations
# ---------------------------------------------------------------------------

df3 = pd.DataFrame(
    {"Status": np.random.choice([0, 1, 2], size=60)},
    index=pd.date_range("2024-01-01", periods=60, freq="D"),
)

chart3 = (
    Dygraph(df3, title="System Status (Step Plot)")
    .options(step_plot=True, fill_graph=True, fill_alpha=0.3, colors=["#9b59b6"])
    .axis("y", value_range=(-0.5, 2.5))
    .legend(show="always")
    .shading("2024-01-10", "2024-01-15", color="rgba(255,200,200,0.4)")
    .annotation("2024-01-10", "!", tooltip="Outage start", series="Status")
    .annotation("2024-01-15", "R", tooltip="Recovered", series="Status")
)
chart3_component = chart3.to_dash(app=app, component_id="chart-3", height="250px")

# ---------------------------------------------------------------------------
# Chart 4: Stacked bar chart with range selector
# ---------------------------------------------------------------------------

chart4_component = stacked_bar(
    app,
    "chart-4",
    initial_data=make_contributions_csv(0),
    colors=["#00d4aa", "#7eb8f7", "#f4a261", "#34d399", "#f76e8a"],
    height=280,
    title="Energy Contributions (Stacked Bar)",
    selector_height=40,
)

# ---------------------------------------------------------------------------
# Chart 5: Declarative API style
# ---------------------------------------------------------------------------

df5 = make_timeseries(0, 99, 50, ["Voltage", "Current"])

chart5 = Dygraph(
    df5,
    title="Declarative API Example",
    options=Options(fill_graph=True, stroke_width=2, animated_zooms=True),
    axes=[Axis("y", label="Value")],
    series=[
        Series("Voltage", color="#e74c3c", stroke_width=2.5),
        Series("Current", color="#3498db", fill_graph=False),
    ],
    legend=Legend(show="always"),
    range_selector=RangeSelector(height=25),
    shadings=[Shading(from_="2024-02-01", to="2024-03-01", color="rgba(255,200,200,0.3)")],
    events=[Event(x="2024-02-14", label="Maintenance", color="#888")],
)
chart5_component = chart5.to_dash(app=app, component_id="chart-5", height="280px")

# ---------------------------------------------------------------------------
# Chart 6: Numpy array input + copy/fork
# ---------------------------------------------------------------------------

base_chart = Dygraph(
    np.column_stack([np.arange(50), np.random.randn(50).cumsum()]),
    title="Numpy Input (base)",
).options(stroke_width=2, colors=["#2ecc71"])

chart6 = base_chart.copy()
chart6._attrs["title"] = "Numpy Input + Copy"  # fork variant
chart6_component = chart6.to_dash(app=app, component_id="chart-6", height="200px")

# ---------------------------------------------------------------------------
# Sync charts 1, 2, and 4 (line + line + stacked bar)
# ---------------------------------------------------------------------------

sync_component = sync_dygraphs(app, ["chart-1", "chart-2", "chart-4"])

# ---------------------------------------------------------------------------
# Dropdown to change trend
# ---------------------------------------------------------------------------

TREND_OPTIONS = [
    {"label": "Strong downtrend (-2)", "value": -2},
    {"label": "Mild downtrend (-1)", "value": -1},
    {"label": "No trend (0)", "value": 0},
    {"label": "Mild uptrend (+1)", "value": 1},
    {"label": "Strong uptrend (+2)", "value": 2},
]

CARD = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.06)",
}

app.layout = html.Div(
    style={
        "fontFamily": "'Segoe UI', sans-serif",
        "backgroundColor": "#ffffff",
        "minHeight": "100vh",
        "padding": "40px",
        "maxWidth": "1200px",
        "margin": "0 auto",
        "color": "#111",
    },
    children=[
        sync_component,
        html.H1(
            "pydygraphs Full Demo", style={"textAlign": "center", "color": "#2c3e50"}
        ),
        html.P(
            "Showcasing: builder + declarative APIs, line charts, step plots, stacked bars, "
            "range selectors, annotations, events, shadings, limits, crosshair, zoom sync, "
            "modebar, secondary axes, numpy input, copy/fork, and more.",
            style={"textAlign": "center", "color": "#666", "marginBottom": "32px"},
        ),
        html.Div(
            style={
                "display": "flex",
                "alignItems": "center",
                "gap": "16px",
                "marginBottom": "24px",
            },
            children=[
                html.Label("Data trend:", style={"fontWeight": "600"}),
                dcc.Dropdown(
                    id="trend",
                    options=TREND_OPTIONS,
                    value=0,
                    clearable=False,
                    style={"width": "260px"},
                ),
            ],
        ),
        html.Div(
            style=CARD,
            children=[
                html.H3(
                    "Synced Line Charts",
                    style={"margin": "0 0 8px 0", "fontSize": "14px", "color": "#888"},
                ),
                chart1_component,
            ],
        ),
        html.Div(
            style=CARD,
            children=[
                html.H3(
                    "Dual Axis",
                    style={"margin": "0 0 8px 0", "fontSize": "14px", "color": "#888"},
                ),
                chart2_component,
            ],
        ),
        html.Div(
            style=CARD,
            children=[
                html.H3(
                    "Step Plot",
                    style={"margin": "0 0 8px 0", "fontSize": "14px", "color": "#888"},
                ),
                chart3_component,
            ],
        ),
        html.Div(
            style=CARD,
            children=[
                html.H3(
                    "Synced Stacked Bar",
                    style={"margin": "0 0 8px 0", "fontSize": "14px", "color": "#888"},
                ),
                chart4_component,
            ],
        ),
        html.Div(
            style=CARD,
            children=[
                html.H3(
                    "Declarative API",
                    style={"margin": "0 0 8px 0", "fontSize": "14px", "color": "#888"},
                ),
                chart5_component,
            ],
        ),
        html.Div(
            style=CARD,
            children=[
                html.H3(
                    "Numpy Input + Copy",
                    style={"margin": "0 0 8px 0", "fontSize": "14px", "color": "#888"},
                ),
                chart6_component,
            ],
        ),
    ],
)


@app.callback(
    Output("chart-4", "data"),
    Input("trend", "value"),
)
def update_bar_data(trend: int) -> str:
    return make_contributions_csv(float(trend))


if __name__ == "__main__":
    app.run(debug=True)
