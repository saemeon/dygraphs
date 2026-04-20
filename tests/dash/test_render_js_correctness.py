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

ASSET = (
    Path(__file__).parent.parent.parent
    / "src"
    / "dygraphs"
    / "assets"
    / "dash_render.js"
).read_text()


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
    def test_capture_starts_with_return_statement(self) -> None:
        """The strategy capture must be raw statements, not an IIFE.

        We earlier hit a parser collision where the strategy was wrapped
        as ``(function (el, opts) { ... })`` and dash-capture concatenated
        it with the preprocess fragment, producing
        ``(preprocessFn)(captureFn)`` — calling the preprocess with the
        capture *function* as its ``el`` argument. Disaster.

        Raw statements must start with the dispatch call.
        """
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        strategy = dygraph_strategy()
        assert strategy.capture.lstrip().startswith("return "), (
            f"strategy.capture must start with 'return', got: {strategy.capture[:80]!r}"
        )

    def test_capture_does_not_define_async_function_expression(self) -> None:
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        strategy = dygraph_strategy()
        assert not strategy.capture.lstrip().startswith("(async function"), (
            "capture is wrapped as an async function expression — IIFE bug"
        )
        assert not strategy.capture.lstrip().startswith("(function"), (
            "capture is wrapped as a function expression — IIFE bug"
        )

    def test_preprocess_is_none(self) -> None:
        """All hide/restore logic lives inside the shared IIFE in the JS."""
        _skip_if_no_dash_capture()
        from dygraphs.dash.capture import dygraph_strategy

        assert dygraph_strategy().preprocess is None
        assert dygraph_strategy(hide_range_selector=False).preprocess is None


# ---------------------------------------------------------------------------
# __JS__: marker slice (the off-by-one we hit)
# ---------------------------------------------------------------------------


class TestJsMarkerSlice:
    def test_uses_correct_slice_in_dash_render(self) -> None:
        """``__JS__:<code>:__JS__`` is 7 chars on each end → ``slice(7, -7)``."""
        assert "slice(7, -7)" in ASSET
        assert "slice(7, -6)" not in ASSET, "off-by-one slice has reappeared"

    def test_uses_correct_slice_in_shiny_component(self) -> None:
        from pathlib import Path

        shiny = (
            Path(__file__).parent.parent.parent
            / "src"
            / "dygraphs"
            / "shiny"
            / "component.py"
        ).read_text()
        assert "slice(7, -7)" in shiny
        assert "slice(7, -6)" not in shiny


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
        assert "id: setup.graphId" in ASSET
        assert "instance: dygraph" in ASSET

    def test_group_registry_dedupes_stale_entries_on_re_render(self) -> None:
        """Before re-registering on a data update, any stale entry for the
        same graphId must be filtered out — otherwise group sync would
        accumulate dead peer references across destroy+recreate cycles."""
        assert "groups[config.group].filter" in ASSET
        assert "e.id !== setup.graphId" in ASSET

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
    def test_asset_is_idempotent_iife(self) -> None:
        """The asset wraps in an IIFE that no-ops on second execution."""
        # The file starts with a /* ... */ docstring; strip it before
        # checking the IIFE shape.
        body = re.sub(r"^/\*.*?\*/\s*", "", ASSET, count=1, flags=re.DOTALL)
        assert body.lstrip().startswith(
            "(function (global)"
        ) or body.lstrip().startswith("(function(global)")
        assert "if (global.dygraphsDash) return;" in ASSET

    def test_asset_exposes_render_entrypoint(self) -> None:
        assert "global.dygraphsDash = {" in ASSET
        assert "render: render" in ASSET

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
