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

    def test_error_fill(self) -> None:
        d = Dygraph(_df()).error_fill("a")
        assert isinstance(d.to_dict()["attrs"]["series"]["a"]["plotter"], JS)


class TestGroupPlotters:
    def test_multi_column_group(self) -> None:
        d = Dygraph(_df()).multi_column_group(["a", "b"])
        cfg = d.to_dict()
        assert isinstance(cfg["attrs"]["series"]["a"]["plotter"], JS)
        assert cfg["attrs"]["series"]["a"]["group"] == "ab"

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
