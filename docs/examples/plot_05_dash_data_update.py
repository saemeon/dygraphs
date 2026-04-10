"""
Interactive Dash: update chart data from callbacks
==================================================

dygraphs charts in Dash follow the `R htmlwidgets
<https://www.htmlwidgets.org/>`_ model: every config update
destroys the existing chart instance and creates a new one. There
is exactly **one** update path — no "did I forget to invalidate X"
bugs to track.

Each chart produced by :meth:`Dygraph.to_dash` is backed by two
``dcc.Store`` components:

+-----------------+---------------------------+------------------------------+
| Store id        | What lives there          | When to write                |
+=================+===========================+==============================+
| ``{cid}-store`` | Canonical config dict     | Fresh data / attrs           |
+-----------------+---------------------------+------------------------------+
| ``{cid}-opts``  | Runtime options override  | Toggling display options     |
+-----------------+---------------------------+------------------------------+

The :func:`dygraphs.dash.data` and :func:`dygraphs.dash.opts`
helpers return the right ``dash.Output`` object for either store
given a chart id, so callbacks don't have to hand-build the
``"{cid}-store"`` / ``"{cid}-opts"`` strings.

Code below is a complete runnable Dash app — drop it in
``app.py`` and run ``python app.py``. The gallery renders the
initial chart only; the interactive callbacks run live when you
start the app.
"""

import numpy as np
import pandas as pd

from dygraphs import Dygraph

# %%
# Data sources — each returns a 180-point DataFrame with the
# same index so the chart's x-axis range stays meaningful across
# swaps.

_DATES = pd.date_range("2024-01-01", periods=180, freq="D")


def random_walk(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {"y": (20 + np.cumsum(rng.standard_normal(180) * 0.8)).round(2)},
        index=_DATES,
    )


def sine_wave() -> pd.DataFrame:
    t = np.linspace(0, 8 * np.pi, 180)
    return pd.DataFrame({"y": (20 + 6 * np.sin(t)).round(2)}, index=_DATES)


# %%
# Static chart previewed in the gallery. The live app starts from
# this same value and swaps it out at runtime.

chart = (
    Dygraph(random_walk(), title="Random walk (initial)")
    .options(retain_date_window=True, stroke_width=2, colors=["#00d4aa"])
    .range_selector(height=30)
    .legend(show="always")
)

# %%
# The live app — callbacks demonstrated
# --------------------------------------
#
# In the gallery rendering, only ``chart`` above gets embedded
# (the Dash app is skipped because it would try to bind a socket).
# When you run the script directly, the app below starts a
# server on ``http://127.0.0.1:8050`` and you can click buttons
# to see the update paths in action.
#
# .. code-block:: python
#
#     import dash
#     from dash import Input, dcc, html
#     from dygraphs.dash import data, opts
#
#     app = dash.Dash(__name__)
#     chart_component = chart.to_dash(app=app, component_id="chart")
#
#     app.layout = html.Div([
#         chart_component,
#         html.Button("Random walk", id="btn-random", n_clicks=0),
#         html.Button("Sine wave", id="btn-sine", n_clicks=0),
#         dcc.Slider(id="stroke-width", min=1, max=6, value=2),
#     ])
#
#     @app.callback(
#         data("chart"),             # <-- data() helper; full refresh
#         Input("btn-random", "n_clicks"),
#         Input("btn-sine", "n_clicks"),
#         prevent_initial_call=True,
#     )
#     def swap_data_source(_r, _s):
#         key = dash.ctx.triggered_id
#         builder = random_walk if key == "btn-random" else sine_wave
#         label = "Random walk" if key == "btn-random" else "Sine wave"
#         return (
#             Dygraph(builder(), title=label)
#             .options(retain_date_window=True, stroke_width=2)
#             .to_dict()
#         )
#
#     @app.callback(
#         opts("chart"),             # <-- opts() helper; merge only
#         Input("stroke-width", "value"),
#     )
#     def change_stroke_width(width):
#         return {"strokeWidth": width}
#
#     app.run(debug=False)
#
# The full runnable version lives at ``examples/dash_data_update.py``
# in the repo, with a colour picker, status text, and all three
# data sources wired up.
