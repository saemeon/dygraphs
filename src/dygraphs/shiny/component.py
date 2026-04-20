"""Shiny for Python integration — render a Dygraph in Shiny apps.

Uses ``session.send_custom_message()`` to push config from Python to JS,
and ``Shiny.addCustomMessageHandler()`` on the client to initialize dygraphs.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from dygraphs.utils import (
    DYGRAPH_CSS_CDN as _DYGRAPH_CSS_CDN,
)
from dygraphs.utils import (
    DYGRAPH_JS_CDN as _DYGRAPH_JS_CDN,
)

if TYPE_CHECKING:
    from dygraphs.dygraph import Dygraph

ASSETS_DIR = Path(__file__).parent.parent / "assets"


def dygraph_ui(
    element_id: str,
    *,
    height: str = "400px",
    width: str = "100%",
) -> Any:
    """Create the UI components for a dygraph chart.

    Returns a ``TagList`` containing:
    - CDN ``<link>`` and ``<script>`` for dygraphs
    - A container ``<div>``
    - A ``<script>`` registering the custom message handler

    Parameters
    ----------
    element_id
        Unique DOM id for the chart container.
    height, width
        CSS dimensions.

    Returns
    -------
    shiny.ui.TagList
    """
    from shiny import ui

    handler_js = f"""
    Shiny.addCustomMessageHandler("dygraphs_{element_id}", function(config) {{
        var el = document.getElementById("{element_id}");
        if (!el) return;

        // Transpose column-oriented data to row-oriented
        var data = config.data;
        var nRows = data[0].length;
        var nCols = data.length;
        var rows = [];
        for (var i = 0; i < nRows; i++) {{
            var row = [];
            for (var j = 0; j < nCols; j++) {{
                var val = data[j][i];
                if (j === 0 && config.format === 'date' && typeof val === 'string') {{
                    val = new Date(val);
                }}
                row.push(val);
            }}
            rows.push(row);
        }}

        // Build options, processing __JS__ markers
        var opts = JSON.parse(JSON.stringify(config.attrs));
        function processJS(obj) {{
            if (!obj || typeof obj !== 'object') return obj;
            for (var key in obj) {{
                if (typeof obj[key] === 'string' && obj[key].indexOf('__JS__:') === 0) {{
                    var code = obj[key].slice(7, -7);
                    try {{ obj[key] = eval('(' + code + ')'); }} catch(e) {{
                        console.warn('dygraphs: eval failed for "' + key + '":', e);
                    }}
                }} else if (typeof obj[key] === 'object') {{
                    processJS(obj[key]);
                }}
            }}
            return obj;
        }}
        processJS(opts);

        // Inject plugin/plotter JS before instantiation
        if (config.extraJs) {{
            for (var ej = 0; ej < config.extraJs.length; ej++) {{
                try {{ eval(config.extraJs[ej]); }} catch(e) {{
                    console.warn('dygraphs: failed to eval extraJs:', e);
                }}
            }}
        }}

        // Plugins
        if (config.plugins) {{
            var plugs = [];
            for (var p = 0; p < config.plugins.length; p++) {{
                var pl = config.plugins[p];
                if (Dygraph.Plugins && Dygraph.Plugins[pl.name]) {{
                    plugs.push(new Dygraph.Plugins[pl.name](pl.options));
                }}
            }}
            if (plugs.length > 0) opts.plugins = plugs;
        }}

        // Group sync: zoom + highlight across charts sharing config.group
        if (config.group) {{
            if (!window.__dyGroups) window.__dyGroups = {{}};
            var grp = config.group;
            if (!window.__dyGroups[grp]) window.__dyGroups[grp] = [];
            window.__dyGroups[grp] = window.__dyGroups[grp].filter(
                function(e) {{ return e.el !== el; }});
            var _broadcastZoom = function(dw) {{
                if (el._suppressZoom) {{ el._suppressZoom = false; return; }}
                window.__dyGroups[grp].forEach(function(peer) {{
                    if (peer.el === el) return;
                    peer.el._suppressZoom = true;
                    peer.instance.updateOptions({{dateWindow: dw}});
                }});
            }};
            opts.zoomCallback = function(a, b) {{ _broadcastZoom([a, b]); }};
            var _userDrawCb = opts.drawCallback;
            opts.drawCallback = function(g, isInitial) {{
                if (_userDrawCb) _userDrawCb(g, isInitial);
                if (isInitial) return;
                _broadcastZoom(g.xAxisRange());
            }};
            opts.highlightCallback = function(event, x, points, row) {{
                if (el._suppressHighlight) return;
                window.__dyGroups[grp].forEach(function(peer) {{
                    if (peer.el === el) return;
                    peer.el._suppressHighlight = true;
                    peer.instance.setSelection(row);
                    peer.el._suppressHighlight = false;
                }});
            }};
            opts.unhighlightCallback = function() {{
                if (el._suppressHighlight) return;
                window.__dyGroups[grp].forEach(function(peer) {{
                    if (peer.el === el) return;
                    peer.el._suppressHighlight = true;
                    peer.instance.clearSelection();
                    peer.el._suppressHighlight = false;
                }});
            }};
        }}

        // Destroy previous instance
        if (el._dygraphInstance) el._dygraphInstance.destroy();

        // Create dygraph
        el._dygraphInstance = new Dygraph(el, rows, opts);
        var g = el._dygraphInstance;

        // Register in group
        if (config.group) {{
            window.__dyGroups[config.group].push({{ el: el, instance: g }});
        }}

        // Annotations
        if (config.annotations && config.annotations.length > 0) {{
            var anns = config.annotations.map(function(a) {{
                return {{
                    series: a.series,
                    x: config.format === 'date' ? new Date(a.x).getTime() : a.x,
                    shortText: a.shortText,
                    text: a.text || '',
                    attachAtBottom: a.attachAtBottom || false
                }};
            }});
            g.setAnnotations(anns);
        }}

        // Shadings
        if (config.shadings && config.shadings.length > 0) {{
            g.updateOptions({{underlayCallback: function(canvas, area, dygraph) {{
                for (var s = 0; s < config.shadings.length; s++) {{
                    var sh = config.shadings[s];
                    canvas.fillStyle = sh.color;
                    if (sh.axis === 'x') {{
                        var from = config.format === 'date' ? new Date(sh.from).getTime() : sh.from;
                        var to = config.format === 'date' ? new Date(sh.to).getTime() : sh.to;
                        var xl = dygraph.toDomXCoord(from), xr = dygraph.toDomXCoord(to);
                        canvas.fillRect(xl, area.y, xr - xl, area.h);
                    }} else {{
                        var yl = dygraph.toDomYCoord(sh.from), yr = dygraph.toDomYCoord(sh.to);
                        canvas.fillRect(area.x, Math.min(yl,yr), area.w, Math.abs(yr-yl));
                    }}
                }}
            }}}});
        }}

        // Events
        if (config.events && config.events.length > 0) {{
            var prevUl = g.getOption('underlayCallback');
            g.updateOptions({{underlayCallback: function(canvas, area, dygraph) {{
                if (prevUl) prevUl(canvas, area, dygraph);
                for (var e = 0; e < config.events.length; e++) {{
                    var ev = config.events[e];
                    canvas.strokeStyle = ev.color || 'black';
                    canvas.lineWidth = 1;
                    if (ev.strokePattern) canvas.setLineDash(ev.strokePattern);
                    canvas.beginPath();
                    if (ev.axis === 'x') {{
                        var pos = config.format === 'date' ? new Date(ev.pos).getTime() : ev.pos;
                        var xp = dygraph.toDomXCoord(pos);
                        canvas.moveTo(xp, area.y); canvas.lineTo(xp, area.y + area.h);
                    }} else {{
                        var yp = dygraph.toDomYCoord(ev.pos);
                        canvas.moveTo(area.x, yp); canvas.lineTo(area.x + area.w, yp);
                    }}
                    canvas.stroke();
                    canvas.setLineDash([]);
                    if (ev.label) {{
                        canvas.fillStyle = ev.color || 'black';
                        canvas.font = '12px sans-serif';
                        if (ev.axis === 'x') {{
                            canvas.fillText(ev.label, xp + 4,
                                ev.labelLoc === 'bottom' ? area.y + area.h - 4 : area.y + 14);
                        }} else {{
                            var llx = ev.labelLoc === 'right'
                                ? area.x + area.w - canvas.measureText(ev.label).width - 4
                                : area.x + 4;
                            canvas.fillText(ev.label, llx, yp - 4);
                        }}
                    }}
                }}
            }}}});
        }}
    }});
    """

    return ui.TagList(
        ui.head_content(
            ui.tags.link(rel="stylesheet", href=_DYGRAPH_CSS_CDN),
            ui.tags.script(src=_DYGRAPH_JS_CDN),
        ),
        ui.div(id=element_id, style=f"width:{width}; height:{height};"),
        ui.tags.script(handler_js),
    )


async def render_dygraph(
    session: Any,
    element_id: str,
    dg: Dygraph,
) -> None:
    """Send dygraph config to the browser via Shiny custom message.

    Call this from a reactive effect or observer to render/update the chart.

    Parameters
    ----------
    session
        Shiny session object.
    element_id
        DOM id matching the ``dygraph_ui()`` call.
    dg
        Configured ``Dygraph`` builder instance.
    """
    config = dg.to_js()
    await session.send_custom_message(f"dygraphs_{element_id}", config)
