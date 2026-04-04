"""dash-dygraphs: Python/Dash wrapper for the dygraphs JavaScript charting library."""

from __future__ import annotations

from dash_dygraphs.dash_component import dygraph_to_dash, register_callbacks
from dash_dygraphs.dygraph import Dygraph
from dash_dygraphs.utils import JS

try:
    from dash_dygraphs._version import __version__
except ModuleNotFoundError:  # pragma: no cover – editable install before first build
    __version__ = "0.0.0.dev0"

__all__ = ["Dygraph", "JS", "dygraph_to_dash", "register_callbacks", "__version__"]
