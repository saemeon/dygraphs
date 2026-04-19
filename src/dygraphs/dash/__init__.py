"""dygraphs Dash adapter — render dygraphs in Plotly Dash apps.

Install with: ``pip install dygraphs[dash]``
"""

from __future__ import annotations

from dygraphs.dash.capture import dygraph_strategy
from dygraphs.dash.component import DyGraph, dygraph_to_dash, stacked_bar

__all__ = [
    "DyGraph",
    "dygraph_strategy",
    "dygraph_to_dash",
    "stacked_bar",
]
