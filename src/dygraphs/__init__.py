"""dygraphs: Python wrapper for the dygraphs JavaScript charting library.

Core port of the R dygraphs package with a Pythonic builder API.
Framework adapters available for Dash and Shiny.

Install extras for framework support::

    pip install dygraphs[dash]     # Plotly Dash
    pip install dygraphs[shiny]    # Shiny for Python

Framework-specific entry points live under their subpackages — import
them directly so Pylance / pyright can see the real signatures::

    from dygraphs.dash import DygraphChart, stacked_bar, dygraph_strategy
    from dygraphs.shiny import dygraph_ui, render_dygraph
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
    "__version__",
]
