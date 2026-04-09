"""Tests for plotter methods — bar_chart, candlestick, stem_series, etc."""

from __future__ import annotations

import pandas as pd

from dygraphs import JS, Dygraph


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1]}, index=idx)


def _single() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame({"y": [1, 2, 3, 4, 5]}, index=idx)


class TestGlobalPlotters:
    def test_bar_chart_single_series(self) -> None:
        d = Dygraph(_single()).bar_chart()
        plotter = d.to_dict()["attrs"]["plotter"]
        assert isinstance(plotter, JS)

    def test_bar_chart_multi_series(self) -> None:
        d = Dygraph(_df()).bar_chart()
        plotter = d.to_dict()["attrs"]["plotter"]
        assert isinstance(plotter, JS)
        # multi-column plotter used when >1 series
        assert "multicolumn" in plotter.code.lower() or "MultiColumn" in plotter.code

    def test_stacked_bar_chart(self) -> None:
        d = Dygraph(_df()).stacked_bar_chart()
        assert isinstance(d.to_dict()["attrs"]["plotter"], JS)

    def test_multi_column(self) -> None:
        d = Dygraph(_df()).multi_column()
        assert isinstance(d.to_dict()["attrs"]["plotter"], JS)

    def test_candlestick(self) -> None:
        d = Dygraph(_df()).candlestick()
        assert isinstance(d.to_dict()["attrs"]["plotter"], JS)


class TestSeriesPlotters:
    def test_bar_series(self) -> None:
        d = Dygraph(_df()).bar_series("a")
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)

    def test_stem_series(self) -> None:
        d = Dygraph(_df()).stem_series("a")
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)

    def test_shadow(self) -> None:
        d = Dygraph(_df()).shadow("a")
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)

    def test_filled_line(self) -> None:
        d = Dygraph(_df()).filled_line("a")
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)

    def test_shadow_and_filled_line_use_distinct_plotters(self) -> None:
        """``shadow()`` and ``filled_line()`` must reference different
        plotter functions.

        Regression guard. Earlier, both methods loaded JS files that
        declared a function named ``filledlineplotter``, and both
        methods set ``plotter="filledlineplotter"``. When a chart used
        both methods, the second-loaded JS file's definition won the
        global namespace and silently changed the first method's
        behaviour. R doesn't have this bug because it inlines the
        plotter source directly into each series's options instead of
        going through a named global.

        After the fix, ``fillplotter.js`` exports
        ``function fillplotter(e)`` and ``filledline.js`` exports
        ``function filledlineplotter(e)``; the two methods reference
        the two distinct names, and a chart that uses both injects
        both functions side-by-side without collision.
        """
        shadow_plot = (
            Dygraph(_df()).shadow("a").to_dict()["attrs"]["series"]["a"]["plotter"]
        )
        filled_plot = (
            Dygraph(_df()).filled_line("a").to_dict()["attrs"]["series"]["a"]["plotter"]
        )
        assert str(shadow_plot) != str(filled_plot)
        assert "fillplotter" in shadow_plot.code
        assert "filledlineplotter" in filled_plot.code

    def test_shadow_and_filled_line_inject_both_functions(self) -> None:
        """Using both methods on the same chart must inject *both*
        plotter JS sources, with the function declarations intact."""
        cfg = Dygraph(_df()).shadow("a").filled_line("b").to_dict()
        extra = cfg.get("extraJs", [])
        assert any("function fillplotter" in j for j in extra)
        assert any("function filledlineplotter" in j for j in extra)

    def test_error_fill(self) -> None:
        d = Dygraph(_df()).error_fill("a")
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)


class TestGroupPlotters:
    def test_multi_column_group(self) -> None:
        d = Dygraph(_df()).multi_column_group(["a", "b"])
        cfg = d.to_dict()
        assert isinstance(cfg["attrs"]["series"]["a"]["plotter"], JS)
        assert cfg["attrs"]["series"]["a"]["group"] == "a\x1fb"

    def test_candlestick_group(self) -> None:
        d = Dygraph(_df()).candlestick_group(["a", "b"])
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)

    def test_stacked_bar_group(self) -> None:
        d = Dygraph(_df()).stacked_bar_group(["a", "b"])
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)

    def test_stacked_line_group(self) -> None:
        d = Dygraph(_df()).stacked_line_group(["a", "b"])
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)

    def test_stacked_ribbon_group(self) -> None:
        d = Dygraph(_df()).stacked_ribbon_group(["a", "b"])
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)
