"""dash-capture demo for dygraphs.

Renders a dygraph chart and wires up two ``capture_element`` buttons
that use :func:`dygraphs.dygraph_strategy` — one that hides the range
selector before snapshotting, one that keeps it.

Run with::

    uv run python examples/capture_demo.py

Then open http://127.0.0.1:8050 in your browser. Click a button, choose
a filename in the wizard, and download the PNG.

Requires ``dash-capture`` (``pip install dash-capture``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dash import Dash, html
from dash_capture import capture_element

from dygraphs import Dygraph, dygraph_strategy


def make_data() -> pd.DataFrame:
    np.random.seed(0)
    dates = pd.date_range("2024-01-01", periods=180, freq="D")
    return pd.DataFrame(
        {
            "Temperature": (15 + np.cumsum(np.random.randn(180) * 0.5)).round(2),
            "Humidity": (40 + np.cumsum(np.random.randn(180) * 0.4)).round(2),
        },
        index=dates,
    )


app = Dash(__name__)

chart = (
    Dygraph(make_data(), title="Temperature & Humidity")
    .options(stroke_width=2, colors=["#00d4aa", "#f4a261"])
    .legend(show="always")
    .range_selector(height=30)
)
chart_component = chart.to_dash(app=app, component_id="sensors", height="320px")

# The chart's canvas container is f"{component_id}-container".
ELEMENT_ID = "sensors-container"

CARD = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px",
}

app.layout = html.Div(
    style={
        "fontFamily": "system-ui, sans-serif",
        "maxWidth": "900px",
        "margin": "0 auto",
        "padding": "40px",
    },
    children=[
        html.H1("dygraphs + dash-capture"),
        html.P(
            "Click a Capture button to open the wizard, then download the "
            "PNG. Each button uses dygraph_strategy() with a different "
            "range-selector setting."
        ),
        html.Div(style=CARD, children=[chart_component]),
        html.Div(
            style={"display": "flex", "gap": "12px"},
            children=[
                capture_element(
                    ELEMENT_ID,
                    trigger="Capture (no range selector)",
                    strategy=dygraph_strategy(hide_range_selector=True),
                    filename="sensors.png",
                ),
                capture_element(
                    ELEMENT_ID,
                    trigger="Capture (with range selector)",
                    strategy=dygraph_strategy(hide_range_selector=False),
                    filename="sensors-with-selector.png",
                ),
            ],
        ),
    ],
)


if __name__ == "__main__":
    app.run(debug=True)
