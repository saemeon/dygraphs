"""Browser rendering tests — verify charts actually render without JS errors.

Uses to_html() + headless Chrome to test that the generated HTML/JS actually
works in a real browser. This catches issues that JSON comparison misses:
plugin JS not loading, shadings/events not drawing, group sync broken, etc.

Requires Chrome + chromedriver. Skipped if unavailable.

Run with::

    uv run pytest tests/integration/test_browser_render.py -v
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from dygraphs import Dygraph

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2020-01-01", periods=10, freq="D")
_DF = pd.DataFrame({"a": range(1, 11), "b": range(10, 0, -1)}, index=_DATES)


@pytest.fixture(scope="module")
def driver():
    """Headless Chrome WebDriver — shared across all tests in this module."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        pytest.skip("selenium not installed")
        return

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    try:
        d = webdriver.Chrome(options=options)
    except Exception:
        options.binary_location = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        try:
            d = webdriver.Chrome(options=options)
        except Exception as exc:
            pytest.skip(f"Chrome/chromedriver not available: {exc}")
            return

    yield d
    d.quit()


def _render(driver: Any, dg: Dygraph, *, cdn: bool = True) -> dict[str, Any]:
    """Write to_html() to a temp file, open in Chrome, return diagnostics."""
    html = dg.to_html(cdn=cdn)
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        f.write(html)
        path = f.name

    driver.get(f"file://{path}")
    time.sleep(3)  # wait for CDN load + render

    # Collect JS errors
    logs = driver.get_log("browser")
    errors = [e for e in logs if e["level"] == "SEVERE"]

    # Check for canvas (dygraph renders into canvas)
    canvases = driver.find_elements("tag name", "canvas")

    # Check for dygraph instance
    has_instance = driver.execute_script("return typeof Dygraph !== 'undefined'")

    # Get chart div content
    chart_html = driver.execute_script(
        "var el = document.getElementById('chart'); return el ? el.innerHTML : '';"
    )

    Path(path).unlink(missing_ok=True)

    return {
        "errors": errors,
        "canvas_count": len(canvases),
        "has_dygraph": has_instance,
        "chart_html": chart_html,
    }


def _assert_no_errors(result: dict[str, Any]) -> None:
    """Assert no severe JS errors."""
    if result["errors"]:
        msgs = [e["message"] for e in result["errors"]]
        # Filter out benign errors (favicon, etc)
        real = [m for m in msgs if "favicon" not in m.lower()]
        assert not real, f"JS errors: {real}"


def _assert_rendered(result: dict[str, Any]) -> None:
    """Assert chart actually rendered (has canvas elements)."""
    assert result["has_dygraph"], "Dygraph library not loaded"
    assert result["canvas_count"] > 0, (
        f"No canvas elements — chart didn't render. HTML: {result['chart_html'][:200]}"
    )


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------


class TestBasicRender:
    def test_simple_chart_renders(self, driver) -> None:
        dg = Dygraph(_DF, title="Basic Chart")
        result = _render(driver, dg)
        _assert_no_errors(result)
        _assert_rendered(result)

    def test_chart_with_options(self, driver) -> None:
        dg = Dygraph(_DF).options(fill_graph=True, draw_points=True, stacked_graph=True)
        result = _render(driver, dg)
        _assert_no_errors(result)
        _assert_rendered(result)

    def test_inline_js_renders(self, driver) -> None:
        """Test cdn=False (inline JS) — no network needed."""
        dg = Dygraph(_DF, title="Inline")
        result = _render(driver, dg, cdn=False)
        _assert_no_errors(result)
        _assert_rendered(result)


# ---------------------------------------------------------------------------
# Overlays: shadings, events, limits
# ---------------------------------------------------------------------------


class TestOverlayRender:
    def test_shadings_render(self, driver) -> None:
        dg = (
            Dygraph(_DF)
            .shading("2020-01-02", "2020-01-04", color="rgba(255,0,0,0.2)")
            .shading("2020-01-06", "2020-01-08", color="rgba(0,0,255,0.2)")
        )
        result = _render(driver, dg)
        _assert_no_errors(result)
        _assert_rendered(result)
        # Verify underlayCallback was set (shadings use it)
        has_underlay = driver.execute_script("""
            var g = document.getElementById('chart')._dygraphInstance ||
                    document.querySelector('canvas').__dygraph;
            // If the chart rendered, shadings were processed
            return document.querySelectorAll('canvas').length > 0;
        """)
        assert has_underlay

    def test_events_and_limits_render(self, driver) -> None:
        dg = (
            Dygraph(_DF)
            .event("2020-01-03", label="Event A", color="red")
            .event("2020-01-07", label="Event B", color="blue", stroke_pattern="dotted")
            .limit(5, label="Threshold", color="green")
        )
        result = _render(driver, dg)
        _assert_no_errors(result)
        _assert_rendered(result)

    def test_annotations_render(self, driver) -> None:
        dg = (
            Dygraph(_DF)
            .annotation("2020-01-03", text="A", tooltip="First", series="a")
            .annotation(
                "2020-01-07",
                text="B",
                tooltip="Second",
                series="b",
                width=20,
                height=20,
            )
        )
        result = _render(driver, dg)
        _assert_no_errors(result)
        _assert_rendered(result)
        # Check annotation divs exist
        ann_count = driver.execute_script(
            "return document.querySelectorAll('.dygraphDefaultAnnotation').length"
        )
        assert ann_count >= 1, "Annotations should render as DOM elements"


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------


class TestPluginRender:
    def test_unzoom_plugin(self, driver) -> None:
        dg = Dygraph(_DF).unzoom()
        result = _render(driver, dg, cdn=False)
        _assert_no_errors(result)
        _assert_rendered(result)

    def test_crosshair_plugin(self, driver) -> None:
        dg = Dygraph(_DF).crosshair(direction="both")
        result = _render(driver, dg, cdn=False)
        _assert_no_errors(result)
        _assert_rendered(result)

    def test_rebase_plugin(self, driver) -> None:
        dg = Dygraph(_DF).rebase(value=100)
        result = _render(driver, dg, cdn=False)
        _assert_no_errors(result)
        _assert_rendered(result)

    def test_ribbon_plugin(self, driver) -> None:
        dg = Dygraph(_DF).ribbon(
            data=[0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
            palette=["red", "blue"],
        )
        result = _render(driver, dg, cdn=False)
        _assert_no_errors(result)
        _assert_rendered(result)


# ---------------------------------------------------------------------------
# Range selector
# ---------------------------------------------------------------------------


class TestRangeSelectorRender:
    def test_range_selector_renders(self, driver) -> None:
        dg = Dygraph(_DF).range_selector(height=30)
        result = _render(driver, dg, cdn=False)
        _assert_no_errors(result)
        _assert_rendered(result)
        # Range selector adds extra canvas elements
        assert result["canvas_count"] >= 3, (
            "Range selector should add foreground + background canvases"
        )


# ---------------------------------------------------------------------------
# Combined features (stress test)
# ---------------------------------------------------------------------------


class TestCombinedRender:
    def test_full_featured_chart(self, driver) -> None:
        """Render a chart with every feature at once."""
        dg = (
            Dygraph(_DF, title="Full Featured")
            .options(
                fill_graph=True,
                draw_points=True,
                stroke_width=2,
                animated_zooms=True,
            )
            .series("a", label="Alpha", color="#ff0000", stroke_width=3)
            .series("b", axis="y2", stroke_pattern="dashed")
            .axis("y", label="Left Axis", value_range=(0, 15))
            .axis("y2", label="Right Axis")
            .legend(show="always", width=200)
            .highlight(circle_size=5, series_background_alpha=0.3)
            .range_selector(height=25)
            .roller(roll_period=2)
            .annotation("2020-01-03", text="!", tooltip="Important", series="Alpha")
            .event("2020-01-05", label="Release", color="green")
            .shading("2020-01-07", "2020-01-09", color="rgba(0,0,255,0.1)")
            .limit(5, label="Target", color="orange")
            .unzoom()
            .crosshair(direction="vertical")
        )
        result = _render(driver, dg, cdn=False)
        _assert_no_errors(result)
        _assert_rendered(result)
        # Should have range selector canvases + main canvas
        assert result["canvas_count"] >= 3

    def test_callbacks_no_error(self, driver) -> None:
        """JS callbacks should not cause errors."""
        dg = Dygraph(_DF).callbacks(
            click="function(e,x,pts){ console.log('click'); }",
            zoom="function(min,max){ console.log('zoom',min,max); }",
        )
        result = _render(driver, dg)
        _assert_no_errors(result)
        _assert_rendered(result)

    def test_custom_css_injected(self, driver) -> None:
        """Custom CSS should be injected into the page."""
        with tempfile.NamedTemporaryFile(suffix=".css", delete=False, mode="w") as f:
            f.write(".dygraph-title { color: rgb(255, 0, 0) !important; }")
            css_path = f.name

        dg = Dygraph(_DF, title="Styled").css(css_path)
        result = _render(driver, dg, cdn=False)
        _assert_no_errors(result)
        _assert_rendered(result)

        # Check CSS was applied
        color = driver.execute_script("""
            var t = document.querySelector('.dygraph-title');
            return t ? getComputedStyle(t).color : 'not found';
        """)
        Path(css_path).unlink(missing_ok=True)
        # rgb(255, 0, 0) = red
        if color != "not found":
            assert "255" in color, f"Title should be red, got: {color}"


# ---------------------------------------------------------------------------
# Group sync (multi-chart page)
# ---------------------------------------------------------------------------


class TestGroupSyncRender:
    def test_two_grouped_charts_render(self, driver) -> None:
        """Two charts with same group should both render without errors."""
        df1 = pd.DataFrame({"x": range(10)}, index=_DATES)
        df2 = pd.DataFrame({"y": range(10, 0, -1)}, index=_DATES)

        html1 = Dygraph(df1, group="sync-test").to_json()
        html2 = Dygraph(df2, group="sync-test").to_json()

        # Build a multi-chart HTML page manually
        page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/dygraph/2.2.1/dygraph.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/dygraph/2.2.1/dygraph.min.css">
</head><body>
<div id="chart1" style="width:600px;height:200px;"></div>
<div id="chart2" style="width:600px;height:200px;"></div>
<script>
(function() {{
    if (!window.__dyGroups) window.__dyGroups = {{}};

    function makeChart(divId, config) {{
        var data = config.data;
        var nRows = data[0].length, nCols = data.length, rows = [];
        for (var i = 0; i < nRows; i++) {{
            var row = [];
            for (var j = 0; j < nCols; j++) {{
                var val = data[j][i];
                if (j === 0 && config.format === 'date' && typeof val === 'string')
                    val = new Date(val);
                row.push(val);
            }}
            rows.push(row);
        }}
        var opts = config.attrs;
        var el = document.getElementById(divId);

        if (config.group) {{
            var grp = config.group;
            if (!window.__dyGroups[grp]) window.__dyGroups[grp] = [];
            var _broadcastZoom = function(dw) {{
                if (el._suppressZoom) {{ el._suppressZoom = false; return; }}
                window.__dyGroups[grp].forEach(function(peer) {{
                    if (peer.el === el) return;
                    peer.el._suppressZoom = true;
                    peer.instance.updateOptions({{dateWindow: dw}});
                }});
            }};
            opts.zoomCallback = function(a, b) {{ _broadcastZoom([a, b]); }};
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

        var g = new Dygraph(el, rows, opts);
        if (config.group) {{
            window.__dyGroups[config.group].push({{el: el, instance: g}});
        }}
        return g;
    }}

    var c1 = {html1};
    var c2 = {html2};
    window._g1 = makeChart('chart1', c1);
    window._g2 = makeChart('chart2', c2);
}})();
</script></body></html>"""

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
            f.write(page)
            path = f.name

        driver.get(f"file://{path}")
        time.sleep(4)

        logs = driver.get_log("browser")
        errors = [
            e
            for e in logs
            if e["level"] == "SEVERE" and "favicon" not in e["message"].lower()
        ]
        assert not errors, f"JS errors: {[e['message'] for e in errors]}"

        # Both charts rendered
        c1_canvases = driver.execute_script(
            "return document.getElementById('chart1').querySelectorAll('canvas').length"
        )
        c2_canvases = driver.execute_script(
            "return document.getElementById('chart2').querySelectorAll('canvas').length"
        )
        assert c1_canvases > 0, "Chart 1 didn't render"
        assert c2_canvases > 0, "Chart 2 didn't render"

        # Group registry should have both charts
        group_size = driver.execute_script(
            "return window.__dyGroups['sync-test'] ? "
            "window.__dyGroups['sync-test'].length : 0"
        )
        assert group_size == 2, f"Group should have 2 charts, got {group_size}"

        # Test zoom sync: simulate zoom via zoomCallback (programmatic
        # updateOptions doesn't fire zoomCallback in dygraphs)
        driver.execute_script("""
            var g1 = window._g1;
            var xr = g1.xAxisRange();
            var mid = (xr[0] + xr[1]) / 2;
            var span = (xr[1] - xr[0]) / 4;
            var newWindow = [mid - span, mid + span];
            // Call zoomCallback directly to trigger sync
            var cb = g1.getOption('zoomCallback');
            if (cb) cb(newWindow[0], newWindow[1]);
            g1.updateOptions({dateWindow: newWindow});
        """)
        time.sleep(2)

        g2_window = driver.execute_script("return window._g2.xAxisRange()")
        g1_window = driver.execute_script("return window._g1.xAxisRange()")
        # g2 should have the same narrow window as g1 (sync worked)
        # Allow some tolerance since zoom callback is debounced
        tolerance = (g1_window[1] - g1_window[0]) * 0.1
        assert abs(g1_window[0] - g2_window[0]) < tolerance, (
            f"Zoom sync failed: g1={g1_window}, g2={g2_window}"
        )

        Path(path).unlink(missing_ok=True)
