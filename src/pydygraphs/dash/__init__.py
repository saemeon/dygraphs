"""pydygraphs Dash adapter — render dygraphs in Plotly Dash apps.

Install with: ``pip install pydygraphs[dash]``
"""

from __future__ import annotations

from pydygraphs.dash.capture import dygraph_strategy
from pydygraphs.dash.component import dygraph_to_dash, stacked_bar, sync_dygraphs

__all__ = ["dygraph_to_dash", "dygraph_strategy", "stacked_bar", "sync_dygraphs"]
