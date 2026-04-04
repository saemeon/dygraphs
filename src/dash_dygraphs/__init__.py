"""dash-dygraphs: Python/Dash wrapper for the dygraphs JavaScript charting library."""

from __future__ import annotations

from dash_dygraphs.dash_component import (
    dygraph_to_dash,
    stacked_bar,
    sync_dygraphs,
)
from dash_dygraphs.dygraph import Dygraph
from dash_dygraphs.utils import JS


# Lazy import — only available when dash-capture is installed
def dygraph_strategy(**kwargs):  # type: ignore[no-untyped-def]  # noqa: ANN003
    """Create a capture strategy for dash-capture. See :mod:`dash_dygraphs.capture`."""
    from dash_dygraphs.capture import dygraph_strategy as _ds
    return _ds(**kwargs)

try:
    from dash_dygraphs._version import __version__
except ModuleNotFoundError:  # pragma: no cover – editable install before first build
    __version__ = "0.0.0.dev0"

__all__ = [
    "Dygraph",
    "JS",
    "dygraph_to_dash",
    "stacked_bar",
    "sync_dygraphs",
    "__version__",
]
