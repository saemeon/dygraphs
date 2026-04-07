"""Dash integration — render a Dygraph builder into Dash components.

Uses the proven pattern: dcc.Store for data + dcc.Graph (hidden) as
clientside callback output + JS that loads dygraphs on demand.

Includes:
- dygraph_to_dash() — render a Dygraph builder into Dash layout
- stacked_bar()     — canvas stacked bar with interactive range selector

Charts sharing the same ``group`` name automatically sync zoom, pan,
and highlight via a global JS group registry.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

from dygraphs.utils import (
    DYGRAPH_CSS_CDN as _DYGRAPH_CSS_CDN,
)
from dygraphs.utils import (
    DYGRAPH_JS_CDN as _DYGRAPH_JS_CDN,
)
from dygraphs.utils import (
    serialise_js,
)

if TYPE_CHECKING:
    from dash import Dash
    from dash.development.base_component import Component

    from dygraphs.dygraph import Dygraph

# ---------------------------------------------------------------------------
# Modebar SVG icons
# ---------------------------------------------------------------------------

_ICON_CAMERA = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 '
    '1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>'
)
_ICON_HOME = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'
    '<polyline points="9 22 9 12 15 12 15 22"/></svg>'
)

# ---------------------------------------------------------------------------
# Modebar CSS (injected once)
# ---------------------------------------------------------------------------

_MODEBAR_CSS = """
.dy-modebar { position:absolute; top:4px; right:4px; display:flex; gap:2px;
  opacity:0; transition:opacity 0.2s; z-index:10; }
.dy-modebar-wrap:hover .dy-modebar { opacity:1; }
.dy-modebar button { background:rgba(255,255,255,0.85); border:1px solid #ddd;
  border-radius:3px; cursor:pointer; padding:3px 5px; color:#555;
  display:flex; align-items:center; justify-content:center; }
.dy-modebar button:hover { background:#f0f0f0; color:#111; }
"""


def _safe_js_id(s: str) -> str:
    """Convert a DOM id to a valid JS identifier fragment."""
    return s.replace("-", "_").replace(".", "_")


def _build_render_js(
    graph_id: str,
    container_id: str,
    chart_div_id: str,
    height: int,
    *,
    modebar: bool = True,
) -> str:
    """Build the clientside JS that initialises the dygraph."""
    js_id = _safe_js_id(graph_id)
    modebar_html = ""
    if modebar:
        modebar_html = (
            f'<div class="dy-modebar">'
            f'<button title="Download as PNG" onclick="window.__dyCap_{js_id}()">{_ICON_CAMERA}</button>'
            f'<button title="Reset zoom" onclick="window.__dyReset_{js_id}()">{_ICON_HOME}</button>'
            f"</div>"
        )
        modebar_html = modebar_html.replace('"', '\\"')

    return f"""function(config, optsOverride) {{
    if (!config) return {{data:[],layout:{{}}}};

    // Load CSS once
    if (!document.getElementById('dygraph-css')) {{
        var l = document.createElement('link');
        l.id = 'dygraph-css'; l.rel = 'stylesheet';
        l.href = '{_DYGRAPH_CSS_CDN}';
        document.head.appendChild(l);
    }}
    if (!document.getElementById('dy-modebar-css')) {{
        var ms = document.createElement('style');
        ms.id = 'dy-modebar-css';
        ms.textContent = {json.dumps(_MODEBAR_CSS)};
        document.head.appendChild(ms);
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

        // Merge runtime options override
        if (optsOverride && typeof optsOverride === 'object') {{
            Object.assign(opts, optsOverride);
            processJS(opts);
        }}

        // Group-based sync: zoom + highlight across charts sharing config.group.
        // Initialise global group registry.
        if (!window.__dyGroups) window.__dyGroups = {{}};

        if (config.group) {{
            var grp = config.group;
            if (!window.__dyGroups[grp]) window.__dyGroups[grp] = [];
            // Remove stale entry for this container (re-render)
            window.__dyGroups[grp] = window.__dyGroups[grp].filter(
                function(e) {{ return e.id !== '{graph_id}'; }});
        }}

        // Zoom broadcast with debounce (drawCallback fires during range-selector panning)
        var _broadcastZoom = function(dw) {{
            if (container._suppressZoom) {{
                container._suppressZoom = false;
                container._lastBroadcastDW = dw;
                return;
            }}
            var prev = container._lastBroadcastDW;
            if (prev && prev[0] === dw[0] && prev[1] === dw[1]) return;
            clearTimeout(container._zoomDebounce);
            container._zoomDebounce = setTimeout(function() {{
                container._lastBroadcastDW = dw;
                if (!config.group || !window.__dyGroups[config.group]) return;
                window.__dyGroups[config.group].forEach(function(peer) {{
                    if (peer.id === '{graph_id}') return;
                    peer.el._suppressZoom = true;
                    peer.el._lastBroadcastDW = dw;
                    if (peer.instance) {{
                        peer.instance.updateOptions({{dateWindow: dw}});
                    }} else if (peer.setDateWindow) {{
                        peer.setDateWindow(dw);
                    }}
                }});
            }}, 30);
        }};
        opts.zoomCallback = function(a, b) {{
            _broadcastZoom([a, b]);
        }};
        var _userDrawCb = opts.drawCallback;
        opts.drawCallback = function(g, isInitial) {{
            if (_userDrawCb) _userDrawCb(g, isInitial);
            if (isInitial) return;
            var dw = g.xAxisRange();
            _broadcastZoom([dw[0], dw[1]]);
        }};

        // Highlight sync: hover one chart → highlight same row in group
        if (config.group) {{
            var _userHighlightCb = opts.highlightCallback;
            opts.highlightCallback = function(event, x, points, row, seriesName) {{
                if (_userHighlightCb) _userHighlightCb(event, x, points, row, seriesName);
                if (container._suppressHighlight) return;
                window.__dyGroups[config.group].forEach(function(peer) {{
                    if (peer.id === '{graph_id}' || !peer.instance) return;
                    peer.el._suppressHighlight = true;
                    peer.instance.setSelection(row);
                    peer.el._suppressHighlight = false;
                }});
            }};
            var _userUnhighlightCb = opts.unhighlightCallback;
            opts.unhighlightCallback = function(event) {{
                if (_userUnhighlightCb) _userUnhighlightCb(event);
                if (container._suppressHighlight) return;
                window.__dyGroups[config.group].forEach(function(peer) {{
                    if (peer.id === '{graph_id}' || !peer.instance) return;
                    peer.el._suppressHighlight = true;
                    peer.instance.clearSelection();
                    peer.el._suppressHighlight = false;
                }});
            }};
        }}

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
            container.innerHTML = '<div class="dy-modebar-wrap" style="position:relative">' +
                '<div id="{chart_div_id}" style="width:100%;height:{height}px"></div>' +
                '{modebar_html}</div>';
            container._dygraphInstance = new Dygraph(
                document.getElementById('{chart_div_id}'), rows, opts);
        }}
        var g = container._dygraphInstance;

        // Register in group for sync
        if (config.group && window.__dyGroups[config.group]) {{
            window.__dyGroups[config.group].push({{
                id: '{graph_id}', el: container, instance: g
            }});
        }}

        // ResizeObserver for responsive resize
        if (!container._resizeObserver) {{
            container._resizeObserver = new ResizeObserver(function() {{
                if (container._dygraphInstance) {{
                    container._dygraphInstance.resize();
                }}
            }});
            container._resizeObserver.observe(container);
        }}

        // Capture (download PNG) function
        window.__dyCap_{js_id} = function() {{
            var chartEl = document.getElementById('{chart_div_id}');
            if (!chartEl) return;
            // Hide range selector temporarily
            var rs = chartEl.querySelector('.dygraph-rangesel-fgcanvas');
            var rsBg = chartEl.querySelector('.dygraph-rangesel-bgcanvas');
            var rsZ = chartEl.querySelector('.dygraph-rangesel-zoomhandle');
            var hidden = [rs, rsBg, rsZ].filter(function(e){{ return e; }});
            hidden.forEach(function(e){{ e.style.display = 'none'; }});
            // Use html2canvas if available, else fallback to canvas merge
            var canvases = chartEl.querySelectorAll('canvas');
            if (canvases.length > 0) {{
                var c = document.createElement('canvas');
                c.width = chartEl.offsetWidth;
                c.height = chartEl.offsetHeight;
                var ctx = c.getContext('2d');
                ctx.fillStyle = 'white';
                ctx.fillRect(0, 0, c.width, c.height);
                // Draw all visible canvases
                canvases.forEach(function(cv) {{
                    if (cv.style.display === 'none') return;
                    var r = cv.getBoundingClientRect();
                    var pr = chartEl.getBoundingClientRect();
                    ctx.drawImage(cv, r.left - pr.left, r.top - pr.top);
                }});
                // Draw title and labels (they're in regular divs)
                var a = document.createElement('a');
                a.download = '{graph_id}.png';
                a.href = c.toDataURL('image/png');
                a.click();
            }}
            hidden.forEach(function(e){{ e.style.display = ''; }});
        }};

        // Reset zoom function
        window.__dyReset_{js_id} = function() {{
            if (container._dygraphInstance) container._dygraphInstance.resetZoom();
        }};

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
# dygraph_to_dash
# ---------------------------------------------------------------------------


def dygraph_to_dash(
    dg: Dygraph,
    *,
    component_id: str | None = None,
    app: Dash | None = None,
    height: str | int = "400px",
    width: str = "100%",
    modebar: bool = True,
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
    modebar
        Show Plotly-style overlay buttons (capture, reset zoom).
    """
    from dash import dcc, html
    from dash.dependencies import Input, Output

    cid = component_id or f"dygraph-{uuid.uuid4().hex[:8]}"
    store_id = f"{cid}-store"
    opts_store_id = f"{cid}-opts"
    container_id = f"{cid}-container"
    chart_div_id = f"{cid}-chart"
    hidden_graph_id = f"{cid}-hidden-graph"

    height_px = int(height.replace("px", "")) if isinstance(height, str) else height

    # Serialise config — handle JS objects
    config = dg.to_dict()
    serialised_config = serialise_js(config)

    component = html.Div(
        [
            dcc.Store(id=store_id, data=serialised_config),
            dcc.Store(id=opts_store_id, data=None),
            dcc.Graph(id=hidden_graph_id, style={"display": "none"}),
            html.Div(id=container_id, style={"width": width}),
        ],
        id=cid,
    )

    if app is not None:
        js = _build_render_js(
            cid, container_id, chart_div_id, height_px, modebar=modebar
        )
        app.clientside_callback(
            js,
            Output(hidden_graph_id, "figure"),
            Input(store_id, "data"),
            Input(opts_store_id, "data"),
        )

    return component


# ---------------------------------------------------------------------------
# stacked_bar — canvas stacked bar with range selector
# ---------------------------------------------------------------------------


def stacked_bar(
    app: Dash,
    graph_id: str,
    initial_data: str = "",
    *,
    colors: list[str] | None = None,
    height: int = 300,
    title: str = "",
    selector_height: int = 40,
    group: str | None = None,
) -> Component:
    """Create a canvas-based stacked bar chart with interactive range selector.

    Parameters
    ----------
    app
        Dash app instance.
    graph_id
        Unique component ID prefix.
    initial_data
        CSV string with Date column + value columns.
    colors
        Color palette for the series.
    height
        Chart height in pixels.
    title
        Chart title.
    selector_height
        Range selector height in pixels.
    group
        Synchronisation group name. Charts sharing the same group name
        will sync their x-axis zoom/pan.
    """
    from dash import dcc, html
    from dash.dependencies import Input, Output

    store_id = graph_id
    container_id = f"{graph_id}-container"
    hidden_graph_id = f"{graph_id}-hidden-graph"

    colors_json = json.dumps(colors or [])
    title_str = json.dumps(title)
    mt = 40 if title else 12
    sh = selector_height

    group_json = json.dumps(group)

    js = f"""function(csvData) {{
        function render() {{
            var container = document.getElementById('{container_id}');
            if (!container) return;

            var lines = csvData.trim().split('\\n');
            var series = lines[0].split(',').slice(1);
            var n = series.length;
            var dates=[], rows=[];
            for (var i=1;i<lines.length;i++) {{
                var p=lines[i].split(',');
                dates.push(new Date(p[0]));
                rows.push(p.slice(1).map(Number));
            }}
            var allMs0 = dates[0].getTime();
            var allMs1 = dates[dates.length-1].getTime();

            var def = ['#00d4aa','#f4a261','#7eb8f7','#f76e8a','#c084fc',
                       '#34d399','#fbbf24','#60a5fa','#f87171','#a78bfa'];
            var uc = {colors_json};
            var clrs = uc.length ? uc : def.slice(0,n);

            var yMin=0, yMax=0;
            rows.forEach(function(row) {{
                var pos=0,neg=0;
                row.forEach(function(v){{ if(v>=0) pos+=v; else neg+=v; }});
                if(pos>yMax) yMax=pos; if(neg<yMin) yMin=neg;
            }});
            var yPad=(yMax-yMin)*0.08||1; yMin-=yPad; yMax+=yPad;

            var xMinMs = container._groupDateWindow
                ? Math.max(container._groupDateWindow[0], allMs0) : allMs0;
            var xMaxMs = container._groupDateWindow
                ? Math.min(container._groupDateWindow[1], allMs1) : allMs1;

            var W = container.clientWidth || 800;
            var H = {height};
            var SH = {sh};
            var TH = H + 6 + SH + 16;
            var ml=60, mr=20, mt={mt}, mb=28;
            var pw=W-ml-mr, ph=H-mt-mb;
            var smt=H+6, sph=SH;

            container.innerHTML = '<canvas id="{graph_id}-canvas" width="'+W+
                '" height="'+TH+'" style="display:block;cursor:ew-resize"></canvas>';
            var cv = document.getElementById('{graph_id}-canvas');
            var cx2 = cv.getContext('2d');
            cx2.clearRect(0,0,W,TH);

            function toX(ms)  {{ return ml+(ms-xMinMs)/(xMaxMs-xMinMs)*pw; }}
            function toY(v)   {{ return mt+ph-(v-yMin)/(yMax-yMin)*ph; }}
            function sToX(ms) {{ return ml+(ms-allMs0)/(allMs1-allMs0)*pw; }}
            function sToY(v)  {{ return smt+sph-(v-yMin)/(yMax-yMin)*sph; }}

            // Grid
            cx2.lineWidth=1;
            for (var gi=0;gi<=5;gi++) {{
                var gv=yMin+(yMax-yMin)*gi/5, gy=toY(gv);
                cx2.strokeStyle='#e8e8e8';
                cx2.beginPath(); cx2.moveTo(ml,gy); cx2.lineTo(ml+pw,gy); cx2.stroke();
                cx2.fillStyle='#666'; cx2.font='11px sans-serif'; cx2.textAlign='right';
                cx2.fillText(gv.toFixed(1),ml-6,gy+4);
            }}
            cx2.strokeStyle='#aaa'; cx2.lineWidth=1.5;
            var y0=toY(0);
            cx2.beginPath(); cx2.moveTo(ml,y0); cx2.lineTo(ml+pw,y0); cx2.stroke();

            // Bars
            var vis=[];
            for (var i=0;i<dates.length;i++) {{
                var ms=dates[i].getTime();
                if (ms>=xMinMs && ms<=xMaxMs) vis.push(i);
            }}
            if (!vis.length) vis=dates.map(function(_,i){{return i;}});
            var bw=Math.max(1,pw/vis.length*0.85);
            vis.forEach(function(ri) {{
                var x=toX(dates[ri].getTime()), pt=0, nb=0;
                for (var si=0;si<n;si++) {{
                    var v=rows[ri][si], yt, yb;
                    if (v>=0) {{ yt=toY(pt+v); yb=toY(pt); pt+=v; }}
                    else      {{ yb=toY(nb+v); yt=toY(nb); nb+=v; }}
                    cx2.fillStyle=clrs[si%clrs.length];
                    cx2.fillRect(x-bw/2,yt,bw,yb-yt);
                }}
            }});

            // Title
            var ts={title_str};
            if (ts) {{
                cx2.fillStyle='#111'; cx2.font='bold 14px sans-serif';
                cx2.textAlign='center'; cx2.fillText(ts,W/2,22);
            }}

            // Legend
            if (n<=8) {{
                var lw=series.reduce(function(a,s){{return a+s.length*7+24;}},0);
                var lx=(W-lw)/2;
                cx2.font='12px sans-serif'; cx2.textAlign='left';
                series.forEach(function(s,si) {{
                    cx2.fillStyle=clrs[si%clrs.length]; cx2.fillRect(lx,H-mb+2,14,10);
                    cx2.fillStyle='#444'; cx2.fillText(s,lx+18,H-mb+12);
                    lx+=s.length*7+28;
                }});
            }}

            // Range selector
            cx2.fillStyle='#ececec';
            cx2.fillRect(ml,smt,pw,sph);
            var mbw=Math.max(1,pw/dates.length*0.9);
            cx2.save(); cx2.globalAlpha=0.6;
            dates.forEach(function(d,ri) {{
                var x=sToX(d.getTime()), pt=0, nb=0;
                for (var si=0;si<n;si++) {{
                    var v=rows[ri][si], yt, yb;
                    if (v>=0) {{ yt=sToY(pt+v); yb=sToY(pt); pt+=v; }}
                    else      {{ yb=sToY(nb+v); yt=sToY(nb); nb+=v; }}
                    cx2.fillStyle=clrs[si%clrs.length];
                    cx2.fillRect(x-mbw/2,yt,mbw,yb-yt);
                }}
            }});
            cx2.restore();

            var selL=sToX(xMinMs), selR=sToX(xMaxMs);
            cx2.fillStyle='rgba(255,255,255,0.6)';
            cx2.fillRect(ml,smt,selL-ml,sph);
            cx2.fillRect(selR,smt,ml+pw-selR,sph);
            cx2.strokeStyle='#888'; cx2.lineWidth=1;
            cx2.strokeRect(selL,smt,selR-selL,sph);
            cx2.fillStyle='rgba(80,80,80,0.5)';
            cx2.fillRect(selL-4,smt,4,sph);
            cx2.fillRect(selR,smt,4,sph);

            cx2.fillStyle='#666'; cx2.font='10px sans-serif'; cx2.textAlign='center';
            for (var li=0;li<=6;li++) {{
                var ms=allMs0+(allMs1-allMs0)*li/6;
                cx2.fillText(new Date(ms).toISOString().slice(0,10), sToX(ms), smt+sph+14);
            }}

            container._state = {{ allMs0:allMs0, allMs1:allMs1, ml:ml, pw:pw,
                                   smt:smt, sph:sph, xMinMs:xMinMs, xMaxMs:xMaxMs }};

            // Mouse interaction for range selector
            if (container._onMouseDown)
                cv.removeEventListener('mousedown', container._onMouseDown);

            container._onMouseDown = function(e) {{
                var rect = cv.getBoundingClientRect();
                var mx = e.clientX - rect.left;
                var my = e.clientY - rect.top;
                var st = container._state;
                var sL = st.ml + (st.xMinMs-st.allMs0)/(st.allMs1-st.allMs0)*st.pw;
                var sR = st.ml + (st.xMaxMs-st.allMs0)/(st.allMs1-st.allMs0)*st.pw;
                var span = st.xMaxMs - st.xMinMs;

                var mode = null;
                if (my >= st.smt && my <= st.smt+st.sph) {{
                    if      (Math.abs(mx-sL) <= 6) mode='resize-l';
                    else if (Math.abs(mx-sR) <= 6) mode='resize-r';
                    else if (mx > sL && mx < sR)   mode='pan';
                    else                            mode='jump';
                }}
                if (!mode) return;

                var sx0=mx, mn0=st.xMinMs, mx0=st.xMaxMs;
                function msFromX(x) {{ return st.allMs0 + (x-st.ml)/st.pw*(st.allMs1-st.allMs0); }}
                function clampAndBroadcast(newMin, newMax) {{
                    if (newMin < st.allMs0) {{ newMin=st.allMs0; newMax=newMin+span; }}
                    if (newMax > st.allMs1) {{ newMax=st.allMs1; newMin=newMax-span; }}
                    newMin=Math.max(newMin,st.allMs0);
                    newMax=Math.min(newMax,st.allMs1);
                    container._groupDateWindow = [newMin, newMax];
                    // Re-render this chart with new window
                    render();
                    // Broadcast to group peers
                    var grpName = {group_json};
                    if (grpName && window.__dyGroups && window.__dyGroups[grpName]) {{
                        window.__dyGroups[grpName].forEach(function(peer) {{
                            if (peer.id === '{graph_id}') return;
                            peer.el._suppressZoom = true;
                            peer.el._lastBroadcastDW = [newMin, newMax];
                            if (peer.instance) {{
                                peer.instance.updateOptions({{dateWindow: [newMin, newMax]}});
                            }} else if (peer.setDateWindow) {{
                                peer.setDateWindow([newMin, newMax]);
                            }}
                        }});
                    }}
                }}

                if (mode==='jump') {{
                    var c=msFromX(mx); clampAndBroadcast(c-span/2, c+span/2); return;
                }}
                function onMove(e2) {{
                    var dx = e2.clientX - rect.left - sx0;
                    var dMs = dx/st.pw*(st.allMs1-st.allMs0);
                    if      (mode==='pan')      clampAndBroadcast(mn0+dMs, mx0+dMs);
                    else if (mode==='resize-l') clampAndBroadcast(Math.min(mn0+dMs,mx0-1), mx0);
                    else if (mode==='resize-r') clampAndBroadcast(mn0, Math.max(mx0+dMs,mn0+1));
                }}
                function onUp() {{
                    document.removeEventListener('mousemove',onMove);
                    document.removeEventListener('mouseup',onUp);
                }}
                document.addEventListener('mousemove',onMove);
                document.addEventListener('mouseup',onUp);
            }};
            cv.addEventListener('mousedown', container._onMouseDown);
        }}

        // Register in group for sync
        var grpName = {group_json};
        if (grpName) {{
            if (!window.__dyGroups) window.__dyGroups = {{}};
            if (!window.__dyGroups[grpName]) window.__dyGroups[grpName] = [];
            window.__dyGroups[grpName] = window.__dyGroups[grpName].filter(
                function(e) {{ return e.id !== '{graph_id}'; }});
            window.__dyGroups[grpName].push({{
                id: '{graph_id}', el: container, instance: null,
                setDateWindow: function(dw) {{
                    container._groupDateWindow = dw;
                    render();
                }}
            }});
        }}

        render();
        return {{data:[],layout:{{}}}};
    }}"""

    app.clientside_callback(
        js,
        Output(hidden_graph_id, "figure"),
        Input(store_id, "data"),
    )

    return html.Div(
        [
            dcc.Store(id=store_id, data=initial_data),
            dcc.Graph(id=hidden_graph_id, style={"display": "none"}),
            html.Div(id=container_id),
        ]
    )
