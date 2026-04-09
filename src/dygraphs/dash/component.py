"""Dash integration — render a Dygraph builder into Dash components.

Uses the proven pattern: dcc.Store for data + dcc.Graph (hidden) as
clientside callback output + JS that loads dygraphs on demand.

The renderer JS itself lives in ``src/dygraphs/assets/dash_render.js``
— a real JavaScript file, lintable, syntax-highlightable. This module
loads it at import time and emits a tiny per-instance shim that
dispatches to ``window.dygraphsDash.render(setup, config, opts)``.

Includes:
- dygraph_to_dash() — render a Dygraph builder into Dash layout
- stacked_bar()     — canvas stacked bar with interactive range selector

Charts sharing the same ``group`` name automatically sync zoom, pan,
and highlight via a global JS group registry.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS
from dygraphs.utils import (
    DYGRAPH_CSS_CDN as _DYGRAPH_CSS_CDN,
)
from dygraphs.utils import (
    DYGRAPH_JS_CDN as _DYGRAPH_JS_CDN,
)
from dygraphs.utils import (
    serialise_js,
)

# Read the renderer asset once at import time. It's an IIFE that
# populates ``window.dygraphsDash`` on first execution and is a no-op
# on subsequent inlines, so each per-instance clientside callback can
# safely include it without re-initialising.
_DASH_RENDER_JS = (
    Path(__file__).parent.parent / "assets" / "dash_render.js"
).read_text()

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
    """Build the clientside callback shim for one chart instance.

    Inlines :data:`_DASH_RENDER_JS` (idempotent) and dispatches to
    ``window.dygraphsDash.render(setup, config, optsOverride)``. The
    full renderer logic lives in ``src/dygraphs/assets/dash_render.js``;
    this function only assembles the per-instance ``setup`` payload.
    """
    js_id = _safe_js_id(graph_id)
    modebar_html = ""
    if modebar:
        modebar_html = (
            f'<div class="dy-modebar">'
            f'<button title="Download as PNG" onclick="window.__dyCap_{js_id}()">{_ICON_CAMERA}</button>'
            f'<button title="Reset zoom" onclick="window.__dyReset_{js_id}()">{_ICON_HOME}</button>'
            f"</div>"
        )

    setup_json = json.dumps(
        {
            "containerId": container_id,
            "chartDivId": chart_div_id,
            "graphId": graph_id,
            "height": height,
            "modebar": modebar,
            "cdnCssUrl": _DYGRAPH_CSS_CDN,
            "cdnJsUrl": _DYGRAPH_JS_CDN,
            "modebarCss": _MODEBAR_CSS,
            "modebarHtml": modebar_html,
            "captureJs": MULTI_CANVAS_CAPTURE_JS,
        }
    )

    # Inline the (idempotent) renderer asset, then dispatch.
    return (
        "function(config, optsOverride) {\n"
        + _DASH_RENDER_JS
        + "\n"
        + f"    window.dygraphsDash.render({setup_json}, config, optsOverride);\n"
        + "    return {data: [], layout: {}};\n"
        + "}"
    )


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
