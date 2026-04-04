"""Dash integration — render a Dygraph builder into Dash components.

Uses the proven pattern: dcc.Store for data + dcc.Graph (hidden) as
clientside callback output + JS that loads dygraphs on demand.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dash_dygraphs.utils import JS

if TYPE_CHECKING:
    from dash import Dash
    from dash.development.base_component import Component

    from dash_dygraphs.dygraph import Dygraph

ASSETS_DIR = Path(__file__).parent / "assets"

_DYGRAPH_JS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/dygraph/2.2.1/dygraph.min.js"
_DYGRAPH_CSS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/dygraph/2.2.1/dygraph.min.css"


def _build_render_js(
    container_id: str,
    chart_div_id: str,
    height: int,
) -> str:
    """Build the clientside JS that initialises the dygraph.

    Follows the same pattern as the user's proven manual approach:
    load dygraphs on-demand, use dcc.Graph hidden output.
    """
    return f"""function(config) {{
    if (!config) return {{data:[],layout:{{}}}};

    // Load CSS once
    if (!document.getElementById('dygraph-css')) {{
        var l = document.createElement('link');
        l.id = 'dygraph-css'; l.rel = 'stylesheet';
        l.href = '{_DYGRAPH_CSS_CDN}';
        document.head.appendChild(l);
    }}

    function render() {{
        var container = document.getElementById('{container_id}');
        if (!container) return;

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
                    var code = obj[key].slice(7, -6);
                    try {{ obj[key] = eval('(' + code + ')'); }} catch(e) {{}}
                }} else if (typeof obj[key] === 'object') {{
                    processJS(obj[key]);
                }}
            }}
            return obj;
        }}
        processJS(opts);

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

        // Point shapes
        if (config.pointShape) {{
            var shapes = config.pointShape;
            if (shapes.__global__) {{
                opts.drawPointCallback = Dygraph.Circles[shapes.__global__.toUpperCase()];
                opts.drawHighlightPointCallback = Dygraph.Circles[shapes.__global__.toUpperCase()];
            }}
            if (opts.series) {{
                for (var sn in shapes) {{
                    if (sn === '__global__') continue;
                    if (!opts.series[sn]) opts.series[sn] = {{}};
                    opts.series[sn].drawPointCallback = Dygraph.Circles[shapes[sn].toUpperCase()];
                    opts.series[sn].drawHighlightPointCallback = Dygraph.Circles[shapes[sn].toUpperCase()];
                }}
            }}
        }}

        // Create or update dygraph
        var ex = container._dygraphInstance;
        if (ex) {{
            ex.updateOptions(Object.assign({{ file: rows }}, opts));
        }} else {{
            container.innerHTML = '<div id="{chart_div_id}" style="width:100%;height:{height}px"></div>';
            container._dygraphInstance = new Dygraph(
                document.getElementById('{chart_div_id}'), rows, opts);
        }}
        var g = container._dygraphInstance;

        // Annotations
        if (config.annotations && config.annotations.length > 0) {{
            var anns = config.annotations.map(function(a) {{
                var ann = {{
                    series: a.series,
                    x: config.format === 'date' ? new Date(a.x).getTime() : a.x,
                    shortText: a.shortText,
                    text: a.text || '',
                    attachAtBottom: a.attachAtBottom || false
                }};
                if (a.width) ann.width = a.width;
                if (a.height) ann.height = a.height;
                if (a.cssClass) ann.cssClass = a.cssClass;
                if (a.tickHeight) ann.tickHeight = a.tickHeight;
                return ann;
            }});
            g.setAnnotations(anns);
        }}

        // Shadings (underlay callback)
        if (config.shadings && config.shadings.length > 0) {{
            var shadingCb = function(canvas, area, dygraph) {{
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
            }};
            g.updateOptions({{underlayCallback: shadingCb}});
        }}

        // Events (vertical/horizontal lines)
        if (config.events && config.events.length > 0) {{
            var prevUl = g.getOption('underlayCallback');
            var eventCb = function(canvas, area, dygraph) {{
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
            }};
            g.updateOptions({{underlayCallback: eventCb}});
        }}

        // Custom CSS injection
        if (config.css) {{
            var styleId = 'dygraph-css-' + '{container_id}';
            var existing = document.getElementById(styleId);
            if (existing) existing.remove();
            var style = document.createElement('style');
            style.id = styleId;
            style.textContent = config.css;
            document.head.appendChild(style);
        }}
    }}

    // Load dygraphs JS on demand, then render
    if (typeof Dygraph === 'undefined') {{
        var s = document.createElement('script');
        s.src = '{_DYGRAPH_JS_CDN}';
        s.onload = render;
        document.head.appendChild(s);
    }} else {{
        render();
    }}

    return {{data:[], layout:{{}}}};
}}"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def dygraph_to_dash(
    dg: Dygraph,
    *,
    component_id: str | None = None,
    app: Dash | None = None,
    height: str | int = "400px",
    width: str = "100%",
) -> Component:
    """Convert a ``Dygraph`` builder into a Dash component tree.

    Parameters
    ----------
    dg
        Configured Dygraph builder instance.
    component_id
        Unique DOM id prefix. Auto-generated if omitted.
    app
        Dash app to register clientside callbacks on.
    height
        Chart height in pixels or CSS string.
    width
        CSS width for the container.
    """
    from dash import dcc, html
    from dash.dependencies import Input, Output

    cid = component_id or f"dygraph-{uuid.uuid4().hex[:8]}"
    store_id = f"{cid}-store"
    container_id = f"{cid}-container"
    chart_div_id = f"{cid}-chart"
    hidden_graph_id = f"{cid}-hidden-graph"

    # Parse height to pixels
    height_px = int(height.replace("px", "")) if isinstance(height, str) else height

    # Serialise config — handle JS objects
    config = dg.to_dict()

    def _serialise(obj: Any) -> Any:
        if isinstance(obj, JS):
            return f"__JS__:{obj.code}:__JS__"
        if isinstance(obj, dict):
            return {k: _serialise(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_serialise(v) for v in obj]
        return obj

    serialised_config = _serialise(config)

    component = html.Div(
        [
            dcc.Store(id=store_id, data=serialised_config),
            dcc.Graph(id=hidden_graph_id, style={"display": "none"}),
            html.Div(
                id=container_id,
                style={"width": width},
            ),
        ],
        id=cid,
    )

    if app is not None:
        js = _build_render_js(container_id, chart_div_id, height_px)
        app.clientside_callback(
            js,
            Output(hidden_graph_id, "figure"),
            Input(store_id, "data"),
        )

    return component


def register_callbacks(
    app: Dash,
    store_id: str,
    container_id: str,
    chart_div_id: str,
    hidden_graph_id: str,
    height_px: int = 400,
) -> None:
    """Register the clientside callback that initialises the dygraph."""
    from dash.dependencies import Input, Output

    js = _build_render_js(container_id, chart_div_id, height_px)
    app.clientside_callback(
        js,
        Output(hidden_graph_id, "figure"),
        Input(store_id, "data"),
    )
