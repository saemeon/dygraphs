"""Custom modebar buttons for ``DygraphChart``.

This module provides :class:`DyModebarButton`, a Dash trigger that
injects a custom button into the dygraph's modebar overlay and exposes
the same bridge protocol as ``dash_capture.ModebarButton``.

Usage::

    from dash_capture import capture_element
    from dygraphs.dash import DygraphChart, DyModebarButton, dygraph_strategy

    chart = DygraphChart(figure=dg, id="sales", height="320px")

    wizard = capture_element(
        "sales-container",
        trigger=DyModebarButton(
            graph_id="sales",
            label="Save as report",
            icon="<svg ...>...</svg>",
        ),
        renderer=my_renderer,
        capture_resolver=resolve,
        strategy=dygraph_strategy(),
    )

    app.layout = html.Div([chart, wizard])

The bridge ``html.Div`` is folded into the wizard component returned by
``capture_element``, so the user never has to mount it separately —
exactly the same UX as ``ModebarButton`` for plotly's modebar.

Why this is so much simpler than the plotly equivalent
------------------------------------------------------
The dygraphs modebar (see :mod:`dygraphs.dash.component`) is plain
static HTML embedded once at chart construction time by
``_build_render_js``. Nothing rebuilds it after, so we can do a
one-shot DOM mutation to inject our button. No retry loop, no
``afterplot`` event listener, no race against an internal
``manageModeBar()`` rebuild.

Compare to ``dash_capture._modebar``: that file's ~150 lines exist
because plotly's ``manageModeBar`` keeps wiping injected buttons after
``relayout`` calls. We have none of that fragility here.
"""

from __future__ import annotations

import secrets

import dash
from dash import html
from dash.dependencies import Input, Output


class DyModebarButton:
    """A custom button on a ``DygraphChart``'s modebar.

    Implements the bridge protocol expected by
    ``dash_capture.capture_element(trigger=...)``: exposes a hidden
    ``bridge`` ``html.Div`` (with ``n_clicks``) and an ``open_input``
    that the wizard listens on. ``capture_element`` detects the
    protocol via ``hasattr(trigger, "bridge") and hasattr(trigger,
    "open_input")`` and folds the bridge into the wizard's returned
    component.

    Construction is side-effecting: it registers a clientside callback
    that runs once when the chart's render store updates, finds the
    chart's modebar in the DOM, and appends a ``<button>`` whose
    ``onclick`` clicks the bridge.

    Parameters
    ----------
    graph_id :
        The ``id=`` you passed to ``DygraphChart``. The injector targets
        ``#{graph_id}-container .dy-modebar`` to find where to append.
    label :
        ``title`` attribute on the rendered button — shown as a tooltip
        on hover. Also used as the ARIA label.
    icon :
        Inner HTML of the button. Typically a small inline ``<svg>``.
        Defaults to a download glyph.

    Attributes
    ----------
    bridge : html.Div
        The hidden bridge component. Mount it anywhere in the layout —
        ``capture_element`` does this for you when you pass the
        ``DyModebarButton`` as ``trigger=``.
    open_input : Input
        ``Input(bridge.id, "n_clicks")``. Used by the wizard to open
        on click, and exposed in case you want to wire the button to
        something other than dash-capture (e.g. a custom callback).
    """

    DEFAULT_ICON = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
        '<polyline points="7 10 12 15 17 10"/>'
        '<line x1="12" y1="15" x2="12" y2="3"/></svg>'
    )

    def __init__(
        self,
        *,
        graph_id: str,
        label: str = "Custom action",
        icon: str = "",
    ):
        self.graph_id = graph_id
        self.label = label
        self.icon = icon or self.DEFAULT_ICON

        # Random suffix so multiple buttons on the same chart, or the
        # same chart on different pages, don't collide.
        suffix = secrets.token_hex(4)
        self._bridge_id = f"_dy_mb_bridge_{graph_id}_{suffix}"
        self._marker = f"_dy_mb_{suffix}"  # idempotency guard on the DOM node

        self.bridge = html.Div(
            id=self._bridge_id,
            n_clicks=0,
            style={"display": "none"},
        )
        self.open_input = Input(self._bridge_id, "n_clicks")

        # Register the clientside injector. It listens on the chart's
        # primary store (the chart re-renders whenever this store
        # updates), finds the modebar, and appends our button.
        # `allow_duplicate=True` because a single chart store can have
        # many DyModebarButton injectors (one per button).
        dash.clientside_callback(
            self._build_injector_js(),
            Output(self._bridge_id, "data-injected"),
            Input(graph_id, "data"),
            prevent_initial_call=False,
        )

    def _build_injector_js(self) -> str:
        """Build the clientside callback JS that injects the button.

        The function fires when the chart's primary store updates. At
        that moment the chart's render callback has fired but may not
        have *finished* rendering — the ``.dy-modebar`` div might not
        exist in the DOM yet.

        We handle this with a bounded retry loop using ``setTimeout``:
        attempt the injection immediately; if the modebar isn't there,
        try again 50 ms later, up to ~3 seconds total. This is the same
        shape as ``dash_capture._modebar.py``'s plotly handling, just
        much simpler because the dygraphs modebar — once created — is
        never rebuilt.

        Idempotency: the button carries a ``data-dybridge=<bridge_id>``
        attribute. If a button with that attribute already exists, we
        bail. This makes the retry loop safe even if both the
        ``_chart_data`` callback and a follow-up rAF settle the DOM at
        roughly the same time.
        """
        # Carefully escape values for JS string interpolation. None of
        # these are user-controlled in practice but we sanitize anyway
        # to keep the contract explicit.
        graph_id = self.graph_id.replace("\\", "\\\\").replace("'", "\\'")
        bridge_id = self._bridge_id.replace("\\", "\\\\").replace("'", "\\'")
        label = self.label.replace("\\", "\\\\").replace("'", "\\'")
        # Icon is HTML; injected via innerHTML.
        icon = self.icon.replace("\\", "\\\\").replace("`", "\\`")

        return f"""
            function(_chart_data) {{
                function attempt(attemptsLeft) {{
                    var modebar = document.querySelector(
                        '#{graph_id}-container .dy-modebar'
                    );
                    if (!modebar) {{
                        if (attemptsLeft > 0) {{
                            setTimeout(function() {{
                                attempt(attemptsLeft - 1);
                            }}, 50);
                        }}
                        return;
                    }}
                    // Idempotency: bail if our button is already present.
                    if (modebar.querySelector(
                        '[data-dybridge="{bridge_id}"]'
                    )) {{
                        return;
                    }}
                    var btn = document.createElement('button');
                    btn.title = '{label}';
                    btn.setAttribute('aria-label', '{label}');
                    btn.setAttribute('data-dybridge', '{bridge_id}');
                    btn.innerHTML = `{icon}`;
                    btn.onclick = function() {{
                        var bridge = document.getElementById('{bridge_id}');
                        if (bridge) bridge.click();
                    }};
                    modebar.appendChild(btn);
                }}
                // Up to ~3 seconds of retries (60 attempts * 50ms).
                attempt(60);
                return window.dash_clientside.no_update;
            }}
        """
