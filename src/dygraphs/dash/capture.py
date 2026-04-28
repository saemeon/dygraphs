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
# Self-contained async IIFE: takes ``(el, fmt, hideRangeSelector, debug)`` and
# returns a Promise<data-URI>. Used by both ``dygraph_strategy`` (via the
# dash-capture wizard) and the chart modebar's camera-icon download in
# ``dygraphs.dash.component``. Keep this as the sole multi-canvas merge JS in
# the codebase — fixes here flow to both call sites.
#
# Behaviour:
#   1. If hideRangeSelector, hide the three range-selector canvases / handles
#      on `el`. They're hidden BEFORE the html2canvas pass so the overlay
#      capture skips them too (html2canvas honours display:none).
#   2. Allocate a destination canvas sized at offset(W,H) * devicePixelRatio
#      and scale the 2D context by DPR — output is sharp on retina displays.
#   3. For each visible source canvas under `el`, blit it via the 9-arg
#      drawImage form, mapping its full backing buffer (cv.width × cv.height,
#      which dygraph backs at css * DPR) into its CSS-pixel rect.
#   4. Rasterise the HTML overlay layer (chart title, x/y axis labels, tick
#      labels, legend, annotations) via ``window.html2canvas`` at the same
#      DPR and composite it on top of the canvas content. ``ignoreElements``
#      skips ``<canvas>`` tags so we don't double-paint them at
#      html2canvas's lower fidelity. The compositing context is reset to
#      identity for this draw because the overlay canvas is already at
#      device-pixel scale. If html2canvas isn't loaded the overlay step
#      silently no-ops; ``dygraph_strategy`` always queues the asset, so
#      this only happens for unusual setups (e.g. a modebar download
#      before any strategy was constructed).
#   5. Restore any hidden range-selector elements.
#   6. Resolve with the data-URI.
#
# When `debug` is true, the IIFE logs dpr/dimensions/per-canvas rects to the
# browser console and outlines each blit destination with a 1px red border so
# you can see exactly where every source canvas landed in the output.
MULTI_CANVAS_CAPTURE_JS = """\
(async function (el, fmt, hideRangeSelector, debug) {
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
    }
    if (window.html2canvas) {
        try {
            var overlay = await window.html2canvas(el, {
                backgroundColor: null,
                scale: dpr,
                useCORS: true,
                logging: !!debug,
                ignoreElements: function (n) {
                    return n.tagName === 'CANVAS';
                }
            });
            ctx.save();
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.drawImage(overlay, 0, 0);
            ctx.restore();
            if (debug) {
                console.log(
                    'html2canvas overlay (device px):',
                    overlay.width, 'x', overlay.height
                );
            }
        } catch (e) {
            if (debug) console.warn('html2canvas overlay failed:', e);
        }
    } else if (debug) {
        console.warn(
            '[dygraph capture] html2canvas not loaded; ' +
            'skipping HTML overlay (title / axis labels / legend).'
        );
    }
    if (debug) console.groupEnd();
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
    the target element onto a single white-backed canvas and overlays
    the HTML layer — chart title, x/y axis labels, tick labels, legend,
    annotations — via ``html2canvas``, returning a base64 data-URI.
    Designed for charts produced by :class:`dygraphs.dash.DygraphChart`.

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
        element dimensions, output canvas dimensions, the bounding rect
        of every source canvas, and the html2canvas overlay dimensions
        to the browser console; it also draws a 1px red border around
        each source canvas's destination rect in the output. Use this
        to diagnose cropping or overlay-alignment issues.

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

    The ``html2canvas`` asset is queued via
    :func:`dash_capture._html2canvas.ensure_html2canvas` at strategy
    construction time. Call ``dygraph_strategy()`` at module level (or
    anywhere before the first page is served) so Dash can drain the
    inline-script queue into the served HTML.

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
        from dash_capture.strategies import CaptureStrategy  # noqa: I001  # type: ignore[unresolved-import]
    except ImportError as exc:
        msg = (
            "dash-capture is required for dygraph_strategy(). "
            "Install it with: pip install dash-capture"
        )
        raise ImportError(msg) from exc

    from dash_capture._html2canvas import ensure_html2canvas  # type: ignore[unresolved-import]

    ensure_html2canvas([])

    # Raw statement that invokes the shared async IIFE with the wrapper's
    # `el`. `preprocess` stays None — hide/restore is internal to the IIFE.
    # The IIFE is async (it awaits html2canvas for the overlay pass), so the
    # capture body must `await` its Promise. dash-capture wraps the capture
    # JS in an `async function`, so top-level `await` is valid.
    hide_js = "true" if hide_range_selector else "false"
    debug_js = "true" if debug else "false"
    capture = (
        f"return await {MULTI_CANVAS_CAPTURE_JS}"
        f"(el, '{format}', {hide_js}, {debug_js});"
    )

    return CaptureStrategy(
        preprocess=None,
        capture=capture,
        format=format,
    )
