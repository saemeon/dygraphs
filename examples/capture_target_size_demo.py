"""Target-size dygraph capture — fit a chart into a report layout.

Run::

    uv run python examples/capture_target_size_demo.py

Then open http://127.0.0.1:8050 and click the "Save" button on each chart
to download a PNG. The downloaded PNG is rendered at exactly the chosen size
— not a bitmap zoom of the live render. Dygraphs's ``ResizeObserver`` redraws
the canvases at the new aspect, axis ticks rebalance, the legend re-positions,
and ``html2canvas`` snapshots the freshly-laid-out chart.

The three examples show how ``.axis()`` options control spacing:
- Chart 1: default layout with full margins and axis labels
- Chart 2: remove CSS margins with `strip_margin=True`, hide axis labels
- Chart 3: tune ``axis_label_width`` (controls tick label space)

Adjust ``axis_label_width`` to match your data's label widths (e.g., "100"
is smaller than "1000000"). No automatic sizing exists — it's a fixed
pixel allocation that you tune per dataset.
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
from dash import Dash, html
from dash_capture import capture_element
from PIL import Image, ImageDraw, ImageFont

from dygraphs import Dygraph
from dygraphs.dash import DygraphChart, DyModebarButton, dygraph_strategy


def make_data() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    dates = pd.date_range("2024-01-01", periods=180, freq="D")
    return pd.DataFrame(
        {
            "Revenue": (100 + np.cumsum(rng.standard_normal(180) * 0.7)).round(2),
            "Cost": (80 + np.cumsum(rng.standard_normal(180) * 0.5)).round(2),
            "Forecast": (110 + np.cumsum(rng.standard_normal(180) * 0.4)).round(2),
        },
        index=dates,
    )


df = make_data()
peak = df["Revenue"].idxmax()


def make_base_chart(title: str) -> Dygraph:
    """Base chart with default styling."""
    dg = Dygraph(df, title=title, xlab="Date", ylab="Index")
    return (
        dg.options(
            stroke_width=2,
            colors=["#1f77b4", "#d62728", "#2ca02c"],
            include_zero=False,
        )
        .legend(show="always", labels_separate_lines=True)
        .annotation(series="Revenue", x=peak, text="P", tooltip="Peak")
    )


chart_default = make_base_chart("Default layout")
chart_compact = make_base_chart("Compact (no labels)").axis(
    "x", label="", label_height=0
).axis("y", label="", label_width=0)
chart_tuned = make_base_chart("Custom axis spacing").axis(
    "y", label="", label_width=0, axis_label_width=30
)

chart_default_component = DygraphChart(
    figure=chart_default, id="metrics-default", height="320px"
)
chart_compact_component = DygraphChart(
    figure=chart_compact, id="metrics-compact", height="320px"
)
chart_tuned_component = DygraphChart(
    figure=chart_tuned, id="metrics-tuned", height="320px"
)


# ---------------------------------------------------------------------------
# Renderer + resolver
# ---------------------------------------------------------------------------


def renderer(
    _target,
    _snapshot_img,
    title: str = "Quarterly metrics — report draft",
    width: int = 1200,
    height: int = 600,
    capture_width: int = 1200,
    capture_height: int = 600,
):
    """Composite a title bar onto the captured chart."""
    img = Image.open(io.BytesIO(_snapshot_img()))
    bar_h = 48
    out = Image.new("RGB", (img.width, img.height + bar_h), "white")
    out.paste(img, (0, bar_h))
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("Helvetica", 22)
    except OSError:
        font = ImageFont.load_default()
    draw.text((16, 12), title, fill="black", font=font)
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    _target.write(buf.getvalue())


def resolve(width, height, **_):
    """Drives the cache key. ``title`` is intentionally absent."""
    return {"capture_width": width, "capture_height": height}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

CARD = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px",
}

COLUMN = {
    "flex": "1",
    "minWidth": "300px",
}

app = Dash(__name__)

app.layout = html.Div(
    style={
        "fontFamily": "system-ui, sans-serif",
        "maxWidth": "1400px",
        "margin": "0 auto",
        "padding": "40px",
    },
    children=[
        html.H1("dygraphs — axis label sizing for chart exports"),
        html.P(
            "Click 'Save' on each chart to download a PNG at your chosen size. "
            "The key to fitting charts into report layouts is controlling axis label space with .axis() options. "
            "Tune axis_label_width to match your data's label widths (e.g., '100' vs '1000000')."
        ),
        html.Div(
            style={"display": "flex", "gap": "20px", "flexWrap": "wrap"},
            children=[
                html.Div(
                    style={**COLUMN},
                    children=[
                        html.H3("Chart 1: Default"),
                        html.Div(style=CARD, children=[chart_default_component]),
                        capture_element(
                            "metrics-default-container",
                            renderer=renderer,
                            capture_resolver=resolve,
                            trigger=DyModebarButton(
                                graph_id="metrics-default", tooltip="Save"
                            ),
                            strategy=dygraph_strategy(strip_margin=False),
                            filename="chart-default.png",
                        ),
                    ],
                ),
                html.Div(
                    style={**COLUMN},
                    children=[
                        html.H3("Chart 2: Compact (no labels)"),
                        html.Div(style=CARD, children=[chart_compact_component]),
                        html.P(
                            "Removes x/y label divs with label_height=0, label_width=0",
                            style={"fontSize": "12px", "color": "#666"},
                        ),
                        capture_element(
                            "metrics-compact-container",
                            renderer=renderer,
                            capture_resolver=resolve,
                            trigger=DyModebarButton(
                                graph_id="metrics-compact", tooltip="Save"
                            ),
                            strategy=dygraph_strategy(strip_margin=True),
                            filename="chart-compact.png",
                        ),
                    ],
                ),
                html.Div(
                    style={**COLUMN},
                    children=[
                        html.H3("Chart 3: Custom axis spacing"),
                        html.Div(style=CARD, children=[chart_tuned_component]),
                        html.P(
                            "Tune axis_label_width=30 for your data's label widths",
                            style={"fontSize": "12px", "color": "#666"},
                        ),
                        capture_element(
                            "metrics-tuned-container",
                            renderer=renderer,
                            capture_resolver=resolve,
                            trigger=DyModebarButton(
                                graph_id="metrics-tuned", tooltip="Save"
                            ),
                            strategy=dygraph_strategy(strip_margin=True),
                            filename="chart-tuned.png",
                        ),
                    ],
                ),
            ],
        ),
    ],
)


if __name__ == "__main__":
    app.run(debug=False)
