"""Demo: what you can ``Output`` from a single Dash callback.

A single dropdown drives one server-side callback that overwrites
**seven** different properties across seven different component types
in one shot — including a Dygraph chart's data store.

Run with::

    uv run python examples/callback_outputs_demo.py

Then open http://127.0.0.1:8050 and switch trends from the dropdown.

Outputs demonstrated
--------------------
1. ``dcc.Store.data``                 — chart data store (drives the chart)
2. ``html.Div.children``              — status text
3. ``html.Div.style``                 — status background colour
4. ``dcc.Input.value``                — text input value
5. ``dcc.Dropdown.options``           — repopulate a second dropdown
6. ``html.Button.disabled``           — gate a button
7. ``dash_table.DataTable.data``      — refresh a table

Any other component prop works the same way — Dash treats every prop
as an observable Output target.
"""

from __future__ import annotations

import dash
import numpy as np
import pandas as pd
from dash import Input, Output, dash_table, dcc, html

from dygraphs import Dygraph
from dygraphs.dash import DygraphChart


def make_data(trend: float, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=120, freq="D")
    return pd.DataFrame(
        {
            "Series": (10 + np.cumsum(trend + rng.standard_normal(120) * 0.5)).round(2),
        },
        index=dates,
    )


# ---------------------------------------------------------------------------
# App + initial chart
# ---------------------------------------------------------------------------

app = dash.Dash(__name__)

initial_chart = (
    Dygraph(make_data(0.0), title="Trend = 0")
    .options(stroke_width=2, colors=["#00d4aa"])
    .legend(show="always")
)
chart_component = DygraphChart(figure=initial_chart, id="chart", height="280px")

# Layout — note IDs we'll target as Outputs
TREND_OPTS = [
    {"label": "Strong down (-2)", "value": -2},
    {"label": "Mild down (-1)", "value": -1},
    {"label": "Flat (0)", "value": 0},
    {"label": "Mild up (+1)", "value": 1},
    {"label": "Strong up (+2)", "value": 2},
]

CARD = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px",
}

app.layout = html.Div(
    style={
        "maxWidth": "900px",
        "margin": "0 auto",
        "padding": "40px",
        "fontFamily": "system-ui, sans-serif",
    },
    children=[
        html.H1("One callback → many Output props"),
        html.P(
            "Switching the trend dropdown fires ONE callback whose return "
            "value updates seven different props across seven component "
            "types. The chart, the status banner, the table, the second "
            "dropdown, the text input, and the button are all driven by "
            "the same return tuple."
        ),
        html.Label("Trend:"),
        dcc.Dropdown(
            id="trend",
            options=TREND_OPTS,
            value=0,
            clearable=False,
            style={"width": "260px", "marginBottom": "16px"},
        ),
        # 1: chart store lives inside chart_component
        html.Div(style=CARD, children=[chart_component]),
        # 3 + 4: status banner — children + style
        html.Div(
            id="status",
            style={
                "padding": "12px",
                "borderRadius": "6px",
                "backgroundColor": "#e8f5e9",
                "marginBottom": "16px",
            },
            children="Pick a trend",
        ),
        # 5: input value
        html.Label("Generated label:"),
        dcc.Input(id="label-input", type="text", style={"marginBottom": "16px"}),
        # 6: dropdown options
        html.Label("Suggested presets:"),
        dcc.Dropdown(
            id="presets",
            options=[],
            placeholder="(choose a trend first)",
            style={"width": "260px", "marginBottom": "16px"},
        ),
        # 7: button disabled
        html.Button(
            "Apply preset",
            id="apply-btn",
            disabled=True,
            style={"marginBottom": "16px"},
        ),
        # 8: table data
        dash_table.DataTable(
            id="summary-table",
            columns=[{"name": c, "id": c} for c in ("metric", "value")],
            data=[],
            style_table={"width": "260px"},
            style_cell={"padding": "6px"},
        ),
    ],
)


# ---------------------------------------------------------------------------
# Single callback, seven outputs
# ---------------------------------------------------------------------------


@dash.callback(
    # 1. Chart data store — drives the dygraph re-render
    Output("chart", "data"),
    # 2. Status banner text
    Output("status", "children"),
    # 3. Status banner background
    Output("status", "style"),
    # 4. Text input value
    Output("label-input", "value"),
    # 5. Second dropdown options
    Output("presets", "options"),
    # 6. Button disabled flag
    Output("apply-btn", "disabled"),
    # 7. Table rows
    Output("summary-table", "data"),
    Input("trend", "value"),
)
def on_trend_change(trend: int) -> tuple:
    df = make_data(float(trend))

    # 1. Build a fresh dygraph config and ship it to the store.
    # Everything about the chart — data AND styling — flows through
    # this single write.
    new_chart = Dygraph(df, title=f"Trend = {trend:+d}").options(
        stroke_width=2,
        colors=["#00d4aa" if trend >= 0 else "#e74c3c"],
        show_labels_on_highlight=trend != 0,
    )
    chart_data = new_chart.to_js()

    # 2 + 3. status banner
    if trend > 0:
        status_text = f"Uptrend selected ({trend:+d})"
        status_style = {
            "padding": "12px",
            "borderRadius": "6px",
            "backgroundColor": "#e8f5e9",
            "marginBottom": "16px",
        }
    elif trend < 0:
        status_text = f"Downtrend selected ({trend:+d})"
        status_style = {
            "padding": "12px",
            "borderRadius": "6px",
            "backgroundColor": "#ffebee",
            "marginBottom": "16px",
        }
    else:
        status_text = "Flat — no trend"
        status_style = {
            "padding": "12px",
            "borderRadius": "6px",
            "backgroundColor": "#f5f5f5",
            "marginBottom": "16px",
        }

    # 4. text input value
    label_value = f"trend_{trend:+d}"

    # 5. populate the second dropdown's options dynamically
    preset_options = [
        {"label": f"Preset A (trend {trend:+d})", "value": f"a-{trend}"},
        {"label": f"Preset B (trend {trend:+d})", "value": f"b-{trend}"},
    ]

    # 6. enable the button only when there's a non-flat trend
    apply_disabled = trend == 0

    # 7. table summary stats
    series = df["Series"]
    table_rows = [
        {"metric": "min", "value": round(float(series.min()), 2)},
        {"metric": "max", "value": round(float(series.max()), 2)},
        {"metric": "mean", "value": round(float(series.mean()), 2)},
        {"metric": "last", "value": round(float(series.iloc[-1]), 2)},
    ]

    return (
        chart_data,
        status_text,
        status_style,
        label_value,
        preset_options,
        apply_disabled,
        table_rows,
    )


if __name__ == "__main__":
    app.run(debug=True)
