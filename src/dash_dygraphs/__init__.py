"""dash-dygraphs: Python/Dash wrapper for the dygraphs JavaScript charting library."""

from __future__ import annotations

try:
    from dash_dygraphs._version import __version__
except ModuleNotFoundError:  # pragma: no cover – editable install before first build
    __version__ = "0.0.0.dev0"
