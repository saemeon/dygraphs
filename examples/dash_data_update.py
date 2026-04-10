"""Interactive Dash demo — update a dygraph chart from server callbacks.

Shows the two canonical update paths for a chart rendered via
``Dygraph.to_dash()``:

1. **Full refresh** — ``data("chart-id")`` targets the chart's data
   store. Writing a fresh ``Dygraph.to_dict()`` payload there destroys
   and recreates the chart with the new data + attributes. Use this
   when the underlying data changes.
2. **Options override** — ``opts("chart-id")`` targets the runtime
   options store. Writing a partial dict there merges on top of the
   existing config without reshipping the data. Use this to toggle
   display options (stroke width, colours, legend, ...) without the
   bandwidth cost of retransmitting the data array.

The ``data`` and ``opts`` helpers come from ``dygraphs.dash`` and
save you from hand-building the magic-id strings (``"<cid>-store"``
and ``"<cid>-opts"``) every time. Both return the right
``dash.Output`` object for a given component id.

Run with::

    uv run python examples/dash_data_update.py

Then open http://127.0.0.1:8050 and:

- Click the data-source buttons to swap the chart between random
  walk, sine wave, and exponential decay. Each button shows the
  ``data("chart")`` update path.
- Drag the stroke-width slider or pick a colour from the swatches to
  see the ``opts("chart")`` update path — the data stays put, only
  the display changes.
- Notice the chart keeps its current x-axis zoom across data updates
  because the initial chart sets ``retain_date_window=True``.
"""

from __future__ import annotations

import dash
import numpy as np
import pandas as pd
from dash import Input, dcc, html

from dygraphs import Dygraph
from dygraphs.dash import data, opts

# ---------------------------------------------------------------------------
# Data sources — each returns a 180-point DataFrame with the same index
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2024-01-01", periods=180, freq="D")


def _random_walk(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {"y": (20 + np.cumsum(rng.standard_normal(180) * 0.8)).round(2)},
        index=_DATES,
    )


def _sine_wave() -> pd.DataFrame:
    t = np.linspace(0, 8 * np.pi, 180)
    return pd.DataFrame({"y": (20 + 6 * np.sin(t)).round(2)}, index=_DATES)


def _exponential_decay() -> pd.DataFrame:
    t = np.linspace(0, 5, 180)
    return pd.DataFrame({"y": (50 * np.exp(-t / 2) + 5).round(2)}, index=_DATES)


_DATA_SOURCES = {
    "random": ("Random walk", _random_walk, "#00d4aa"),
    "sine": ("Sine wave", _sine_wave, "#f4a261"),
    "expon": ("Exponential decay", _exponential_decay, "#7eb8f7"),
}

# ---------------------------------------------------------------------------
# Initial chart
# ---------------------------------------------------------------------------

app = dash.Dash(__name__)

_initial_df = _random_walk()
initial_chart = (
    Dygraph(_initial_df, title="Random walk")
    # retain_date_window=True preserves the user's x-axis zoom across
    # data updates — without it, each update resets to the full range.
    .options(retain_date_window=True, stroke_width=2, colors=["#00d4aa"])
    .range_selector(height=30)
    .legend(show="always")
)
chart_component = initial_chart.to_dash(app=app, component_id="chart", height="320px")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

_CARD = {
    "background": "#ffffff",
    "borderRadius": "10px",
    "padding": "20px",
    "marginBottom": "16px",
    "boxShadow": "0 1px 4px rgba(0,0,0,0.08)",
}

_COLOURS = [
    ("#00d4aa", "Teal"),
    ("#f4a261", "Orange"),
    ("#7eb8f7", "Blue"),
    ("#f76e8a", "Pink"),
    ("#c084fc", "Purple"),
]

app.layout = html.Div(
    style={
        "maxWidth": "900px",
        "margin": "0 auto",
        "padding": "40px 24px",
        "fontFamily": "system-ui, -apple-system, sans-serif",
        "background": "#f7f7f9",
        "minHeight": "100vh",
    },
    children=[
        html.H1("Interactive dygraphs in Dash"),
        html.P(
            [
                "Two update paths demonstrated side-by-side: the ",
                html.Code("data()"),
                " helper for full refreshes (destroy + recreate) and the ",
                html.Code("opts()"),
                " helper for runtime overrides (merge without reshipping data).",
            ]
        ),
        # Chart card
        html.Div(style=_CARD, children=[chart_component]),
        # Data source buttons — demonstrate the data() helper
        html.Div(
            style=_CARD,
            children=[
                html.H3("Swap data source", style={"marginTop": 0}),
                html.P(
                    [
                        "Each button fires a callback that writes a ",
                        "fresh ",
                        html.Code("Dygraph.to_dict()"),
                        " to ",
                        html.Code('data("chart")'),
                        " — the chart is destroyed and recreated with "
                        "the new data and attributes.",
                    ],
                    style={"color": "#666", "fontSize": "14px"},
                ),
                html.Div(
                    style={"display": "flex", "gap": "8px"},
                    children=[
                        html.Button(
                            label,
                            id=f"btn-{key}",
                            n_clicks=0,
                            style={
                                "padding": "10px 16px",
                                "border": "1px solid #ddd",
                                "borderRadius": "6px",
                                "background": "#fff",
                                "cursor": "pointer",
                                "fontSize": "14px",
                            },
                        )
                        for key, (label, _, _) in _DATA_SOURCES.items()
                    ],
                ),
            ],
        ),
        # Runtime options — demonstrate the opts() helper
        html.Div(
            style=_CARD,
            children=[
                html.H3("Tweak runtime options", style={"marginTop": 0}),
                html.P(
                    [
                        "The stroke-width slider and colour picker fire ",
                        "callbacks that write partial dicts to ",
                        html.Code('opts("chart")'),
                        " — the data stays put, only the visual options ",
                        "change. No bandwidth spent reshipping the 180 ",
                        "data points.",
                    ],
                    style={"color": "#666", "fontSize": "14px"},
                ),
                html.Label("Stroke width:", style={"fontWeight": 500}),
                dcc.Slider(
                    id="stroke-width",
                    min=1,
                    max=6,
                    step=1,
                    value=2,
                    marks={i: str(i) for i in range(1, 7)},
                ),
                html.Label(
                    "Colour:",
                    style={
                        "fontWeight": 500,
                        "display": "block",
                        "marginTop": "12px",
                    },
                ),
                dcc.RadioItems(
                    id="colour",
                    options=[{"label": name, "value": hex} for hex, name in _COLOURS],
                    value="#00d4aa",
                    inline=True,
                    labelStyle={"marginRight": "14px"},
                ),
            ],
        ),
    ],
)

# ---------------------------------------------------------------------------
# Callbacks — three callbacks, each showing one update path
# ---------------------------------------------------------------------------


@app.callback(
    # data("chart") is sugar for Output("chart-store", "data"). Full refresh.
    data("chart"),
    Input("btn-random", "n_clicks"),
    Input("btn-sine", "n_clicks"),
    Input("btn-expon", "n_clicks"),
    prevent_initial_call=True,
)
def on_data_source_change(_r: int, _s: int, _e: int) -> dict:
    """Button click -> rebuild the chart with the new data source.

    We look up which button triggered this callback via the Dash
    ``ctx.triggered_id`` API, then build a fresh Dygraph and return
    its serialised dict. The chart's clientside renderer sees the
    store update, destroys the old dygraph, and creates a new one
    with the new data.
    """
    triggered = dash.ctx.triggered_id
    if triggered is None:
        return dash.no_update

    key = triggered.removeprefix("btn-")
    label, builder, colour = _DATA_SOURCES[key]
    return (
        Dygraph(builder(), title=label)
        .options(retain_date_window=True, stroke_width=2, colors=[colour])
        .range_selector(height=30)
        .legend(show="always")
        .to_dict()
    )


@app.callback(
    # opts("chart") is sugar for Output("chart-opts", "data"). Overrides only.
    opts("chart"),
    Input("stroke-width", "value"),
    Input("colour", "value"),
)
def on_runtime_option_change(stroke_width: int, colour: str) -> dict:
    """Slider or colour change -> merge a runtime override.

    Returning a dict from this callback writes it to the opts store;
    the clientside renderer merges it on top of the existing config
    without touching the data. The dygraphs JS property names are
    camelCase here (``strokeWidth``, ``colors``) because the override
    is applied post-serialisation — no snake_case translation happens.
    """
    return {"strokeWidth": stroke_width, "colors": [colour]}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    app.run(debug=False)
