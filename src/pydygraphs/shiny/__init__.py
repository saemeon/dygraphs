"""pydygraphs Shiny adapter — render dygraphs in Shiny for Python apps.

Install with: ``pip install pydygraphs[shiny]``
"""

from __future__ import annotations

from pydygraphs.shiny.component import dygraph_ui, render_dygraph

__all__ = ["dygraph_ui", "render_dygraph"]
