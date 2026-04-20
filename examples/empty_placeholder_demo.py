"""Empty-placeholder demo.

Build the layout with ``DygraphChart(None, id="chart")``. The chart is a
real, id-addressable Dash component from the start, but the inner store
holds ``data=None`` and the clientside renderer early-returns on falsy
config (``dash_render.js``: ``if (!config) return;``). A dropdown
callback pushes the first real config through the store, triggering a
full destroy+recreate (same model as R's ``renderDygraph``).

Every visible change — data AND styling — flows through the single
``Output(chart, "data")`` channel. There is no separate "opts" store;
one write path, one mental model. If your app needs cheap
cosmetic-only updates without recreating the chart, see CLAUDE.md →
"Decisions deferred / opts store".

Run with: ``uv run python examples/empty_placeholder_demo.py``
"""

from __future__ import annotations

import dash
import numpy as np
import pandas as pd
from dash import Input, Output, dcc, html

from dygraphs import Dygraph
from dygraphs.dash import DygraphChart

# ---------------------------------------------------------------------------
# Pretend datasets. In a real app these would come from a DB query, an
# upload, etc. The dropdown picks one.
# ---------------------------------------------------------------------------
np.random.seed(0)
_INDEX = pd.date_range("2024-01-01", periods=120, freq="D")
DATASETS: dict[str, pd.DataFrame] = {
    "sine": pd.DataFrame(
        {"y": np.sin(np.linspace(0, 8 * np.pi, 120))}, index=_INDEX
    ),
    "random walk": pd.DataFrame(
        {"y": np.cumsum(np.random.randn(120))}, index=_INDEX
    ),
    "double": pd.DataFrame(
        {"a": np.cumsum(np.random.randn(120)), "b": np.cumsum(np.random.randn(120))},
        index=_INDEX,
    ),
}


app = dash.Dash(__name__)

# Empty placeholder — no data yet. The callback below fills it.
chart = DygraphChart(None, id="chart", height="320px")

app.layout = html.Div(
    [
        html.H2("Empty-placeholder demo"),
        html.P(
            "Pick a dataset to populate the chart. Styling changes "
            "(stroke width) ride along on the same primary-store write "
            "— no separate override channel."
        ),
        dcc.Dropdown(
            id="dataset",
            options=[{"label": name, "value": name} for name in DATASETS],
            placeholder="Pick a dataset…",
            style={"width": 300, "marginBottom": 16},
        ),
        html.Div(
            [
                html.Label("Stroke width", style={"marginRight": 8}),
                dcc.Slider(
                    id="stroke",
                    min=1,
                    max=6,
                    step=1,
                    value=2,
                    marks={i: str(i) for i in range(1, 7)},
                ),
            ],
            style={"width": 360, "marginBottom": 16},
        ),
        chart,
    ]
)


@dash.callback(
    Output(chart, "data"),
    Input("dataset", "value"),
    Input("stroke", "value"),
    prevent_initial_call=True,
)
def populate(name: str | None, stroke: int) -> dict | None:
    if not name:
        return None  # cleared dropdown → back to empty state
    df = DATASETS[name]
    # ``to_js()`` is ``to_dict()`` with embedded ``JS(code)`` objects
    # replaced by ``"__JS__:code:__JS__"`` string markers — Dash can
    # ship those over the wire, and the clientside renderer
    # evaluates them back to real JS at render time. Using plain
    # ``to_dict()`` here would hit ``InvalidCallbackReturnValue``
    # because the config carries e.g. ``Dygraph.Interaction.defaultModel``
    # as a ``JS`` object.
    return (
        Dygraph(df, title=name)
        .options(stroke_width=stroke)
        .range_selector(height=30)
        .to_js()
    )


if __name__ == "__main__":
    app.run(debug=True)
