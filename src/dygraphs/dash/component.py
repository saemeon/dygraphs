"""Dash integration — render a Dygraph builder into Dash components.

Architecture (intentionally transparent — no magic, see "How it works"
in docs/index.md):

- Each chart is two sibling components inside an outer ``html.Div``:
  a ``dcc.Store`` (carries the serialised config; its id is the
  chart's user-facing id), and a chart container ``html.Div``
  (id ``{id}-container``) where the dygraphs JS renders its DOM.
- A per-instance clientside callback listens to the store and calls
  ``window.dygraphsDash.render(setup, config)``. Its dummy output
  targets the store itself with ``allow_duplicate=True`` and returns
  ``dash_clientside.no_update`` — standard Dash idiom for
  "side-effectful clientside callback with no store mutation."
  Requires ``dash>=2.9.0`` for ``allow_duplicate=True`` and
  ``prevent_initial_call='initial_duplicate'``.
- The renderer JS itself lives in ``src/dygraphs/assets/dash_render.js``
  — a real JavaScript file, lintable, syntax-highlightable. This module
  reads it once at import time and inlines it into each per-instance
  callback body (the JS is an IIFE guard, so repeated inlines are
  idempotent).

The :class:`DygraphChart` class is a ``dash_wrap.ComponentWrapper`` over
the ``dcc.Store`` — the chart's *identity* is the Store, so
``Output(chart, "data")`` in a callback resolves to the Store's id.
The wrapper's two mechanisms (both from dash-wrap, both documented):
``_set_random_id`` returns the inner Store's id, and ``__class__`` is
spoofed so ``isinstance(chart, dcc.Store)`` is ``True``.

Public surface:

- :class:`DygraphChart` — the class-based Dash entry (dygraphs JS).
- :class:`StackedBarChart` — canvas-based stacked bar chart with a
  range selector. Sibling of :class:`DygraphChart` with the same
  construction pattern, but a different renderer (no dygraphs.js).

Charts sharing the same ``group`` name automatically sync zoom, pan,
and highlight via a global JS group registry.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from dash import dcc
from dash_wrap import ComponentWrapper, register_proxy_defaults

from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS
from dygraphs.utils import (
    DYGRAPH_CSS_CDN as _DYGRAPH_CSS_CDN,
)
from dygraphs.utils import (
    DYGRAPH_JS_CDN as _DYGRAPH_JS_CDN,
)

# Read the renderer asset once at import time. It's an IIFE that
# populates ``window.dygraphsDash`` on first execution and is a no-op
# on subsequent inlines, so each per-instance clientside callback can
# safely include it without re-initialising.
_DASH_RENDER_JS = (
    Path(__file__).parent.parent / "assets" / "dash_render.js"
).read_text()

# dash-wrap's default registry has no entry for dcc.Store. Register
# "data" so wrap(Store) and DygraphChart auto-proxy the one prop that
# matters. Re-registering the same type is idempotent (replaces).
register_proxy_defaults(dcc.Store, ("data",))

if TYPE_CHECKING:
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
    ``window.dygraphsDash.render(setup, config)``. The full renderer
    logic lives in ``src/dygraphs/assets/dash_render.js``; this
    function only assembles the per-instance ``setup`` payload.
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

    # Inline the (idempotent) renderer asset, then dispatch. The
    # callback's nominal Output is the data store with
    # allow_duplicate=True; returning dash_clientside.no_update means
    # the store is not actually mutated and there's no feedback loop
    # (the same store is also one of this callback's Inputs).
    return (
        "function(config) {\n"
        + _DASH_RENDER_JS
        + "\n"
        + f"    window.dygraphsDash.render({setup_json}, config);\n"
        + "    return window.dash_clientside.no_update;\n"
        + "}"
    )


# ---------------------------------------------------------------------------
# DygraphChart — the primary Dash entry point
# ---------------------------------------------------------------------------


class DygraphChart(ComponentWrapper):
    """Dash component for a dygraphs chart.

    Usage mirrors ``dcc.Graph``::

        from dygraphs import Dygraph
        from dygraphs.dash import DygraphChart

        app.layout = html.Div([
            DygraphChart(figure=dg, id="chart"),
        ])

    **What it actually is.** A ``DygraphChart`` is an ``html.Div`` that
    contains two siblings:

    - ``dcc.Store(id=id, data=<serialised config>)`` — the chart
      store. The chart's identity in the callback registry. Its id
      equals the user-supplied ``id``.
    - ``html.Div(id=f"{id}-container")`` — the container where
      dygraphs renders its JS-driven DOM.

    The class inherits from :class:`dash_wrap.ComponentWrapper` with
    the Store as the *inner* component, so the callback registry
    resolves ``Output(chart, ...)`` to the Store's id. Two small pieces
    of machinery make that work — both shipped by dash-wrap, both
    documented in its README, no magic beyond that:

    - ``_set_random_id`` is overridden on the wrapper to return the
      inner Store's id. Dash's dependency wiring calls this when it
      sees a component passed to ``Output`` / ``Input`` / ``State``.
    - ``__class__`` is a property that returns the inner Store's
      class, so ``isinstance(chart, dcc.Store)`` is ``True``. The
      C-level ``type(chart)`` is still ``DygraphChart``, which is
      what Dash's serialiser uses to emit the DOM (a normal
      ``<div>``).

    A per-instance clientside callback is registered at construction.
    It listens to the store and dispatches to
    ``window.dygraphsDash.render(setup, config)``. The callback body
    inlines ``dash_render.js`` (IIFE-guarded, idempotent) and a tiny
    per-chart ``setup`` payload built by :func:`_build_render_js`.

    Any change to chart options — stroke width, colors, legend — is
    pushed through the same primary store as a fresh config (full
    destroy+recreate, matching R's ``renderDygraph`` model). There's
    no separate "options override" channel; one write path, one
    mental model. See CLAUDE.md "Decisions deferred / opts store" if
    you hit a performance wall and want to reintroduce a cheaper
    cosmetic-updates channel.

    Parameters
    ----------
    figure : Dygraph | None
        Configured Dygraph builder instance, or ``None`` for an empty
        placeholder. With ``None`` the primary store holds ``data=None``
        and the clientside renderer early-returns (``if (!config)
        return;``); users push the first real config via
        ``Output(chart, "data")``. Use case: building an app layout
        where the first chart state arrives only after a callback
        fires (e.g. a button click).
    id : str | None
        User-facing DOM id. Assigned to the primary ``dcc.Store``; the
        opts store gets ``{id}-opts`` and the container div
        ``{id}-container``. Auto-generated if omitted.
    height : str | int
        Chart height in pixels or a CSS height string.
    width : str
        CSS width for the container div.
    modebar : bool
        Show the Plotly-style hover overlay (capture + reset-zoom).

    Examples
    --------
    Updating the chart's data — including restyles — via ``to_js``,
    which returns a Dash-safe dict (see :meth:`Dygraph.to_js`)::

        @callback(Output(chart, "data"), Input("btn", "n_clicks"))
        def refresh(n):
            return Dygraph(df * n).to_js()

        @callback(Output(chart, "data"), Input("thick", "n_clicks"))
        def thick(n):
            return (
                Dygraph(df)
                .options(stroke_width=3 if n else 1)
                .to_js()
            )
    """

    def __init__(
        self,
        figure: Dygraph | None,
        id: str | None = None,  # noqa: A002
        height: str | int = "400px",
        width: str = "100%",
        modebar: bool = True,
    ) -> None:
        from dash import clientside_callback, html
        from dash.dependencies import Input, Output

        cid = id or f"dygraph-{uuid.uuid4().hex[:8]}"
        height_px = int(height.replace("px", "")) if isinstance(height, str) else height
        # figure=None → store holds None; dash_render.js's
        # ``if (!config) return;`` makes the callback a no-op until
        # a real config is pushed.
        serialised_config = figure.to_js() if figure is not None else None

        store = dcc.Store(id=cid, data=serialised_config)
        container_id = f"{cid}-container"
        container = html.Div(id=container_id, style={"width": width})

        # Proxy only ``data``. We deliberately do NOT proxy ``id``:
        # Dash's layout validation walks the tree reading each
        # component's ``.id`` to detect duplicates, and a proxied
        # ``id`` would make the outer wrapper report the same id as
        # the inner Store — tripping ``DuplicateIdError``. Users
        # reach the inner id via :attr:`cid` or by passing the same
        # string they gave the constructor; callback resolution via
        # ``Output(chart, ...)`` still works (dash-wrap's
        # ``_set_random_id`` walks to the inner).
        super().__init__(
            store,
            proxy_props=["data"],
            children=[store, container],
        )
        # Python-side-only attribute (not a Dash prop, not serialised
        # into the DOM). dash-wrap's __setattr__ routes non-proxy
        # names through super() to html.Div / object.
        self._cid = cid

        # Per-instance clientside callback. Dummy output targets the
        # primary store with allow_duplicate=True; JS returns
        # dash_clientside.no_update so the store isn't mutated.
        js = _build_render_js(
            cid, container_id, f"{cid}-chart", height_px, modebar=modebar
        )
        clientside_callback(
            js,
            Output(cid, "data", allow_duplicate=True),
            Input(cid, "data"),
            prevent_initial_call="initial_duplicate",
        )

    @property
    def chart_id(self) -> str:
        """The chart id — equals the inner ``dcc.Store``'s ``id``.

        Exposed under ``chart_id`` rather than ``id`` because Dash's
        layout validation reads ``.id`` on every component to detect
        duplicates. Proxying ``id`` to the inner store would make
        the outer wrapper and the inner store look like duplicates
        even though only the inner is rendered with an id.

        Use this when you need the id as a string — for example to
        construct sibling ids (``f"{chart.chart_id}-download"``) or
        pass to :class:`dash.Output` alongside derived ids. For the
        direct callback wire-up, ``Output(chart, "data")`` works just
        as well (dash-wrap resolves it to the store's id).
        """
        return self._cid

    def __getattr__(self, name: str) -> Any:
        """Proxy to dash-wrap's default handler, with one friendly error.

        Users coming from ``dcc.Graph`` habitually reach for
        ``chart.id``. The wrapper deliberately has no ``id``
        attribute (to avoid Dash's duplicate-id validation tripping
        against the inner store), so the default lookup would raise
        a generic ``AttributeError``. Intercept that one case with a
        message that points to :attr:`chart_id`.
        """
        if name == "id":
            raise AttributeError(
                "DygraphChart has no 'id' attribute — use '.chart_id' "
                "to read the chart's id. The outer wrapper stays "
                "id-less to avoid Dash's duplicate-id validation; the "
                "real id lives on the inner dcc.Store and is what "
                "Output(chart, ...) resolves to."
            )
        return super().__getattr__(name)


# ---------------------------------------------------------------------------
# StackedBarChart — canvas stacked bar with range selector
# ---------------------------------------------------------------------------


def _build_stacked_bar_js(
    graph_id: str,
    container_id: str,
    *,
    colors: list[str] | None,
    height: int,
    title: str,
    selector_height: int,
    group: str | None,
) -> str:
    """Build the clientside callback body for one stacked-bar instance.

    Kept as a separate helper so :class:`StackedBarChart.__init__` stays
    readable. The JS draws directly on a ``<canvas>`` — this chart type
    doesn't use dygraphs.js at all (different renderer, different
    semantics from :class:`DygraphChart`).
    """
    colors_json = json.dumps(colors or [])
    title_str = json.dumps(title)
    mt = 40 if title else 12
    sh = selector_height
    group_json = json.dumps(group)

    return f"""function(csvData) {{
        var container = document.getElementById('{container_id}');
        if (!container) return window.dash_clientside.no_update;

        function render() {{
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
        return window.dash_clientside.no_update;
    }}"""


class StackedBarChart(ComponentWrapper):
    """Canvas-based stacked bar chart with interactive range selector.

    Sibling of :class:`DygraphChart` — same class-based construction
    pattern, same dash-wrap identity mechanics — but a completely
    different renderer: this one draws directly on a ``<canvas>`` and
    does not use dygraphs.js at all. The trade-off is interactivity
    scope: built-in pan / zoom via a range selector, but no group
    sync with highlights the way :class:`DygraphChart` has.

    Layout — two siblings inside an ``html.Div``:

    - ``dcc.Store(id={id}, data=initial_data_csv)`` — the chart's
      identity. Push a fresh CSV string via ``Output(chart, "data")``.
    - ``html.Div(id={id}-container)`` — the container where the
      canvas is drawn.

    Parameters
    ----------
    id : str | None
        User-facing DOM id. Assigned to the data store; container gets
        ``{id}-container``. Auto-generated if omitted.
    initial_data : str
        Initial CSV data. Must start with a ``Date,...`` header row.
        Empty string renders nothing until a callback pushes data.
    colors : list[str] | None
        Hex / CSS colors, one per non-date column. Falls back to a
        built-in palette when omitted.
    height : int
        Main chart height in pixels.
    title : str
        Chart title, drawn on the canvas above the plot.
    selector_height : int
        Height of the range-selector strip at the bottom.
    group : str | None
        Sync group name. Charts sharing the same name coordinate their
        x-axis window via the ``window.__dyGroups`` registry — same
        mechanism used by :class:`DygraphChart`.

    Examples
    --------
    ::

        from dygraphs.dash import StackedBarChart

        chart = StackedBarChart(
            id="bars",
            initial_data="Date,A,B\\n2024-01-01,1,2\\n2024-01-02,3,4",
            title="Stacked demo",
        )

        @callback(Output(chart, "data"), Input("refresh", "n_clicks"))
        def refresh(_n):
            return updated_csv_string
    """

    def __init__(
        self,
        id: str | None = None,  # noqa: A002
        *,
        initial_data: str = "",
        colors: list[str] | None = None,
        height: int = 300,
        title: str = "",
        selector_height: int = 40,
        group: str | None = None,
    ) -> None:
        from dash import clientside_callback, html
        from dash.dependencies import Input, Output

        cid = id or f"stacked-bar-{uuid.uuid4().hex[:8]}"
        container_id = f"{cid}-container"

        store = dcc.Store(id=cid, data=initial_data)
        container = html.Div(id=container_id)

        # Proxy ``data`` so ``Output(chart, "data")`` targets the inner
        # store. See DygraphChart for why we don't proxy ``id``.
        super().__init__(
            store,
            proxy_props=["data"],
            children=[store, container],
        )
        self._cid = cid

        # Per-instance clientside callback. Same dummy-output +
        # allow_duplicate idiom as DygraphChart.
        js = _build_stacked_bar_js(
            cid,
            container_id,
            colors=colors,
            height=height,
            title=title,
            selector_height=selector_height,
            group=group,
        )
        clientside_callback(
            js,
            Output(cid, "data", allow_duplicate=True),
            Input(cid, "data"),
            prevent_initial_call="initial_duplicate",
        )

    @property
    def chart_id(self) -> str:
        """The chart id — equals the inner ``dcc.Store``'s ``id``."""
        return self._cid

    def __getattr__(self, name: str) -> Any:
        """Friendly error for ``.id`` access; see :class:`DygraphChart`."""
        if name == "id":
            raise AttributeError(
                "StackedBarChart has no 'id' attribute — use "
                "'.chart_id' to read the chart's id. The outer wrapper "
                "stays id-less to avoid Dash's duplicate-id validation."
            )
        return super().__getattr__(name)
