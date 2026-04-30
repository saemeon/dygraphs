"""dygraphs Dash adapter — render dygraphs in Plotly Dash apps.

Install with: ``pip install dygraphs[dash]``
"""

from __future__ import annotations

from dygraphs.dash.capture import dygraph_strategy
from dygraphs.dash.component import DygraphChart, StackedBarChart
from dygraphs.dash.modebar import DyModebarButton

__all__ = [
    "DygraphChart",
    "DyModebarButton",
    "StackedBarChart",
    "dygraph_strategy",
]
