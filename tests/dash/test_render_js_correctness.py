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
    """The renderer must walk the option tree exactly once per render.

    The previous layout called ``processJsMarkers(opts)`` twice — once
    after parsing ``config.attrs`` and once again after merging
    ``optsOverride`` — which double-walked every base attr. The current
    layout merges first and walks the merged result exactly once. Lock
    this in so a future "let's process attrs early for safety" patch
    doesn't silently regress to two walks.
    """

    def test_processjsmarkers_called_once_on_opts(self) -> None:
        # Count call sites that operate on the merged ``opts`` object.
        # The function definition uses ``processJsMarkers(obj)`` and the
        # recursive descent uses ``processJsMarkers(val)``, so neither
        # matches this literal.
        assert ASSET.count("processJsMarkers(opts)") == 1, (
            "processJsMarkers(opts) must be called exactly once per render — "
            "the previous double-walk layout has regressed"
        )

    def test_processjsmarkers_call_follows_object_assign(self) -> None:
        """The single walk must come *after* the override merge.

        If it ran before ``Object.assign(opts, optsOverride)``, any
        marker strings inside the override would slip through unevaluated.
        """
        merge_idx = ASSET.find("Object.assign(opts, optsOverride)")
        walk_idx = ASSET.find("processJsMarkers(opts)")
        assert merge_idx != -1, "override merge call missing from renderer"
        assert walk_idx != -1, "processJsMarkers(opts) call missing from renderer"
        assert walk_idx > merge_idx, (
            "processJsMarkers(opts) must run after Object.assign(opts, optsOverride) "
            "or override markers will not be evaluated"
        )


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
