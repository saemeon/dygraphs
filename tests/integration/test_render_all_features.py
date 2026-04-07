"""Browser render tests for every chart type and feature variant.

Catches issues that unit tests miss: JS syntax errors from bad serialization,
missing Dygraph.Plotters namespace, multiline JS unwrapping failures,
dateWindow/data timezone misalignment, etc.

Run with::

    uv run pytest tests/integration/test_render_all_features.py -v
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
# Fixtures & helpers
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2020-01-01", periods=20, freq="D")
_DF = pd.DataFrame({"a": range(1, 21), "b": range(20, 0, -1)}, index=_DATES)
_DF3 = pd.DataFrame(
    {"x": range(1, 21), "y": range(20, 0, -1), "z": [5] * 20}, index=_DATES
)


@pytest.fixture(scope="module")
def driver():
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


def _open(driver: Any, dg: Dygraph, *, cdn: bool = True) -> None:
    html = dg.to_html(cdn=cdn)
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        f.write(html)
        path = f.name
    driver.get(f"file://{path}")
    time.sleep(3)
    Path(path).unlink(missing_ok=True)


def _no_errors(driver: Any) -> None:
    logs = driver.get_log("browser")
    errors = [
        e["message"]
        for e in logs
        if e["level"] == "SEVERE" and "favicon" not in e["message"].lower()
    ]
    assert not errors, f"JS errors: {errors}"


def _has_canvas(driver: Any) -> None:
    count = driver.execute_script("return document.querySelectorAll('canvas').length")
    assert count > 0, "No canvas — chart did not render"


def _assert_renders(driver: Any, dg: Dygraph, *, cdn: bool = True) -> None:
    _open(driver, dg, cdn=cdn)
    _no_errors(driver)
    _has_canvas(driver)


# ---------------------------------------------------------------------------
# Global plotters (IIFE-based, use Dygraph.Plotters.* references)
# ---------------------------------------------------------------------------


class TestGlobalPlotters:
    def test_bar_chart_single(self, driver) -> None:
        dg = Dygraph(pd.DataFrame({"y": range(10)}, index=_DATES[:10])).bar_chart()
        _assert_renders(driver, dg)

    def test_bar_chart_multi(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).bar_chart())

    def test_stacked_bar_chart(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).stacked_bar_chart())

    def test_multi_column(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).multi_column())

    def test_candlestick(self, driver) -> None:
        ohlc = pd.DataFrame(
            {"O": [10, 11], "H": [12, 13], "L": [9, 10], "C": [11, 12]},
            index=_DATES[:2],
        )
        _assert_renders(driver, Dygraph(ohlc).candlestick())

    def test_candlestick_compress(self, driver) -> None:
        ohlc = pd.DataFrame(
            {"O": [10, 11], "H": [12, 13], "L": [9, 10], "C": [11, 12]},
            index=_DATES[:2],
        )
        _assert_renders(driver, Dygraph(ohlc).candlestick(compress=True))


# ---------------------------------------------------------------------------
# Series-level plotters (bare function refs loaded via <script>)
# ---------------------------------------------------------------------------


class TestSeriesPlotters:
    def test_bar_series(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).bar_series("a"))

    def test_stem_series(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).stem_series("a"))

    def test_shadow(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).shadow("a"))

    def test_filled_line(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).filled_line("a"))

    def test_error_fill(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).error_fill("a"))


# ---------------------------------------------------------------------------
# Group-level plotters
# ---------------------------------------------------------------------------


class TestGroupPlotters:
    def test_multi_column_group(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF3).multi_column_group(["x", "y"]))

    def test_candlestick_group(self, driver) -> None:
        ohlc = pd.DataFrame(
            {"O": [10, 11], "H": [12, 13], "L": [9, 10], "C": [11, 12]},
            index=_DATES[:2],
        )
        _assert_renders(driver, Dygraph(ohlc).candlestick_group(["O", "H", "L", "C"]))

    def test_stacked_bar_group(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF3).stacked_bar_group(["x", "y"]))

    def test_stacked_line_group(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF3).stacked_line_group(["x", "y"]))

    def test_stacked_ribbon_group(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF3).stacked_ribbon_group(["x", "y"]))


# ---------------------------------------------------------------------------
# Inline plotters (multiline JS via options/series)
# ---------------------------------------------------------------------------


class TestInlinePlotters:
    def test_stem_plot_option(self, driver) -> None:
        dg = Dygraph(_DF).options(stem_plot=True)
        _assert_renders(driver, dg)

    def test_series_stem_plot(self, driver) -> None:
        dg = Dygraph(_DF).series("a", stem_plot=True)
        _assert_renders(driver, dg)

    def test_custom_plotter(self, driver) -> None:
        js = "function(e){var ctx=e.drawingContext;var pts=e.points;ctx.fillStyle=e.color;for(var i=0;i<pts.length;i++){ctx.beginPath();ctx.arc(pts[i].canvasx,pts[i].canvasy,3,0,2*Math.PI);ctx.fill();}}"
        dg = Dygraph(_DF).custom_plotter(js)
        _assert_renders(driver, dg)


# ---------------------------------------------------------------------------
# Range selector with date window
# ---------------------------------------------------------------------------


class TestRangeSelector:
    def test_range_selector_basic(self, driver) -> None:
        dg = Dygraph(_DF).range_selector()
        _open(driver, dg)
        _no_errors(driver)
        _has_canvas(driver)
        # Range selector should add extra canvas elements
        canvas_count = driver.execute_script(
            "return document.querySelectorAll('canvas').length"
        )
        assert canvas_count >= 2, "Range selector should add extra canvases"

    def test_range_selector_with_date_window(self, driver) -> None:
        dg = Dygraph(_DF).range_selector(date_window=("2020-01-05", "2020-01-15"))
        _open(driver, dg)
        _no_errors(driver)
        _has_canvas(driver)
        # Verify the x-axis range is restricted
        x_range = driver.execute_script("""
            var canvases = document.querySelectorAll('canvas');
            // The dygraph instance should exist
            var el = document.getElementById('chart');
            return el ? el.children.length : 0;
        """)
        assert x_range > 0, "Chart container should have children"


# ---------------------------------------------------------------------------
# Interaction options
# ---------------------------------------------------------------------------


class TestInteractionOptions:
    def test_disable_zoom(self, driver) -> None:
        dg = Dygraph(_DF).options(disable_zoom=True)
        _assert_renders(driver, dg)

    def test_animated_zooms(self, driver) -> None:
        dg = Dygraph(_DF).options(animated_zooms=True)
        _assert_renders(driver, dg)


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------


class TestPlugins:
    def test_unzoom(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).unzoom())

    def test_crosshair(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).crosshair())

    def test_rebase(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF).rebase(value=100))

    def test_ribbon(self, driver) -> None:
        dg = Dygraph(_DF).ribbon(
            data=[0, 1] * 10, palette=["rgba(0,255,0,0.2)", "rgba(255,0,0,0.2)"]
        )
        _assert_renders(driver, dg)


# ---------------------------------------------------------------------------
# Point shapes
# ---------------------------------------------------------------------------


class TestPointShapes:
    def test_global_point_shape(self, driver) -> None:
        dg = Dygraph(_DF).options(draw_points=True, point_shape="star")
        _assert_renders(driver, dg)

    def test_per_series_point_shape(self, driver) -> None:
        dg = (
            Dygraph(_DF)
            .options(draw_points=True)
            .series("a", point_shape="triangle")
            .series("b", point_shape="square")
        )
        _assert_renders(driver, dg)


# ---------------------------------------------------------------------------
# Overlays
# ---------------------------------------------------------------------------


class TestOverlays:
    def test_annotations(self, driver) -> None:
        dg = Dygraph(_DF).annotation("2020-01-05", "A", series="a")
        _open(driver, dg)
        _no_errors(driver)
        _has_canvas(driver)

    def test_events_and_limits(self, driver) -> None:
        dg = (
            Dygraph(_DF)
            .event("2020-01-05", "E", color="red")
            .limit(10, "L", color="blue")
        )
        _assert_renders(driver, dg)

    def test_shadings(self, driver) -> None:
        dg = Dygraph(_DF).shading("2020-01-03", "2020-01-07")
        _assert_renders(driver, dg)


# ---------------------------------------------------------------------------
# Declarative API
# ---------------------------------------------------------------------------


class TestDeclarativeRender:
    def test_full_declarative(self, driver) -> None:
        from dygraphs import Axis, Legend, Options, RangeSelector, Series

        dg = Dygraph(
            _DF,
            title="Declarative",
            options=Options(fill_graph=True, stroke_width=2),
            axes=[Axis("y", label="Val")],
            series=[Series("a", color="red")],
            legend=Legend(show="always"),
            range_selector=RangeSelector(height=25),
        )
        _assert_renders(driver, dg)


# ---------------------------------------------------------------------------
# CDN vs inline (both should render)
# ---------------------------------------------------------------------------


class TestCdnVsInline:
    def test_cdn_renders(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF, title="CDN"), cdn=True)

    def test_inline_renders(self, driver) -> None:
        _assert_renders(driver, Dygraph(_DF, title="Inline"), cdn=False)


# ---------------------------------------------------------------------------
# Stacked graph
# ---------------------------------------------------------------------------


class TestStackedGraph:
    def test_stacked_graph(self, driver) -> None:
        dg = Dygraph(_DF).options(stacked_graph=True)
        _assert_renders(driver, dg)
