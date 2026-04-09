"""dygraphs Dash adapter — render dygraphs in Plotly Dash apps.

Install with: ``pip install dygraphs[dash]``
"""

from __future__ import annotations

from dygraphs.dash.capture import dygraph_strategy
from dygraphs.dash.component import dygraph_to_dash, stacked_bar
from dygraphs.dash.outputs import data, opts

__all__ = [
    "data",
    "dygraph_strategy",
    "dygraph_to_dash",
    "opts",
    "stacked_bar",
]
