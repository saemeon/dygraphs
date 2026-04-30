"""Target-size dygraph capture — fit a chart into a report layout.

Run::

    uv run python examples/capture_target_size_demo.py

Then open http://127.0.0.1:8050, click "Capture for report", and pick
the width / height that matches your report's chart slot. The
downloaded PNG is rendered at exactly that size — not a bitmap zoom of
the live render. Dygraphs's ``ResizeObserver`` redraws the canvases at
the new aspect, axis ticks rebalance, the legend re-positions, and
``html2canvas`` snapshots the freshly-laid-out chart. Original styles
are restored after capture, so the live view is unchanged.

How it's wired
--------------
The renderer declares ``capture_width`` / ``capture_height``. Those
are excluded from the auto-generated form (they're a wire-protocol to
the strategy), so the wizard exposes plain ``width`` / ``height``
fields and a ``capture_resolver`` translates one to the other.
``capture_element`` auto-wires the renderer's params into the
strategy, so ``dygraph_strategy()`` "just works" without explicit
``_params=...`` plumbing.
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

chart = (
    Dygraph(df, title="Quarterly metrics", xlab="Date", ylab="Index (base = 100)")
    .options(
        stroke_width=2,
        colors=["#1f77b4", "#d62728", "#2ca02c"],
        include_zero=False,
    )
    .legend(show="always", labels_separate_lines=True)
    .annotation(series="Revenue", x=peak, text="P", tooltip="Peak")
)
chart_component = DygraphChart(figure=chart, id="metrics", height="320px")

ELEMENT_ID = "metrics-container"


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
    """Composite a title bar onto the captured chart.

    Field roles (proven by which fields hit the cache):

    - ``width`` / ``height`` are dimensional — they go through
      ``capture_resolver`` and ARE part of the cache key. Editing them
      forces a fresh JS capture (chart reflows, ResizeObserver redraws).
    - ``title`` is non-dimensional — only used here, in Python. The
      cache hash doesn't see it, so editing the title reuses the prior
      browser-side capture and just re-composites the title bar.
      You can confirm by watching the live chart: it flickers when you
      change width/height, but stays still when you only change title.
    """
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

app = Dash(__name__)

app.layout = html.Div(
    style={
        "fontFamily": "system-ui, sans-serif",
        "maxWidth": "960px",
        "margin": "0 auto",
        "padding": "40px",
    },
    children=[
        html.H1("dygraphs — target-size capture for reports"),
        html.P(
            "The live chart below is 320px tall. Click 'Capture for "
            "report', set the width and height to fit your report "
            "slot, and the downloaded PNG will be rendered at exactly "
            "those dimensions — ticks rebalanced, legend repositioned, "
            "no bitmap-zoom blur."
        ),
        html.Div(style=CARD, children=[chart_component]),
        # Wizard triggered by an extra button injected into the chart's
        # built-in modebar. ``DyModebarButton`` exposes the bridge protocol
        # that ``capture_element`` recognises, so the bridge gets folded
        # into the wizard component automatically — no hidden html.Button
        # in the layout.
        capture_element(
            ELEMENT_ID,
            renderer=renderer,
            capture_resolver=resolve,
            trigger=DyModebarButton(graph_id="metrics", label="Save as report"),
            strategy=dygraph_strategy(),
            filename="metrics-report.png",
        ),
    ],
)


if __name__ == "__main__":
    app.run(debug=False)
