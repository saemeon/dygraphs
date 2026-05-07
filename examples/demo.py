"""dygraphs + dash-capture — unified demo.

Four sections, each demonstrating one capture concern. Run with::

    uv run python examples/capture_demo.py

Then open http://127.0.0.1:8050.

1. **Basic capture.** Two buttons (range selector hidden vs kept).
2. **Full overlays.** A chart with every kind of HTML overlay dygraphs
   emits (title, axis labels, tick labels, legend, annotation, event
   line). Confirms html2canvas composites everything correctly.
3. **Target-size export.** User picks width / height in the wizard,
   chart resizes live and the captured PNG is at exactly that size.
   The renderer draws a 2px black border + size caption so the saved
   pixels are easy to verify.
4. **Axis spacing trio.** Three side-by-side charts showing how
   ``.axis()`` options (default / no labels / tuned label_width)
   change the captured layout at the same target size.

Requires ``dash-capture`` (``pip install dash-capture``).
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
from dash import Dash, html
from dash_capture import capture_element
from PIL import Image, ImageDraw

from dygraphs import Dygraph
from dygraphs.dash import DygraphChart, DyModebarButton, dygraph_strategy

# ---------------------------------------------------------------------------
# Shared data + styles
# ---------------------------------------------------------------------------


def make_data(seed: int = 0, n: int = 180) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "Temperature": (15 + np.cumsum(rng.standard_normal(n) * 0.5)).round(2),
            "Humidity": (40 + np.cumsum(rng.standard_normal(n) * 0.4)).round(2),
        },
        index=dates,
    )


df = make_data()
peak_idx = df["Temperature"].idxmax()
midpoint = df.index[len(df) // 2]

CARD = {
    "backgroundColor": "#f8f9fa",
    "borderRadius": "12px",
    "padding": "20px",
    "marginBottom": "16px",
}
COLUMN = {"flex": "1", "minWidth": "300px"}

# ---------------------------------------------------------------------------
# Renderers (shared)
# ---------------------------------------------------------------------------


def passthrough(_target, _snapshot_img):
    """No-frills renderer — write the PNG bytes through verbatim."""
    _target.write(_snapshot_img())


def bordered(
    _target,
    _snapshot_img,
    width: int = 1200,
    height: int = 400,
    capture_width: int = 1200,
    capture_height: int = 400,
):
    """Draw a 2px black border + a caption with the actual pixel size,
    so the saved PNG makes the captured size visible at a glance.
    """
    img = Image.open(io.BytesIO(_snapshot_img())).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (img.width - 1, img.height - 1)], outline="black", width=2)
    caption = (
        f"captured: {img.width} x {img.height}  |  "
        f"requested: {capture_width} x {capture_height}"
    )
    draw.text((6, 6), caption, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    _target.write(buf.getvalue())


def resolve_wh(width: int = 1200, height: int = 400, **_):
    return {"capture_width": width, "capture_height": height}


# ---------------------------------------------------------------------------
# Section 1 — basic capture (with / without range selector)
# ---------------------------------------------------------------------------

basic_chart = (
    Dygraph(df, title="Temperature & Humidity")
    .options(stroke_width=2, colors=["#00d4aa", "#f4a261"])
    .legend(show="always")
    .range_selector(height=30)
)
basic_component = DygraphChart(figure=basic_chart, id="basic", height="320px")

# ---------------------------------------------------------------------------
# Section 2 — full overlays (title + axes + legend + annotation + event)
# ---------------------------------------------------------------------------

overlays_chart = (
    Dygraph(df, title="Sensors — overlay-capture demo", xlab="Date", ylab="Reading")
    .options(stroke_width=2, colors=["#00d4aa", "#f4a261"], include_zero=False)
    .legend(show="always", labels_separate_lines=True)
    .annotation(series="Temperature", x=peak_idx, text="P", tooltip="Peak temperature")
    .event(x=midpoint, label="midpoint", color="#888")
    .range_selector(height=30)
)
overlays_component = DygraphChart(figure=overlays_chart, id="overlays", height="380px")

# ---------------------------------------------------------------------------
# Section 3 — target-size export (user picks width/height)
# ---------------------------------------------------------------------------
sized_chart = (
    Dygraph(df, title="Pick width & height in the wizard")
    .options(stroke_width=2, colors=["#1f77b4", "#d62728"], include_zero=False)
    .legend(show="always", labels_separate_lines=True)
    .range_selector(height=30)
)
sized_component = DygraphChart(figure=sized_chart, id="sized", height="400px")

# ---------------------------------------------------------------------------
# Section 4 — axis-spacing trio (same target size, different axis options)
# ---------------------------------------------------------------------------


def make_axis_chart(title: str) -> Dygraph:
    return (
        Dygraph(df, title=title, xlab="Date", ylab="Index")
        .options(
            stroke_width=2,
            colors=["#1f77b4", "#d62728"],
            include_zero=False,
        )
        .legend(show="always", labels_separate_lines=True)
        .annotation(series="Temperature", x=peak_idx, text="P", tooltip="Peak")
    )


axis_default = make_axis_chart("Default")
axis_compact = (
    make_axis_chart("Compact (no labels)")
    .axis("x", label="", label_height=0)
    .axis("y", label="", label_width=0)
)
axis_tuned = make_axis_chart("Tuned axis_label_width=30").axis(
    "y", label="", label_width=0, axis_label_width=30
)

axis_default_component = DygraphChart(axis_default, id="axis-default", height="320px")
axis_compact_component = DygraphChart(axis_compact, id="axis-compact", height="320px")
axis_tuned_component = DygraphChart(axis_tuned, id="axis-tuned", height="320px")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = Dash(__name__)

app.layout = html.Div(
    style={
        "fontFamily": "system-ui, sans-serif",
        "maxWidth": "1400px",
        "margin": "0 auto",
        "padding": "40px",
    },
    children=[
        html.H1("dygraphs + dash-capture — unified demo"),
        # --- Section 1 ---
        html.H2("1. Basic capture"),
        html.P(
            "Two buttons: one hides the range selector during capture "
            "(default), one keeps it. The hide path uses dygraphs' own "
            "showRangeSelector option toggle so the plot fills the freed "
            "space — no white strip, no cropping."
        ),
        html.Div(style=CARD, children=[basic_component]),
        html.Div(
            style={"display": "flex", "gap": "12px"},
            children=[
                capture_element(
                    "basic-container",
                    trigger="Capture (no range selector)",
                    strategy=dygraph_strategy(hide_range_selector=True),
                    filename="basic-no-rs.png",
                ),
                capture_element(
                    "basic-container",
                    trigger="Capture (with range selector)",
                    strategy=dygraph_strategy(hide_range_selector=False),
                    filename="basic-with-rs.png",
                ),
            ],
        ),
        # --- Section 2 ---
        html.H2("2. Full overlays"),
        html.P(
            "Title, x/y axis labels, tick labels, always-on legend, an "
            "annotation, and an event line. Captured PNG includes all of "
            "it — html2canvas rasterises the HTML overlay layer at "
            "devicePixelRatio so text stays crisp."
        ),
        html.Div(style=CARD, children=[overlays_component]),
        capture_element(
            "overlays-container",
            trigger="Capture PNG",
            strategy=dygraph_strategy(),
            filename="overlays.png",
        ),
        # --- Section 3 ---
        html.H2("3. Target-size export"),
        html.P(
            "Click Save and pick width / height in the wizard. The chart "
            "resizes live and the captured PNG is at exactly that size. "
            "The bordered renderer stamps a black frame + caption so you "
            "can confirm the captured pixels match what you asked for."
        ),
        html.Div(style=CARD, children=[sized_component]),
        capture_element(
            "sized-container",
            renderer=bordered,
            capture_resolver=resolve_wh,
            trigger=DyModebarButton(graph_id="sized", tooltip="Save"),
            strategy=dygraph_strategy(strip_margin=True),
            filename="sized.png",
        ),
        # --- Section 4 ---
        html.H2("4. Axis-spacing trio"),
        html.P(
            "Same data, same target size — different .axis() options. "
            "Tune axis_label_width to your data's tick widths (e.g. '100' "
            "vs '1000000') so the plot area fills the captured PNG."
        ),
        html.Div(
            style={"display": "flex", "gap": "20px", "flexWrap": "wrap"},
            children=[
                html.Div(
                    style={**COLUMN},
                    children=[
                        html.H3("Default"),
                        html.Div(style=CARD, children=[axis_default_component]),
                        capture_element(
                            "axis-default-container",
                            renderer=bordered,
                            capture_resolver=resolve_wh,
                            trigger=DyModebarButton(
                                graph_id="axis-default", tooltip="Save"
                            ),
                            strategy=dygraph_strategy(strip_margin=False),
                            filename="axis-default.png",
                        ),
                    ],
                ),
                html.Div(
                    style={**COLUMN},
                    children=[
                        html.H3("Compact (no labels)"),
                        html.Div(style=CARD, children=[axis_compact_component]),
                        html.P(
                            "label_height=0, label_width=0 removes the "
                            "label divs entirely.",
                            style={"fontSize": "12px", "color": "#666"},
                        ),
                        capture_element(
                            "axis-compact-container",
                            renderer=bordered,
                            capture_resolver=resolve_wh,
                            trigger=DyModebarButton(
                                graph_id="axis-compact", tooltip="Save"
                            ),
                            strategy=dygraph_strategy(strip_margin=True),
                            filename="axis-compact.png",
                        ),
                    ],
                ),
                html.Div(
                    style={**COLUMN},
                    children=[
                        html.H3("Tuned axis_label_width"),
                        html.Div(style=CARD, children=[axis_tuned_component]),
                        html.P(
                            "Tighter axis_label_width=30 reclaims plot "
                            "space for narrow tick labels.",
                            style={"fontSize": "12px", "color": "#666"},
                        ),
                        capture_element(
                            "axis-tuned-container",
                            renderer=bordered,
                            capture_resolver=resolve_wh,
                            trigger=DyModebarButton(
                                graph_id="axis-tuned", tooltip="Save"
                            ),
                            strategy=dygraph_strategy(strip_margin=True),
                            filename="axis-tuned.png",
                        ),
                    ],
                ),
            ],
        ),
    ],
)


if __name__ == "__main__":
    app.run(debug=True)
