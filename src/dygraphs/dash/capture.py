"""Capture strategy for dash-capture compatibility.

Provides :func:`dygraph_strategy` — a thin wrapper around
:func:`dash_capture.multi_canvas_strategy` that adds the dygraphs-
specific behaviour needed for clean exports. The heavy lifting —
canvas-walking, html2canvas overlay, live-resize — lives in
dash-capture so other chart libraries can reuse it.

dygraph-specific behaviour layered on top of multi_canvas_strategy:

* **Range-selector toggle.** When ``hide_range_selector=True`` (the
  default), the preprocess calls
  ``dygraphInstance.updateOptions({showRangeSelector: false})`` so the
  plugin removes its DOM and the plot fills the whole container. The
  capture is wrapped in a ``try/finally`` that toggles it back on. No
  output cropping or height compensation needed: dygraphs lays the
  plot out at the full container height.
* **Strip margin.** Optional zero-out of the container's CSS margin
  and padding for tight exports.

The shared multi-canvas IIFE :data:`dash_capture.MULTI_CANVAS_CAPTURE_JS`
is also invoked directly by the chart's modebar camera-icon download
button (see :mod:`dygraphs.dash.component`), with
:data:`DYGRAPH_HIDE_SELECTORS` passed at call time — that path *does*
use display-toggle selector hiding (no dygraph instance handle in the
modebar context). Two different mechanisms, same observable result.

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

#: CSS selectors for the range-selector overlay. Used by the modebar
#: camera-icon download path in :mod:`dygraphs.dash.component` to hide
#: the bottom navigation strip via display-toggle during capture.
#:
#: :func:`dygraph_strategy` uses a different mechanism (toggling the
#: ``showRangeSelector`` option via the dygraph instance) so that
#: dygraphs reflows the plot to fill the freed space. The modebar path
#: doesn't have a handle to the dygraph instance, so it falls back to
#: hiding the canvases — the live plot height stays the same and the
#: hidden strip is simply absent from the captured image.
DYGRAPH_HIDE_SELECTORS = [
    ".dygraph-rangesel-fgcanvas",
    ".dygraph-rangesel-bgcanvas",
    ".dygraph-rangesel-zoomhandle",
]

#: Milliseconds to wait after toggling ``showRangeSelector`` off before
#: capturing. Dygraphs' range-selector plugin defers its own resize
#: through a ``setTimeout(..., 1)`` (see ``range-selector.js``); we wait
#: longer than that, plus two rAFs, to let the layout settle. 16ms is
#: empirically reliable on modern hardware while staying imperceptible.
_TOGGLE_SETTLE_MS = 16


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

    Wraps :func:`dash_capture.multi_canvas_strategy` and adds two
    dygraphs-specific behaviours: a range-selector toggle (so the
    plot fills the full container during capture) and an optional
    margin/padding strip.

    Parameters
    ----------
    hide_range_selector : bool, default: True
        If ``True``, the preprocess calls
        ``dygraphInstance.updateOptions({showRangeSelector: false})``
        before capture and toggles it back on afterwards. Dygraphs
        removes the plugin's DOM and reflows the plot to fill the freed
        space, so the captured image is exactly the plot — no white
        strip, no cropping. Toggle is gated on the dygraph instance
        being present and the option being currently on. The user sees
        a brief flicker on the live chart.
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
        canvases at the new aspect. Independent of the toggle settle
        (which has its own hardcoded wait — see ``_TOGGLE_SETTLE_MS``).
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

    strategy = _build_dygraph_strategy(
        multi_canvas_strategy=multi_canvas_strategy,
        hide_range_selector=hide_range_selector,
        strip_margin=strip_margin,
        format=format,
        debug=debug,
        settle_frames=settle_frames,
        _params=_params,
    )

    # Override _rebuild so capture_element's auto-wire of renderer params
    # re-applies our preprocess additions (range-selector toggle and
    # strip_margin) on top of multi_canvas_strategy.
    strategy._rebuild = lambda p: _build_dygraph_strategy(
        multi_canvas_strategy=multi_canvas_strategy,
        hide_range_selector=hide_range_selector,
        strip_margin=strip_margin,
        format=format,
        debug=debug,
        settle_frames=settle_frames,
        _params=p,
    )
    return strategy


def _build_dygraph_strategy(
    *,
    multi_canvas_strategy: Any,
    hide_range_selector: bool,
    strip_margin: bool,
    format: str,
    debug: bool,
    settle_frames: int,
    _params: Any,
) -> Any:
    strategy = multi_canvas_strategy(
        hide_selectors=[],
        format=format,
        debug=debug,
        settle_frames=settle_frames,
        _params=_params,
    )

    # Hide the range selector via dygraphs' own option toggle. The plugin
    # removes its DOM and triggers a resize so the plot fills the full
    # container height — capture sees a chart with no range selector at
    # all (no white strip, no compensation, no post-crop). The capture
    # JS is wrapped in try/finally so the toggle-back runs even if the
    # capture throws.
    #
    # The toggle is no-op if no dygraph instance is present or the option
    # was already off. The marker `el._dcap_rs_was_on` carries state from
    # preprocess to the finally so we only restore what we changed.
    # Block scopes ({...}) keep the local consts from leaking into other
    # preprocess fragments concatenated alongside this one.
    if hide_range_selector:
        toggle_off = f"""\
            {{
                const _dy = el._dygraphInstance;
                if (_dy && _dy.getOption && _dy.getOption('showRangeSelector')) {{
                    el._dcap_rs_was_on = true;
                    _dy.updateOptions({{showRangeSelector: false}}, false);
                    await new Promise(r => setTimeout(r, {_TOGGLE_SETTLE_MS}));
                    await new Promise(r => requestAnimationFrame(r));
                    await new Promise(r => requestAnimationFrame(r));
                }}
            }}"""
        strategy.preprocess = (
            (toggle_off + "\n" + strategy.preprocess)
            if strategy.preprocess
            else toggle_off
        )

        original_capture = strategy.capture
        strategy.capture = f"""\
            try {{ return await (async () => {{ {original_capture} }})(); }}
            finally {{
                if (el._dcap_rs_was_on && el._dygraphInstance) {{
                    el._dygraphInstance.updateOptions(
                        {{showRangeSelector: true}}, false
                    );
                    delete el._dcap_rs_was_on;
                }}
            }}"""

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
