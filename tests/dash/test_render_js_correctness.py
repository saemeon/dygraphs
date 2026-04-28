"""Static correctness checks for the Dash renderer JS asset.

These tests assert *properties* of ``src/dygraphs/assets/dash_render.js``
and the Python-side helpers that build the per-instance shim. They run
in milliseconds — no Chrome, no Dash server, no Selenium.

Each assertion pins one of the bugs we hit during the Dash refactor:

* DPR cropping in the multi-canvas merge (capture.py)
* IIFE-vs-statement parser collision in the dash-capture wizard strategy
* ``__JS__:`` marker slice off-by-one
* Modebar / wizard capture-source drift
* In-place ``updateOptions`` regression sneaking back into the renderer
* ``retain_date_window`` plumbing
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

# The shared framework-agnostic renderer. All the correctness properties
# pinned below (destroy+recreate, dateWindow normalisation, plotter eval
# order, interactionModel shim, group sync, processJsMarkers
# single-pass, etc.) live here — both Dash and Shiny inline this asset,
# so the assertions apply to both rendering paths simultaneously.
_ASSETS_DIR = Path(__file__).parent.parent.parent / "src" / "dygraphs" / "assets"
ASSET = (_ASSETS_DIR / "render_core.js").read_text()

# The Dash-specific shim (modebar, capture, reset buttons). Used only by
# the handful of tests asserting on Dash-only features.
DASH_SHIM = (_ASSETS_DIR / "dash_render.js").read_text()


def _skip_if_no_dash_capture() -> None:
    if importlib.util.find_spec("dash_capture") is None:
        pytest.skip("dash-capture not installed")


# ---------------------------------------------------------------------------
# Always-recreate (R/htmlwidgets update model)
# ---------------------------------------------------------------------------


class TestAlwaysRecreate:
    def test_destroy_called(self) -> None:
        """The renderer must call ``ex.destroy()`` on the previous instance."""
        assert "ex.destroy()" in ASSET

    def test_no_in_place_update_branch(self) -> None:
        """The old in-place updateOptions branch must not return.

        Catches a regression where someone reintroduces
        ``ex.updateOptions(Object.assign({file: rows}, opts))`` for
        perf reasons. The R model is one path: always destroy + create.
        """
        assert "Object.assign({file: rows}, opts)" not in ASSET
        assert "Object.assign({file:rows}, opts)" not in ASSET

    def test_new_dygraph_always_called(self) -> None:
        """The renderer always reaches ``new Dygraph(...)`` after the destroy."""
        assert "new Dygraph(" in ASSET

    def test_retain_date_window_branch_present(self) -> None:
        """``opts.retainDateWindow`` is honoured by reading the prior range.

        It lives under ``config.attrs`` Python-side, which becomes ``opts``
        once the renderer parses the payload.
        """
        assert "opts.retainDateWindow" in ASSET
        assert "xAxisRange()" in ASSET

    def test_retain_date_window_default_is_off(self) -> None:
        """The Python builder defaults retain_date_window to False (matches R)."""
        from dygraphs import Dygraph

        d = Dygraph([[1, 10], [2, 20]])
        assert d.to_dict()["attrs"].get("retainDateWindow") is False

    def test_retain_date_window_true_propagates_to_config(self) -> None:
        from dygraphs import Dygraph

        d = Dygraph([[1, 10], [2, 20]]).options(retain_date_window=True)
        assert d.to_dict()["attrs"]["retainDateWindow"] is True


# ---------------------------------------------------------------------------
# DPR-aware multi-canvas capture (the original cropping bug)
# ---------------------------------------------------------------------------


class TestMultiCanvasCaptureDpr:
    def test_uses_devicepixelratio(self) -> None:
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        assert "window.devicePixelRatio" in MULTI_CANVAS_CAPTURE_JS

    def test_output_canvas_sized_in_device_px(self) -> None:
        """The output canvas's pixel size must include ``* dpr`` for both axes."""
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        assert re.search(
            r"out\.width\s*=\s*Math\.round\(cssW\s*\*\s*dpr\)",
            MULTI_CANVAS_CAPTURE_JS,
        )
        assert re.search(
            r"out\.height\s*=\s*Math\.round\(cssH\s*\*\s*dpr\)",
            MULTI_CANVAS_CAPTURE_JS,
        )

    def test_uses_9_arg_drawimage(self) -> None:
        """drawImage must use the 9-arg form (source rect + dest rect).

        The 3-arg form ``drawImage(cv, x, y)`` paints the source canvas
        at its *natural* (device-px) size into a CSS-px destination,
        which is exactly the original DPR cropping bug. Catch any
        accidental revert by requiring the explicit 9-arg call.
        """
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        assert re.search(
            r"drawImage\(\s*cv\s*,\s*0\s*,\s*0\s*,\s*cv\.width\s*,\s*cv\.height",
            MULTI_CANVAS_CAPTURE_JS,
        )

    def test_context_scaled_by_dpr(self) -> None:
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        assert "ctx.scale(dpr, dpr)" in MULTI_CANVAS_CAPTURE_JS


# ---------------------------------------------------------------------------
# dygraph_strategy (dash-capture wizard) — IIFE vs raw statements
# ---------------------------------------------------------------------------


class TestDygraphStrategyShape:
    def test_capture_dispatches_to_shared_iife(self) -> None:
        """The strategy capture must dispatch to the shared async IIFE.

        We earlier hit a parser collision where the strategy was wrapped
        as ``(function (el, opts) { ... })`` and dash-capture concatenated
        it with the preprocess fragment, producing
        ``(preprocessFn)(captureFn)`` — calling the preprocess with the
        capture *function* as its ``el`` argument. Disaster.

        Now the capture is wrapped in ``try { ... } finally { ... }`` so
        the live-resize preprocess can be cleaned up safely; the
        dispatch must still ``await`` the shared async IIFE.
        """
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        strategy = dygraph_strategy()
        assert "await (async function" in strategy.capture, (
            "strategy.capture must await the shared async IIFE; "
            f"got: {strategy.capture[:120]!r}"
        )

    def test_capture_does_not_define_top_level_function_expression(self) -> None:
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        strategy = dygraph_strategy()
        assert not strategy.capture.lstrip().startswith("(async function"), (
            "capture is wrapped as an async function expression — IIFE bug"
        )
        assert not strategy.capture.lstrip().startswith("(function"), (
            "capture is wrapped as a function expression — IIFE bug"
        )

    def test_capture_has_finally_cleanup(self) -> None:
        """The capture must restore inline styles in a finally block.

        The live-resize preprocess sets ``el.style.width``/``height``/
        ``visibility`` and stashes the originals on ``el._dcap_saved``;
        the finally block restores them so the live chart isn't left
        in the resized state if html2canvas throws.
        """
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        capture = dygraph_strategy().capture
        assert "finally" in capture
        assert "_dcap_saved" in capture

    def test_preprocess_none_without_capture_dims(self) -> None:
        """No preprocess when the renderer doesn't declare capture_width/height."""
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        assert dygraph_strategy().preprocess is None
        assert dygraph_strategy(hide_range_selector=False).preprocess is None
        assert dygraph_strategy(_params={}).preprocess is None

    def test_preprocess_emitted_for_capture_width(self) -> None:
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        s = dygraph_strategy(_params={"capture_width": None})
        assert s.preprocess is not None
        assert "opts.width" in s.preprocess
        assert "opts.height" not in s.preprocess

    def test_preprocess_emitted_for_capture_height(self) -> None:
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        s = dygraph_strategy(_params={"capture_height": None})
        assert s.preprocess is not None
        assert "opts.height" in s.preprocess
        assert "opts.width" not in s.preprocess

    def test_preprocess_emitted_for_both_dims(self) -> None:
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        s = dygraph_strategy(_params={"capture_width": None, "capture_height": None})
        assert s.preprocess is not None
        assert "opts.width" in s.preprocess
        assert "opts.height" in s.preprocess
        assert "_dcap_saved" in s.preprocess
        assert "requestAnimationFrame" in s.preprocess

    def test_preprocess_settle_frames_default(self) -> None:
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        s = dygraph_strategy(_params={"capture_width": None})
        assert "i < 2" in s.preprocess

    def test_preprocess_settle_frames_custom(self) -> None:
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        s = dygraph_strategy(settle_frames=4, _params={"capture_width": None})
        assert "i < 4" in s.preprocess

    def test_preprocess_does_not_set_visibility_hidden(self) -> None:
        # Regression: visibility:hidden cascades to descendants and
        # html2canvas (used by the IIFE for the HTML overlay pass) skips
        # hidden elements — that wiped chart title, axis labels, tick
        # labels, and legend from the captured PNG. The brief flicker of
        # the resize is the price of correct output.
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        s = dygraph_strategy(_params={"capture_width": None})
        assert "visibility" not in s.preprocess


# ---------------------------------------------------------------------------
# HTML overlay capture (title / axis labels / tick labels / legend)
# ---------------------------------------------------------------------------


class TestHtmlOverlayCapture:
    """Pin the html2canvas overlay pass that captures HTML-rendered chart
    chrome (title, x/y axis labels, tick labels, legend, annotations).
    Without this pass the strategy only blits ``<canvas>`` elements and
    drops everything that dygraphs renders as positioned ``<div>``s.
    """

    def test_iife_is_async(self) -> None:
        """The shared IIFE must be async to await html2canvas."""
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        assert MULTI_CANVAS_CAPTURE_JS.lstrip().startswith("(async function"), (
            "MULTI_CANVAS_CAPTURE_JS must be an async IIFE so it can await "
            "html2canvas; got: " + MULTI_CANVAS_CAPTURE_JS[:60]
        )

    def test_iife_calls_html2canvas(self) -> None:
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        assert "window.html2canvas" in MULTI_CANVAS_CAPTURE_JS, (
            "overlay pass must invoke window.html2canvas"
        )
        assert "await window.html2canvas(el" in MULTI_CANVAS_CAPTURE_JS, (
            "html2canvas call must be awaited so the overlay completes before toDataURL"
        )

    def test_iife_skips_canvas_elements_in_overlay_pass(self) -> None:
        """``ignoreElements`` must skip ``<canvas>`` so html2canvas doesn't
        re-rasterise plot canvases at lower fidelity over our sharp blits.
        """
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        assert "ignoreElements" in MULTI_CANVAS_CAPTURE_JS
        assert re.search(
            r"n\.tagName\s*===\s*['\"]CANVAS['\"]",
            MULTI_CANVAS_CAPTURE_JS,
        ), "ignoreElements filter must compare tagName === 'CANVAS'"

    def test_iife_overlay_uses_dpr_scale(self) -> None:
        """The overlay must rasterise at the same DPR as the canvas
        composite — otherwise label text would either be blurry (scale
        too low) or oversized when blitted (scale mismatch).
        """
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        assert re.search(r"scale:\s*dpr", MULTI_CANVAS_CAPTURE_JS), (
            "html2canvas must be called with scale: dpr to match the output canvas DPR"
        )

    def test_iife_overlay_drawn_in_device_pixels(self) -> None:
        """Before drawImage'ing the overlay, the context must be reset to
        identity transform — the overlay canvas is already at device
        pixels, but our context is dpr-scaled.
        """
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

        # The overlay drawImage block must appear after a setTransform
        # to identity. Search the substring around the overlay drawImage.
        idx = MULTI_CANVAS_CAPTURE_JS.find("ctx.drawImage(overlay")
        assert idx > 0, "overlay drawImage call missing"
        prelude = MULTI_CANVAS_CAPTURE_JS[max(0, idx - 200) : idx]
        assert "setTransform(1, 0, 0, 1, 0, 0)" in prelude, (
            "overlay drawImage must be preceded by setTransform identity "
            "so the overlay is painted at device pixels"
        )

    def test_strategy_queues_html2canvas(self) -> None:
        """``dygraph_strategy()`` must queue the vendored html2canvas asset
        so Dash drains it into the served HTML's inline-script slot.
        """
        _skip_if_no_dash_capture()
        from dash._callback import GLOBAL_INLINE_SCRIPTS

        from dygraphs.dash.capture import dygraph_strategy

        before = list(GLOBAL_INLINE_SCRIPTS)
        try:
            dygraph_strategy()
            joined = "\n".join(GLOBAL_INLINE_SCRIPTS)
            assert "__dcap_html2canvas__" in joined, (
                "html2canvas must be queued into Dash's inline-script slot "
                "by every dygraph_strategy() construction"
            )
        finally:
            GLOBAL_INLINE_SCRIPTS[:] = before

    def test_modebar_handler_awaits_async_capture(self) -> None:
        """The modebar ``__dyCap_<id>`` handler must be async and await
        the capture function — the IIFE now returns a Promise.
        """
        assert re.search(
            r"__dyCap_'\s*\+\s*jsId\s*\]\s*=\s*async function",
            DASH_SHIM,
        ), "modebar capture handler must be declared 'async function'"
        assert "await captureFn(" in DASH_SHIM, (
            "modebar handler must await the (now async) capture IIFE"
        )


# ---------------------------------------------------------------------------
# __JS__: marker slice (the off-by-one we hit)
# ---------------------------------------------------------------------------


class TestJsMarkerSlice:
    def test_uses_correct_slice_in_dash_render(self) -> None:
        """``__JS__:<code>:__JS__`` is 7 chars on each end → ``slice(7, -7)``."""
        assert "slice(7, -7)" in ASSET
        assert "slice(7, -6)" not in ASSET, "off-by-one slice has reappeared"

    def test_shiny_delegates_to_shared_core(self) -> None:
        """Shiny must go through ``window.dygraphs.render`` (the shared
        core) rather than re-implementing the marker slice / rendering
        pipeline inline. This is how we prevent the two adapters from
        drifting apart — fixes to the core apply to both."""
        from pathlib import Path

        shiny = (
            Path(__file__).parent.parent.parent
            / "src"
            / "dygraphs"
            / "shiny"
            / "component.py"
        ).read_text()
        assert "window.dygraphs.render(" in shiny
        # And the old re-implemented slice(7, -7) / processJS function
        # should no longer live in the Shiny source — the core handles it.
        assert "slice(7, -7)" not in shiny, (
            "Shiny adapter should delegate to window.dygraphs.render "
            "(shared core), not re-implement __JS__ marker resolution"
        )


# ---------------------------------------------------------------------------
# processJsMarkers is called exactly once per render (single-pass invariant)
# ---------------------------------------------------------------------------


class TestJsMarkerSinglePass:
    """The renderer walks the option tree exactly once per render.

    The marker protocol (``__JS__:...``) is evaluated in a single pass
    over the ``opts`` object. Lock this in so a future accidental
    double-walk is caught.
    """

    def test_processjsmarkers_called_once_on_opts(self) -> None:
        # Count call sites that operate on the ``opts`` object. The
        # function definition uses ``processJsMarkers(obj)`` and the
        # recursive descent uses ``processJsMarkers(val)``, so neither
        # matches this literal.
        assert ASSET.count("processJsMarkers(opts)") == 1, (
            "processJsMarkers(opts) must be called exactly once per render"
        )


# ---------------------------------------------------------------------------
# No hidden sink — callback writes back to the data store itself
# ---------------------------------------------------------------------------


_COMPONENT_PY = (
    Path(__file__).parent.parent.parent / "src" / "dygraphs" / "dash" / "component.py"
).read_text()


class TestNoHiddenGraphSink:
    """Lock in the always-no-update + allow_duplicate dummy-output pattern.

    The clientside callback writes back to the data ``dcc.Store``
    itself with ``allow_duplicate=True`` and the JS returns
    ``window.dash_clientside.no_update`` so the store isn't actually
    mutated (no feedback loop). Requires ``dash>=2.9.0`` for
    ``allow_duplicate`` and ``prevent_initial_call='initial_duplicate'``.
    """

    def test_shim_returns_no_update(self) -> None:
        """The per-instance shim must end with ``return no_update``."""
        from dygraphs.dash.component import _build_render_js

        js = _build_render_js("g", "g-container", "g-chart", 320, modebar=True)
        assert "window.dash_clientside.no_update" in js
        # Old empty-figure return must not reappear.
        assert "{data: [], layout: {}}" not in js
        assert "{data:[],layout:{}}" not in js

    def test_component_uses_allow_duplicate(self) -> None:
        """The DygraphChart callback wires allow_duplicate=True."""
        assert "allow_duplicate=True" in _COMPONENT_PY

    def test_component_uses_initial_duplicate_prevent(self) -> None:
        """prevent_initial_call must be 'initial_duplicate' (Dash 2.9 feature)."""
        assert 'prevent_initial_call="initial_duplicate"' in _COMPONENT_PY

    def test_component_no_hidden_graph_id_var(self) -> None:
        """The ``hidden_graph_id`` local must be gone — symptom of the old sink."""
        assert "hidden_graph_id" not in _COMPONENT_PY
        assert "hidden-graph" not in _COMPONENT_PY

    def test_component_does_not_instantiate_dcc_graph(self) -> None:
        """The dcc.Graph hidden sink instance must be gone from layouts."""
        assert "dcc.Graph(" not in _COMPONENT_PY

    def test_pyproject_pins_dash_2_9(self) -> None:
        """``allow_duplicate`` requires dash>=2.9.0 — pin it in pyproject."""
        pyproject = (Path(__file__).parent.parent.parent / "pyproject.toml").read_text()
        # The dash extra and the test group both must require >=2.9.0.
        # An older >=2.0.0 pin would let the runtime crash on the
        # allow_duplicate keyword for users on the minimum version.
        assert "dash>=2.0.0" not in pyproject, (
            "dash>=2.0.0 is too old for allow_duplicate=True; must be >=2.9.0"
        )
        assert "dash>=2.9.0" in pyproject


# ---------------------------------------------------------------------------
# Group sync wiring (locks in the JS invariants for cross-chart zoom/highlight)
# ---------------------------------------------------------------------------


class TestGroupSyncWiring:
    """The group-sync JS path is the most complex piece of cross-chart
    state we have: a global ``window.__dyGroups`` registry, a debounced
    zoom broadcaster, and a highlight relay. End-to-end coverage needs
    Selenium, but the individual pieces are stable string patterns in
    the renderer source — assertable in microseconds. One check per
    invariant; refactors of the group-sync code must preserve every
    one of them or delete the corresponding assertion with a reason.
    """

    def test_global_group_registry_on_window(self) -> None:
        """The registry is attached to ``window`` via ``global.__dyGroups``
        so every chart on the page can see it across callback invocations."""
        assert "global.__dyGroups" in ASSET
        assert "ensureGroupRegistry" in ASSET

    def test_group_registry_entry_keyed_by_graph_id(self) -> None:
        """New charts push ``{id, el, instance}`` into the group's list.

        ``id`` is the graphId the Python side generates per chart; the
        broadcast loop uses it to skip the source chart so it doesn't
        echo its own zoom event. Locks in the shape of the entry.
        """
        assert "groups[config.group].push" in ASSET
        assert "id: graphId" in ASSET  # local var in render_core.js
        assert "instance: dygraph" in ASSET

    def test_group_registry_dedupes_stale_entries_on_re_render(self) -> None:
        """Before re-registering on a data update, any stale entry for the
        same graphId must be filtered out — otherwise group sync would
        accumulate dead peer references across destroy+recreate cycles."""
        assert "groups[config.group].filter" in ASSET
        assert "e.id !== graphId" in ASSET

    def test_zoom_broadcast_loop_skips_source_chart(self) -> None:
        """The broadcast loop must early-return when the peer is the
        source of the zoom event. Without this, each drag event produces
        an infinite feedback loop."""
        assert "groups[group].forEach" in ASSET
        assert "peer.id === graphId" in ASSET

    def test_zoom_broadcast_uses_update_options_date_window(self) -> None:
        """Peer charts are notified via
        ``peer.instance.updateOptions({dateWindow: dw})`` — the dygraphs
        JS API for programmatic zoom. A refactor that accidentally
        swaps this for ``peer.instance.resetZoom()`` or similar would
        silently break cross-chart sync."""
        assert "peer.instance.updateOptions({dateWindow: dw})" in ASSET

    def test_zoom_broadcast_suppress_flag_breaks_feedback_loop(self) -> None:
        """Before broadcasting to a peer, the peer's ``_suppressZoom``
        flag is set so its own ``zoomCallback`` short-circuits on the
        resulting dateWindow change. This is the feedback-loop breaker —
        losing it produces an infinite zoom cascade across the group."""
        assert "peer.el._suppressZoom = true" in ASSET
        assert "container._suppressZoom" in ASSET

    def test_zoom_broadcast_is_debounced(self) -> None:
        """``setTimeout`` + ``clearTimeout`` on ``_zoomDebounce`` throttles
        the broadcast to ~30ms. Without debouncing, drag events fire
        per-pixel and saturate peers' update queues."""
        assert "_zoomDebounce" in ASSET
        assert "clearTimeout(container._zoomDebounce)" in ASSET

    def test_highlight_sync_uses_set_and_clear_selection(self) -> None:
        """Highlight (hover row) sync relays through
        ``peer.instance.setSelection(row)`` on highlight and
        ``peer.instance.clearSelection()`` on unhighlight — the dygraphs
        JS API for programmatic hover-row control."""
        assert "peer.instance.setSelection(row)" in ASSET
        assert "peer.instance.clearSelection()" in ASSET

    def test_highlight_sync_respects_suppress_flag(self) -> None:
        """Mirrors the zoom-sync suppress flag: each peer sets
        ``_suppressHighlight`` around the relay so the peer's own
        callback doesn't echo back."""
        assert "peer.el._suppressHighlight" in ASSET
        assert "container._suppressHighlight" in ASSET

    def test_attach_sync_early_returns_on_missing_group(self) -> None:
        """``attachHighlightSync`` early-returns when ``config.group``
        is falsy — charts without a group name must not pay the
        relay cost."""
        assert "if (!group) return;" in ASSET


# ---------------------------------------------------------------------------
# Asset / shim integration
# ---------------------------------------------------------------------------


class TestRendererAssetIntegration:
    def test_core_asset_is_idempotent_iife(self) -> None:
        """The shared core asset wraps in an IIFE that no-ops on second
        execution (multiple charts and both adapters inline it)."""
        body = re.sub(r"^/\*.*?\*/\s*", "", ASSET, count=1, flags=re.DOTALL)
        assert body.lstrip().startswith(
            "(function (global)"
        ) or body.lstrip().startswith("(function(global)")
        assert "if (global.dygraphs) return;" in ASSET

    def test_core_asset_exposes_render_entrypoint(self) -> None:
        assert "global.dygraphs = {" in ASSET
        assert "render: render" in ASSET

    def test_dash_shim_is_idempotent_iife(self) -> None:
        """The Dash shim also guards via IIFE so multiple per-chart
        inlines only register ``window.dygraphsDash`` once."""
        body = re.sub(r"^/\*.*?\*/\s*", "", DASH_SHIM, count=1, flags=re.DOTALL)
        assert body.lstrip().startswith(
            "(function (global)"
        ) or body.lstrip().startswith("(function(global)")
        assert "if (global.dygraphsDash) return;" in DASH_SHIM

    def test_dash_shim_exposes_render_entrypoint(self) -> None:
        assert "global.dygraphsDash = {" in DASH_SHIM
        assert "render: render" in DASH_SHIM

    def test_dash_shim_dispatches_to_shared_core(self) -> None:
        """The Dash shim must go through ``window.dygraphs.render`` —
        that's the whole point of the shared-core extraction. Lock it
        in so a future refactor doesn't silently re-inline the
        rendering logic back into ``dash_render.js``."""
        assert "global.dygraphs.render(" in DASH_SHIM

    def test_shim_dispatches_to_window_dygraphsdash(self) -> None:
        from dygraphs.dash.component import _build_render_js

        js = _build_render_js("g", "g-container", "g-chart", 320, modebar=True)
        assert "window.dygraphsDash.render(" in js

    def test_shim_includes_setup_payload(self) -> None:
        from dygraphs.dash.component import _build_render_js

        js = _build_render_js("g", "g-container", "g-chart", 320, modebar=True)
        # All the per-instance fields the asset reads
        for key in (
            "containerId",
            "chartDivId",
            "graphId",
            "height",
            "modebar",
            "cdnCssUrl",
            "cdnJsUrl",
            "modebarCss",
            "modebarHtml",
            "captureJs",
        ):
            assert f'"{key}":' in js, f"shim setup missing {key!r}"

    def test_shim_includes_capture_js_source(self) -> None:
        """The modebar receives the same MULTI_CANVAS_CAPTURE_JS source.

        After the asset extraction, the source is JSON-encoded into the
        ``setup.captureJs`` field, so it appears in the shim as an
        escaped substring rather than verbatim.
        """
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS
        from dygraphs.dash.component import _build_render_js

        js = _build_render_js("g", "g-container", "g-chart", 320, modebar=True)
        encoded = json.dumps(MULTI_CANVAS_CAPTURE_JS)[1:-1]  # strip outer quotes
        assert encoded in js


# ---------------------------------------------------------------------------
# dateWindow normalisation: Python emits ISO strings, Dygraph wants ms
# ---------------------------------------------------------------------------


class TestDateWindowNormalisation:
    """Lock in the client-side ISO-string → ms conversion for ``opts.dateWindow``.

    The Python builder (:meth:`Dygraph.range_selector`) serialises the
    ``date_window`` kwarg as ISO-8601 strings so the dict round-trips
    cleanly through JSON. The Dygraph constructor, though, expects
    ``dateWindow`` as ``[number_ms, number_ms]`` or ``[Date, Date]``
    — handed ISO strings it silently coerces to ``NaN`` and the
    initial zoom window is ignored. The renderer converts here, before
    ``new Dygraph(...)``.
    """

    def test_normalisation_block_present(self) -> None:
        """The ``opts.dateWindow`` conversion exists in the renderer."""
        assert "opts.dateWindow && opts.dateWindow.length === 2" in ASSET
        assert "opts.dateWindow = opts.dateWindow.map" in ASSET

    def test_iso_string_mapped_via_new_date_get_time(self) -> None:
        """String entries become ``new Date(v).getTime()`` (milliseconds)."""
        # Single-line check: the conversion body mentions both the
        # string type guard and the new Date(...).getTime() call.
        pattern = re.compile(
            r"opts\.dateWindow\s*=\s*opts\.dateWindow\.map\("
            r".*?typeof\s+v\s*===\s*'string'\s*\?"
            r"\s*new\s+Date\(v\)\.getTime\(\)",
            re.DOTALL,
        )
        assert pattern.search(ASSET), (
            "opts.dateWindow normalisation must convert ISO strings via "
            "new Date(v).getTime()"
        )

    def test_numeric_date_window_passes_through(self) -> None:
        """Numbers/Dates survive the map unchanged (``: v`` fallback)."""
        # The ternary's false-branch returns v as-is so pre-computed
        # timestamps (or Date objects) aren't re-wrapped.
        pattern = re.compile(
            r"typeof\s+v\s*===\s*'string'\s*\?"
            r"\s*new\s+Date\(v\)\.getTime\(\)\s*:\s*v",
            re.DOTALL,
        )
        assert pattern.search(ASSET), (
            "non-string dateWindow entries must pass through unchanged"
        )

    def test_normalisation_runs_before_dygraph_instantiation(self) -> None:
        """The conversion must happen before ``new Dygraph(...)``.

        Normalising AFTER construction is too late — Dygraph has already
        parsed the ISO strings into NaN.
        """
        normalise_idx = ASSET.find("opts.dateWindow = opts.dateWindow.map")
        construct_idx = ASSET.find("new Dygraph(")
        assert normalise_idx != -1, "dateWindow normalisation missing"
        assert construct_idx != -1, "new Dygraph(...) call missing"
        assert normalise_idx < construct_idx, (
            "dateWindow normalisation must run before new Dygraph(...) — "
            "otherwise the ISO strings have already become NaN"
        )


# ---------------------------------------------------------------------------
# interactionModel compat shim: Dygraph.Interaction.defaultModel fallback
# ---------------------------------------------------------------------------


class TestInteractionModelCompatShim:
    """Lock in the ``Dygraph.Interaction.defaultModel`` fallback.

    ``.range_selector(keep_mouse_zoom=True)`` (the default) emits
    ``JS("Dygraph.Interaction.defaultModel")`` in the config.
    ``processJsMarkers`` ``eval``\\ s the marker at render time —
    but some Dygraph builds expose it only as
    ``Dygraph.defaultInteractionModel`` at the top level, leaving
    ``Dygraph.Interaction.defaultModel`` undefined. The shim
    populates the former from the latter when missing, so the eval
    resolves to a real interaction model. Same shim as the
    ``to_html`` path.
    """

    def test_shim_present(self) -> None:
        """The fallback assignment exists in the renderer."""
        # Single-line pattern: when Interaction.defaultModel is falsy
        # AND defaultInteractionModel exists, copy across.
        assert "Dygraph.Interaction.defaultModel" in ASSET
        assert "Dygraph.defaultInteractionModel" in ASSET
        assert (
            "Dygraph.Interaction.defaultModel = Dygraph.defaultInteractionModel"
            in ASSET
        )

    def test_shim_guarded_by_dygraph_presence(self) -> None:
        """The shim must not run before dygraphs.js has loaded.

        Running ``Dygraph.Interaction.defaultModel = ...`` before the
        library loads would crash with ``ReferenceError: Dygraph is
        not defined``. Guard with a ``typeof Dygraph !== 'undefined'``
        check.
        """
        pattern = re.compile(
            r"typeof\s+Dygraph\s*!==\s*'undefined'\s*&&\s*Dygraph\.Interaction",
            re.DOTALL,
        )
        assert pattern.search(ASSET), (
            "interactionModel shim must be guarded by a typeof check"
        )

    def test_shim_runs_before_dygraph_instantiation(self) -> None:
        """The shim must run before ``new Dygraph(...)``.

        If it ran afterwards, the first render's ``processJsMarkers``
        eval of ``Dygraph.Interaction.defaultModel`` would still see
        ``undefined``.
        """
        shim_idx = ASSET.find(
            "Dygraph.Interaction.defaultModel = Dygraph.defaultInteractionModel"
        )
        construct_idx = ASSET.find("new Dygraph(")
        assert shim_idx != -1, "compat shim missing"
        assert construct_idx != -1, "new Dygraph(...) call missing"
        assert shim_idx < construct_idx, (
            "interactionModel shim must run before new Dygraph(...) — "
            "otherwise the first render hands an undefined model to Dygraph"
        )

    def test_shim_runs_before_processjsmarkers(self) -> None:
        """The shim must run before ``processJsMarkers(opts)``.

        ``processJsMarkers`` is what actually evaluates the
        ``__JS__:Dygraph.Interaction.defaultModel:__JS__`` marker. If
        the shim runs after, the marker resolves to ``undefined``.
        """
        shim_idx = ASSET.find(
            "Dygraph.Interaction.defaultModel = Dygraph.defaultInteractionModel"
        )
        markers_idx = ASSET.find("processJsMarkers(opts)")
        assert shim_idx != -1
        assert markers_idx != -1
        assert shim_idx < markers_idx, (
            "interactionModel shim must run before processJsMarkers(opts) "
            "so the __JS__ marker eval resolves to a defined model"
        )


# ---------------------------------------------------------------------------
# extraJs eval order: must precede processJsMarkers so Dygraph.Plotters.X
# and Dygraph.DataHandlers.X are defined when the markers are evaluated.
# ---------------------------------------------------------------------------


class TestExtraJsEvalOrder:
    """Lock in ``evalExtraJs(config)`` running before ``processJsMarkers(opts)``.

    ``.bar_chart()``, ``.stacked_bar_chart()``, ``.multi_column()``,
    ``.candlestick()`` each emit two things into the config: a
    ``plotter`` attr set to a ``JS("Dygraph.Plotters.BarChart")``
    marker, and an ``extraJs`` entry whose IIFE assigns
    ``Dygraph.Plotters.BarChart = barChartPlotter``. The namespace
    lookup only resolves AFTER the IIFE runs — so ``evalExtraJs``
    must happen before ``processJsMarkers`` evaluates the marker.
    Otherwise the marker resolves to ``undefined`` and Dygraph
    silently falls back to the default line plotter.
    """

    def test_evaljs_runs_before_processjsmarkers(self) -> None:
        evaljs_idx = ASSET.find("evalExtraJs(config)")
        markers_idx = ASSET.find("processJsMarkers(opts)")
        assert evaljs_idx != -1, "evalExtraJs(config) call missing"
        assert markers_idx != -1, "processJsMarkers(opts) call missing"
        assert evaljs_idx < markers_idx, (
            "evalExtraJs(config) must run before processJsMarkers(opts) — "
            "otherwise JS('Dygraph.Plotters.X') markers resolve to undefined"
        )

    def test_plotter_js_assigns_namespace(self) -> None:
        """Each plotter JS assigns ``Dygraph.Plotters.Name = function``.

        If a plotter JS were to define a bare global (e.g.
        ``function BarChart(e) { ... }``) without the namespace
        assignment, our ``JS("Dygraph.Plotters.BarChart")`` marker
        would still resolve to ``undefined``. This test reads each
        bundled plotter file and verifies the namespace assignment.
        """
        plotters_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "dygraphs"
            / "assets"
            / "plotters"
        )
        # The four chart-level plotters referenced by JS(...) markers
        # in dygraph.py (.bar_chart(), .stacked_bar_chart(),
        # .multi_column(), .candlestick()). Series-level plotters
        # (.bar_series(), etc.) use a different mechanism — they
        # inline the JS source as the plotter value, no namespace
        # assignment needed.
        expected = {
            "barchart.js": "Dygraph.Plotters.BarChart",
            "stackedbarchart.js": "Dygraph.Plotters.StackedBarChart",
            "multicolumn.js": "Dygraph.Plotters.MultiColumn",
            "candlestick.js": "Dygraph.Plotters.CandlestickPlotter",
        }
        for fname, namespace in expected.items():
            src = (plotters_dir / fname).read_text()
            assert f"{namespace} =" in src, (
                f"{fname} must assign `{namespace} = ...` so the "
                f"JS('{namespace}') marker resolves. Otherwise the "
                f"chart silently falls back to the default line plotter."
            )
