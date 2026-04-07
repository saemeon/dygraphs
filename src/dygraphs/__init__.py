"""dygraphs: Python wrapper for the dygraphs JavaScript charting library.

Core port of the R dygraphs package with a Pythonic builder API.
Framework adapters available for Dash and Shiny (future).

Install extras for framework support::

    pip install dygraphs[dash]     # Plotly Dash
    pip install dygraphs[shiny]    # Shiny for Python (coming soon)
"""

from __future__ import annotations

from dygraphs.declarative import (
    Annotation,
    Axis,
    Callbacks,
    Event,
    Highlight,
    Legend,
    Limit,
    Options,
    RangeSelector,
    Roller,
    Series,
    Shading,
)
from dygraphs.dygraph import Dygraph
from dygraphs.utils import JS, make_custom_bar_data, make_error_bar_data

try:
    from dygraphs._version import __version__
except ModuleNotFoundError:  # pragma: no cover – editable install before first build
    __version__ = "0.0.0.dev0"


# ---------------------------------------------------------------------------
# Lazy Dash imports — only available when dygraphs[dash] is installed.
# These are top-level convenience re-exports so users can write:
#   from dygraphs import dygraph_to_dash
# ---------------------------------------------------------------------------


def dygraph_to_dash(*args, **kwargs):  # type: ignore[no-untyped-def]  # noqa: ANN002, ANN003
    """Render a Dygraph into Dash components. Requires ``dygraphs[dash]``."""
    from dygraphs.dash import dygraph_to_dash as _fn

    return _fn(*args, **kwargs)


def stacked_bar(*args, **kwargs):  # type: ignore[no-untyped-def]  # noqa: ANN002, ANN003
    """Create a stacked bar chart for Dash. Requires ``dygraphs[dash]``."""
    from dygraphs.dash import stacked_bar as _fn

    return _fn(*args, **kwargs)


def dygraph_strategy(**kwargs):  # type: ignore[no-untyped-def]  # noqa: ANN003
    """Capture strategy for dash-capture. Requires ``dygraphs[dash]``."""
    from dygraphs.dash import dygraph_strategy as _fn

    return _fn(**kwargs)


__all__ = [
    # Core
    "Dygraph",
    "JS",
    # Declarative dataclasses
    "Annotation",
    "Axis",
    "Callbacks",
    "Event",
    "Highlight",
    "Legend",
    "Limit",
    "Options",
    "RangeSelector",
    "Roller",
    "Series",
    "Shading",
    # Utilities
    "make_custom_bar_data",
    "make_error_bar_data",
    # Dash (lazy)
    "dygraph_strategy",
    "dygraph_to_dash",
    "stacked_bar",
    "__version__",
]
