"""Capture strategy for dash-capture compatibility.

Provides ``dygraph_strategy()`` — a drop-in strategy for
``dash_capture.capture_element()`` that captures dygraph charts
with optional range-selector hiding.

Usage::

    from dygraphs.dash.capture import dygraph_strategy
    from dash_capture import capture_element

    capture_element(
        app, "btn", "my-chart-container", "img-store",
        strategy=dygraph_strategy(hide_range_selector=True),
    )

No changes to dash-capture are required.
"""

from __future__ import annotations

from typing import Any


def dygraph_strategy(
    *,
    hide_range_selector: bool = True,
    format: str = "png",
) -> Any:
    """Create a capture strategy compatible with ``dash_capture.capture_element()``.

    Parameters
    ----------
    hide_range_selector
        If ``True``, temporarily hide the range selector before capture
        and restore it afterwards.
    format
        Image format: ``"png"``, ``"jpeg"``, or ``"webp"``.

    Returns
    -------
    CaptureStrategy
        A ``dash_capture.strategies.CaptureStrategy`` instance.

    Raises
    ------
    ImportError
        If ``dash-capture`` is not installed.
    """
    try:
        from dash_capture.strategies import CaptureStrategy  # noqa: I001  # type: ignore[unresolved-import]
    except ImportError as exc:
        msg = (
            "dash-capture is required for dygraph_strategy(). "
            "Install it with: pip install dash-capture"
        )
        raise ImportError(msg) from exc

    # JS: hide range selector elements before capture
    preprocess = None
    if hide_range_selector:
        preprocess = """\
(function(el, opts) {
    var selectors = [
        '.dygraph-rangesel-fgcanvas',
        '.dygraph-rangesel-bgcanvas',
        '.dygraph-rangesel-zoomhandle'
    ];
    el._dyHidden = [];
    selectors.forEach(function(sel) {
        var items = el.querySelectorAll(sel);
        items.forEach(function(item) {
            el._dyHidden.push({el: item, display: item.style.display});
            item.style.display = 'none';
        });
    });
})"""

    # JS: merge all visible canvases into one, return data-URI
    capture = f"""\
(async function(el, opts) {{
    var canvases = el.querySelectorAll('canvas');
    var c = document.createElement('canvas');
    c.width = el.offsetWidth;
    c.height = el.offsetHeight;
    var ctx = c.getContext('2d');
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, c.width, c.height);
    var pr = el.getBoundingClientRect();
    canvases.forEach(function(cv) {{
        if (cv.style.display === 'none' || cv.offsetParent === null) return;
        var r = cv.getBoundingClientRect();
        ctx.drawImage(cv, r.left - pr.left, r.top - pr.top);
    }});
    // Restore hidden elements
    if (el._dyHidden) {{
        el._dyHidden.forEach(function(h) {{ h.el.style.display = h.display; }});
        delete el._dyHidden;
    }}
    return c.toDataURL('image/{format}');
}})"""

    return CaptureStrategy(
        preprocess=preprocess,
        capture=capture,
        format=format,
    )
