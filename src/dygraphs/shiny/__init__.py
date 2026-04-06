"""dygraphs Shiny adapter — render dygraphs in Shiny for Python apps.

Install with: ``pip install dygraphs[shiny]``
"""

from __future__ import annotations

from dygraphs.shiny.component import dygraph_ui, render_dygraph

__all__ = ["dygraph_ui", "render_dygraph"]
