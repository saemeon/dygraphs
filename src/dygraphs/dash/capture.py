"""Capture strategy for dash-capture compatibility.

Provides :func:`dygraph_strategy` — a thin wrapper around
:func:`dash_capture.multi_canvas_strategy` that bakes in the dygraphs-
specific knowledge (which selectors to hide for a clean export). The
heavy lifting — canvas-walking, html2canvas overlay, live-resize — lives
in dash-capture so other chart libraries can reuse it.

The shared multi-canvas IIFE :data:`dash_capture.MULTI_CANVAS_CAPTURE_JS`
is also invoked directly by the chart's modebar camera-icon download
button (see :mod:`dygraphs.dash.component`), with this module's
:data:`DYGRAPH_HIDE_SELECTORS` passed at call time. Single source of
truth for the JS, dygraphs owns the selector list.

See Also
--------
dygraphs.dash.DygraphChart : Render a Dygraph as a Dash component.
dash_capture.multi_canvas_strategy : The underlying generic strategy.
"""

from __future__ import annotations

from typing import Any

# Re-export so component.py and any callers that previously imported
# MULTI_CANVAS_CAPTURE_JS from this module keep working.
from dash_capture import MULTI_CANVAS_CAPTURE_JS  # noqa: F401

# ---------------------------------------------------------------------------
# Dygraphs-specific selectors to hide during capture
# ---------------------------------------------------------------------------

#: CSS selectors for the range-selector overlay. Hidden during capture
#: so the export shows the chart without the bottom navigation strip.
#: Used by both :func:`dygraph_strategy` and the modebar camera-icon
#: download in :mod:`dygraphs.dash.component`. Source of truth for which
#: chrome elements should be omitted from a chart export.
DYGRAPH_HIDE_SELECTORS = [
    ".dygraph-rangesel-fgcanvas",
    ".dygraph-rangesel-bgcanvas",
    ".dygraph-rangesel-zoomhandle",
]


def dygraph_strategy(
    *,
    hide_range_selector: bool = True,
    strip_margin: bool = False,
    format: str = "png",
    debug: bool = False,
    settle_frames: int = 2,
    _params: Any = None,
) -> Any:
    """Create a capture strategy compatible with ``dash_capture.capture_element()``.

    Composites every visible ``<canvas>`` inside the target element onto
    a single white-backed canvas and overlays the HTML layer (chart
    title, axis labels, tick labels, legend, annotations) via
    ``html2canvas``, returning a base64 data-URI. Designed for charts
    produced by :class:`dygraphs.dash.DygraphChart`.

    This is a thin wrapper around :func:`dash_capture.multi_canvas_strategy`
    that pre-fills :data:`DYGRAPH_HIDE_SELECTORS` when
    ``hide_range_selector`` is True.

    Parameters
    ----------
    hide_range_selector : bool, default: True
        If ``True``, temporarily hide the range-selector canvases
        (:data:`DYGRAPH_HIDE_SELECTORS`) before capture and restore
        their original ``display`` values afterwards.
    strip_margin : bool, default: False
        If ``True``, temporarily zero out CSS margin and padding on the
        target element during capture. This removes spacing around the
        chart, matching the behavior of Plotly's ``strip_margin`` option.
    format : {"png", "jpeg", "webp"}, default: "png"
        Output image format. The format is baked into the JS at strategy
        build time, so the wizard's runtime ``fmt`` argument is ignored —
        build a separate strategy per format if you need a chooser.
    debug : bool, default: False
        Forward to :func:`multi_canvas_strategy` — logs per-canvas blits
        and outlines destination rects in red.
    settle_frames : int, default: 2
        rAF ticks to await between live-resize and capture, so dygraphs's
        ``ResizeObserver`` (in :file:`render_core.js`) re-lays-out the
        canvases at the new aspect.
    _params : Mapping or None, optional
        Internal hook mirroring :func:`dash_capture.html2canvas_strategy`.
        Pass ``inspect.signature(renderer).parameters`` to enable
        target-size capture: when the renderer declares
        ``capture_width`` / ``capture_height``, the wrapped strategy
        emits a live-resize preprocess.

    Returns
    -------
    CaptureStrategy
        A ``dash_capture.strategies.CaptureStrategy`` instance, ready to
        pass to ``capture_element(..., strategy=...)``.

    Raises
    ------
    ImportError
        If ``dash-capture`` is not installed. Install with
        ``pip install dygraphs[dash] dash-capture``.

    Notes
    -----
    SVG output is **not** supported: dygraphs renders to ``<canvas>``,
    and ``canvas.toDataURL`` only emits raster formats.

    The HTML overlay rendered by ``html2canvas`` is rasterised at the
    same ``devicePixelRatio`` as the canvas composite, so text stays
    crisp on retina displays. Compositing order is canvases first,
    overlays on top — so labels never get drawn over by axis lines.

    Examples
    --------
    Wire a capture button next to a chart::

        from dash import Dash, html
        from dash_capture import capture_element

        from dygraphs import Dygraph
        from dygraphs.dash import DygraphChart, dygraph_strategy

        app = Dash(__name__)

        chart = Dygraph(df, title="Sales").range_selector()
        chart_component = DygraphChart(figure=chart, id="sales", height="320px")

        app.layout = html.Div([
            chart_component,
            capture_element(
                "sales-container",
                trigger="Download PNG",
                strategy=dygraph_strategy(hide_range_selector=True),
                filename="sales.png",
            ),
        ])

    The element id passed to ``capture_element`` is
    ``f"{id}-container"`` — the inner ``<div>`` that holds
    the chart canvases (see :class:`dygraphs.dash.DygraphChart`).
    """
    try:
        from dash_capture import multi_canvas_strategy
    except ImportError as exc:
        msg = (
            "dash-capture is required for dygraph_strategy(). "
            "Install it with: pip install dash-capture"
        )
        raise ImportError(msg) from exc

    strategy = multi_canvas_strategy(
        hide_selectors=DYGRAPH_HIDE_SELECTORS if hide_range_selector else [],
        format=format,
        debug=debug,
        settle_frames=settle_frames,
        _params=_params,
    )

    # If strip_margin is True, enhance the preprocess to zero margins.
    if strip_margin:
        margin_strip = """\
            const _orig_margin = el.style.margin;
            const _orig_padding = el.style.padding;
            el.style.margin = "0";
            el.style.padding = "0";"""
        strategy.preprocess = (
            (strategy.preprocess + "\n" + margin_strip)
            if strategy.preprocess
            else margin_strip
        )

    return strategy
