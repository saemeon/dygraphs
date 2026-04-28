"""Demo of full-fidelity dygraph capture (canvas + HTML overlays).

``dygraph_strategy()`` composites every visible ``<canvas>`` inside a
chart and rasterises the HTML overlay layer (chart title, x/y axis
labels, tick labels, legend, annotations) via the vendored
``html2canvas`` from ``dash-capture``. Result: a PNG that matches what
the user sees, with no missing chrome.

To stress-test, the chart below has every kind of HTML overlay
dygraphs emits:

* ``main`` chart title
* ``xlab`` / ``ylab`` (the y-label is CSS-rotated 90°)
* per-axis tick labels (positioned ``<div>``s)
* always-on legend
* an ``annotation`` and an ``event`` line label

Run with::

    uv run python examples/capture_overlays_demo.py

Then open http://127.0.0.1:8050, click the Capture button (or use the
modebar camera icon top-right of the chart on hover), and download the
PNG. Requires ``dash-capture``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dash import Dash, html
from dash_capture import capture_element

from dygraphs import Dygraph
from dygraphs.dash import DygraphChart, dygraph_strategy


def make_data() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    dates = pd.date_range("2024-01-01", periods=180, freq="D")
    return pd.DataFrame(
        {
            "Temperature": (15 + np.cumsum(rng.standard_normal(180) * 0.5)).round(2),
            "Humidity": (40 + np.cumsum(rng.standard_normal(180) * 0.4)).round(2),
        },
        index=dates,
    )


df = make_data()
midpoint = df.index[len(df) // 2]
peak_idx = df["Temperature"].idxmax()

chart = (
    Dygraph(
        df,
        title="Sensors — overlay-capture demo",
        xlab="Date",
        ylab="Reading",
    )
    .options(stroke_width=2, colors=["#00d4aa", "#f4a261"], include_zero=False)
    .legend(show="always", labels_separate_lines=True)
    .annotation(series="Temperature", x=peak_idx, text="P", tooltip="Peak temperature")
    .event(x=midpoint, label="midpoint", color="#888")
    .range_selector(height=30)
)
chart_component = DygraphChart(figure=chart, id="sensors", height="380px")

ELEMENT_ID = "sensors-container"

CARD = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px",
}

app = Dash(__name__)

app.layout = html.Div(
    style={
        "fontFamily": "system-ui, sans-serif",
        "maxWidth": "960px",
        "margin": "0 auto",
        "padding": "40px",
    },
    children=[
        html.H1("dygraphs capture — full chart with overlays"),
        html.P(
            "The chart below has every kind of overlay dygraphs emits "
            "(title, axis labels, tick labels, legend, annotation, event "
            "line). Click Capture (or the modebar camera icon) and the "
            "downloaded PNG will include all of it."
        ),
        html.Div(style=CARD, children=[chart_component]),
        capture_element(
            ELEMENT_ID,
            trigger="Capture PNG",
            strategy=dygraph_strategy(),
            filename="sensors.png",
        ),
    ],
)


if __name__ == "__main__":
    app.run(debug=True)
