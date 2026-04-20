"""Capture strategy for dash-capture compatibility.

Provides :func:`dygraph_strategy` — a drop-in strategy for
:func:`dash_capture.capture_element` that captures dygraph charts as
PNG/JPEG/WebP images, with optional range-selector hiding.

Why a custom strategy is needed
-------------------------------
A dygraph chart draws onto several stacked ``<canvas>`` elements
(plot, axes, range selector). The built-in
``dash_capture.canvas_strategy`` only captures the *first* canvas it
finds, so it cannot reproduce the full chart. ``dygraph_strategy``
walks every visible canvas under the container and composites them
onto a single output canvas, preserving their on-screen position.

No changes to ``dash-capture`` are required — the returned object is a
plain ``dash_capture.strategies.CaptureStrategy``.

The same JS used by this strategy is also invoked by the chart's
modebar camera-icon download button (see
:mod:`dygraphs.dash.component`), via the shared
:data:`MULTI_CANVAS_CAPTURE_JS` constant — single source of truth for
the multi-canvas merge.

See Also
--------
dygraphs.dash.DygraphChart : Render a Dygraph as a Dash component.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Shared multi-canvas merge JS
# ---------------------------------------------------------------------------
#
# Self-contained IIFE: takes (el, fmt, hideRangeSelector, debug) and returns a
# data-URI string. Used by both ``dygraph_strategy`` (via the dash-capture
# wizard) and the chart modebar's camera-icon download in
# ``dygraphs.dash.component``. Keep this as the sole multi-canvas merge JS in
# the codebase — fixes here flow to both call sites.
#
# Behaviour:
#   1. If hideRangeSelector, hide the three range-selector canvases on `el`.
#   2. Allocate a destination canvas sized at offset(W,H) * devicePixelRatio
#      and scale the 2D context by DPR — output is sharp on retina displays.
#   3. For each visible source canvas under `el`, blit it via the 9-arg
#      drawImage form, mapping its full backing buffer (cv.width × cv.height,
#      which dygraph backs at css * DPR) into its CSS-pixel rect.
#   4. Restore any hidden range-selector elements (always — even on errors
#      via the surrounding async wrapper, since this body is synchronous).
#   5. Return the data-URI.
#
# When `debug` is true, the IIFE logs dpr/dimensions/per-canvas rects to the
# browser console and outlines each blit destination with a 1px red border so
# you can see exactly where every source canvas landed in the output.
MULTI_CANVAS_CAPTURE_JS = """\
(function (el, fmt, hideRangeSelector, debug) {
    if (hideRangeSelector) {
        el._dyHidden = [];
        [
            '.dygraph-rangesel-fgcanvas',
            '.dygraph-rangesel-bgcanvas',
            '.dygraph-rangesel-zoomhandle'
        ].forEach(function (sel) {
            el.querySelectorAll(sel).forEach(function (item) {
                el._dyHidden.push({el: item, display: item.style.display});
                item.style.display = 'none';
            });
        });
    }
    var dpr = window.devicePixelRatio || 1;
    var canvases = el.querySelectorAll('canvas');
    var cssW = el.offsetWidth;
    var cssH = el.offsetHeight;
    var out = document.createElement('canvas');
    out.width = Math.round(cssW * dpr);
    out.height = Math.round(cssH * dpr);
    var ctx = out.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, cssW, cssH);
    var pr = el.getBoundingClientRect();
    if (debug) {
        console.group('[dygraph capture] debug');
        console.log('target el:', el.id || el.tagName, el);
        console.log('devicePixelRatio:', dpr);
        console.log('el.offsetWidth/Height (CSS):', cssW, 'x', cssH);
        console.log('el.getBoundingClientRect():', pr);
        console.log('output canvas (device px):', out.width, 'x', out.height);
        console.log('found', canvases.length, 'canvas elements');
    }
    var drawn = 0;
    canvases.forEach(function (cv, i) {
        var skip = (cv.style.display === 'none' || cv.offsetParent === null);
        var r = cv.getBoundingClientRect();
        if (debug) {
            console.log(
                '  canvas[' + i + '] backing=' + cv.width + 'x' + cv.height +
                ' rect=' + Math.round(r.width) + 'x' + Math.round(r.height) +
                ' @ (' + Math.round(r.left - pr.left) + ',' +
                Math.round(r.top - pr.top) + ')' +
                (skip ? ' SKIPPED' : ''),
                cv
            );
        }
        if (skip) return;
        ctx.drawImage(
            cv,
            0, 0, cv.width, cv.height,
            r.left - pr.left, r.top - pr.top, r.width, r.height
        );
        if (debug) {
            ctx.save();
            ctx.strokeStyle = 'red';
            ctx.lineWidth = 1;
            ctx.strokeRect(
                r.left - pr.left + 0.5, r.top - pr.top + 0.5,
                r.width - 1, r.height - 1
            );
            ctx.restore();
        }
        drawn++;
    });
    if (debug) {
        console.log('drew', drawn, 'canvases onto output');
        console.groupEnd();
    }
    if (el._dyHidden) {
        el._dyHidden.forEach(function (h) {
            h.el.style.display = h.display;
        });
        delete el._dyHidden;
    }
    return out.toDataURL('image/' + fmt);
})"""


def dygraph_strategy(
    *,
    hide_range_selector: bool = True,
    format: str = "png",
    debug: bool = False,
) -> Any:
    """Create a capture strategy compatible with ``dash_capture.capture_element()``.

    The returned strategy composites every visible ``<canvas>`` inside
    the target element onto a single white-backed canvas and returns a
    base64 data-URI. It is designed for charts produced by
    :class:`dygraphs.dash.DygraphChart`.

    The capture JS is :data:`MULTI_CANVAS_CAPTURE_JS` — the same code
    invoked by the chart modebar's camera-icon download — so the two
    paths cannot drift apart.

    Parameters
    ----------
    hide_range_selector : bool, default: True
        If ``True``, temporarily hide the range-selector canvases
        (``.dygraph-rangesel-fgcanvas``, ``.dygraph-rangesel-bgcanvas``,
        ``.dygraph-rangesel-zoomhandle``) before capture and restore
        their original ``display`` values afterwards.
    format : {"png", "jpeg", "webp"}, default: "png"
        Output image format. The format is baked into the JS at strategy
        build time, so the wizard's runtime ``fmt`` argument is ignored —
        build a separate strategy per format if you need a chooser.
    debug : bool, default: False
        If ``True``, the capture JS logs ``devicePixelRatio``, target
        element dimensions, output canvas dimensions, and the bounding
        rect of every source canvas to the browser console; it also
        draws a 1px red border around each source canvas's destination
        rect in the output. Use this to diagnose cropping issues.

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

    HTML elements rendered outside the canvases (chart title, axis tick
    labels, legend) are **not** captured by this strategy — only the
    plot canvases are. Use ``dash_capture.html2canvas_strategy()`` if
    you need the full HTML overlay.

    Examples
    --------
    Wire a capture button next to a chart::

        from dash import Dash, html
        from dash_capture import capture_element

        from dygraphs import Dygraph, dygraph_strategy
        from dygraphs.dash import DygraphChart

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
        from dash_capture.strategies import CaptureStrategy  # noqa: I001  # type: ignore[unresolved-import]
    except ImportError as exc:
        msg = (
            "dash-capture is required for dygraph_strategy(). "
            "Install it with: pip install dash-capture"
        )
        raise ImportError(msg) from exc

    # Raw statement that invokes the shared IIFE with the wrapper's `el`.
    # `preprocess` stays None — hide/restore is internal to the IIFE.
    hide_js = "true" if hide_range_selector else "false"
    debug_js = "true" if debug else "false"
    capture = (
        f"return {MULTI_CANVAS_CAPTURE_JS}(el, '{format}', {hide_js}, {debug_js});"
    )

    return CaptureStrategy(
        preprocess=None,
        capture=capture,
        format=format,
    )
