"""Shared helpers for the gallery package — data, scaffolding, builders."""

from __future__ import annotations

import html as html_mod
from typing import TypeAlias

import numpy as np
import pandas as pd

from dygraphs import Dygraph

# Public type aliases used by every chapter
ChartList: TypeAlias = list[tuple[str, str]]
Section: TypeAlias = tuple[str, ChartList]

# Deterministic seed so the gallery is reproducible across runs
_RNG = np.random.default_rng(42)
_DATES = pd.date_range("2024-01-01", periods=90, freq="D")


def _ts(cols: list[str], base: float = 20.0) -> pd.DataFrame:
    """Reproducible synthetic time series with the named columns."""
    data = {}
    for i, c in enumerate(cols):
        data[c] = (base + i * 5 + np.cumsum(_RNG.standard_normal(90) * 0.6)).round(2)
    return pd.DataFrame(data, index=_DATES)


def _html(dg: Dygraph, **kw) -> str:
    """Render a Dygraph to standalone HTML at the gallery's standard size."""
    return dg.to_html(height="280px", cdn=True, **kw)


def render_section(title: str, charts: ChartList) -> str:
    """Render a section as the iframe-card HTML the gallery uses."""
    cards = ""
    for subtitle, chart_html in charts:
        # Each chart is a self-contained HTML page — render in an iframe
        # so all <head> scripts (CDN, plotters, shapes.js) are preserved.
        escaped = chart_html.replace("&", "&amp;").replace('"', "&quot;")
        cards += f"""
        <div class="card">
            <h3>{html_mod.escape(subtitle)}</h3>
            <iframe srcdoc="{escaped}" style="width:100%;height:320px;border:none;"></iframe>
        </div>"""
    return f"""
    <div class="section">
        <h2>{html_mod.escape(title)}</h2>
        {cards}
    </div>"""
