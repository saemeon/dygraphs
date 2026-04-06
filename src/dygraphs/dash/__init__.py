"""dygraphs Dash adapter — render dygraphs in Plotly Dash apps.

Install with: ``pip install dygraphs[dash]``
"""

from __future__ import annotations

from dygraphs.dash.capture import dygraph_strategy
from dygraphs.dash.component import dygraph_to_dash, stacked_bar, sync_dygraphs

__all__ = ["dygraph_to_dash", "dygraph_strategy", "stacked_bar", "sync_dygraphs"]
