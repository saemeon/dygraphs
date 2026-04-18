"""Helpers for wiring Dash callbacks to a dygraphs chart's stores.

Each chart created with :func:`dygraphs.dash.dygraph_to_dash` (or
:meth:`Dygraph.to_dash`) is backed by two ``dcc.Store`` components:

- ``{component_id}-store`` — canonical config (data + attrs). Writing
  here triggers a full destroy+recreate of the dygraph instance.
- ``{component_id}-opts`` — runtime overrides. Writing here merges
  options without retransmitting the data payload.

Rather than making users hand-build the magic-id strings, this module
exposes :func:`data` and :func:`opts` that return ``dash.Output``
objects pointing at the right store. The string format is the single
source of truth, mirrored in
``src/dygraphs/dash/component.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dash.dependencies import Output


def data(component_id: str) -> Output:
    """Build a Dash ``Output`` for the data store of a dygraphs chart.

    Use this in serverside or clientside callbacks to push a fresh
    config (data + attrs) into the chart::

        from dygraphs.dash import data

        @dash.callback(data("my-chart"), Input("refresh", "n_clicks"))
        def refresh(_n):
            return Dygraph(new_df).to_dict()

    Parameters
    ----------
    component_id : str
        The same ``component_id`` passed to
        :func:`dygraphs.dash.dygraph_to_dash` or :meth:`Dygraph.to_dash`.

    Returns
    -------
    dash.dependencies.Output
        ``Output(f"{component_id}-store", "data")``.
    """
    from dash.dependencies import Output

    return Output(f"{component_id}-store", "data")


def opts(component_id: str) -> Output:
    """Build a Dash ``Output`` for the runtime opts store of a dygraphs chart.

    Mirrors :func:`data` but targets the per-chart options store. Use
    it to push runtime overrides (line widths, colors, axis labels, …)
    without retransmitting the data payload::

        from dygraphs.dash import opts

        @dash.callback(opts("my-chart"), Input("toggle", "value"))
        def toggle(v):
            return {"strokeWidth": 3 if v else 1}

    Parameters
    ----------
    component_id : str
        The same ``component_id`` passed to
        :func:`dygraphs.dash.dygraph_to_dash` or :meth:`Dygraph.to_dash`.

    Returns
    -------
    dash.dependencies.Output
        ``Output(f"{component_id}-opts", "data")``.
    """
    from dash.dependencies import Output

    return Output(f"{component_id}-opts", "data")
