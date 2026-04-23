"""Shiny for Python integration — render a Dygraph in Shiny apps.

Uses ``session.send_custom_message()`` to push config from Python to JS,
and ``Shiny.addCustomMessageHandler()`` on the client to initialize dygraphs.

Rendering is delegated to the shared :mod:`dygraphs.assets.render_core`
module, which is the single source of truth for how a ``Dygraph`` config
becomes a rendered chart. The Shiny-specific layer here is intentionally
thin: it only wires Shiny's custom-message protocol into
``window.dygraphs.render(container, config)``.
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

# The shared framework-agnostic renderer — inlined into the UI once per
# page so ``window.dygraphs.render`` is available when Shiny messages
# arrive. IIFE-guarded, so repeated inlines (multiple charts in one
# layout) are safe no-ops after the first.
_RENDER_CORE_JS = (ASSETS_DIR / "render_core.js").read_text()


def dygraph_ui(
    element_id: str,
    *,
    height: str = "400px",
    width: str = "100%",
) -> Any:
    """Create the UI components for a dygraph chart.

    Returns a ``TagList`` containing:

    - CDN ``<link>`` and ``<script>`` for dygraphs
    - The shared ``render_core.js`` asset (idempotent; only the first
      inline registers ``window.dygraphs``)
    - A container ``<div>`` Shiny will target via custom message
    - A ``<script>`` registering the custom message handler for this
      specific ``element_id``, which dispatches into
      ``window.dygraphs.render(container, config)``

    Parameters
    ----------
    element_id : str
        Unique DOM id for the chart container.
    height, width : str
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
        window.dygraphs.render(el, config);
    }});
    """

    return ui.TagList(
        ui.head_content(
            ui.tags.link(rel="stylesheet", href=_DYGRAPH_CSS_CDN),
            ui.tags.script(src=_DYGRAPH_JS_CDN),
            ui.tags.script(_RENDER_CORE_JS),
        ),
        ui.div(id=element_id, style=f"width:{width}; height:{height};"),
        ui.tags.script(handler_js),
    )


async def render_dygraph(
    session: Any,
    element_id: str,
    dg: Dygraph | None,
) -> None:
    """Send dygraph config to the browser via Shiny custom message.

    Call this from a reactive effect or observer to render / update the
    chart. Passing ``dg=None`` clears the chart (matches the empty-
    placeholder semantics of :class:`dygraphs.dash.DygraphChart`
    constructed with ``figure=None``) — the clientside renderer
    early-returns on falsy config.

    Parameters
    ----------
    session : Shiny session
        Shiny session object.
    element_id : str
        DOM id matching the ``dygraph_ui()`` call.
    dg : Dygraph | None
        Configured ``Dygraph`` builder instance, or ``None`` to clear.
    """
    config = dg.to_js() if dg is not None else None
    await session.send_custom_message(f"dygraphs_{element_id}", config)
