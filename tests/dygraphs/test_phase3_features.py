"""Tests for Phase 3 features: error bar columns, candlestick compress,
generic plugin/plotter/handler, series_data, group label/stemPlot."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import Dygraph
from dygraphs.utils import JS

_DATES = pd.date_range("2020-01-01", periods=5, freq="D")


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1], "c": [0.5, 1, 0.5, 1, 0.5]},
        index=_DATES,
    )


# ---------------------------------------------------------------------------
# Error bar columns (series(columns=...))
# ---------------------------------------------------------------------------


class TestErrorBarColumns:
    def test_custom_bars_3_columns(self) -> None:
        """3 columns → customBars mode, merged into [low, mid, high] tuples."""
        d = Dygraph(_df()).series(columns=["c", "a", "b"])
        cfg = d.to_dict()
        assert cfg["attrs"]["customBars"] is True
        # Middle column "a" becomes display name
        assert "a" in cfg["attrs"]["labels"]
        # Original columns removed, merged column added
        assert "c" not in cfg["attrs"]["labels"]
        assert "b" not in cfg["attrs"]["labels"]
        # Data should contain tuples
        merged_idx = cfg["attrs"]["labels"].index("a")
        merged_col = cfg["data"][merged_idx]
        assert merged_col[0] == [0.5, 1, 5]  # [c[0], a[0], b[0]]

    def test_error_bars_2_columns(self) -> None:
        """2 columns → errorBars mode, merged into [value, error] tuples."""
        d = Dygraph(_df()).series(columns=["a", "c"])
        cfg = d.to_dict()
        assert cfg["attrs"]["errorBars"] is True
        # First column "a" becomes display name
        assert "a" in cfg["attrs"]["labels"]
        assert "c" not in cfg["attrs"]["labels"]
        merged_idx = cfg["attrs"]["labels"].index("a")
        merged_col = cfg["data"][merged_idx]
        assert merged_col[0] == [1, 0.5]  # [a[0], c[0]]

    def test_custom_bars_with_label(self) -> None:
        """label= overrides the display name."""
        d = Dygraph(_df()).series(columns=["c", "a", "b"], label="MyBars")
        cfg = d.to_dict()
        assert "MyBars" in cfg["attrs"]["labels"]

    def test_invalid_column_count(self) -> None:
        with pytest.raises(ValueError, match="columns must have"):
            Dygraph(_df()).series(columns=["a"])

    def test_invalid_column_name(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            Dygraph(_df()).series(columns=["a", "nonexistent", "b"])


# ---------------------------------------------------------------------------
# Candlestick compress
# ---------------------------------------------------------------------------


class TestCandlestickCompress:
    def test_compress_false_no_extra_js(self) -> None:
        df = pd.DataFrame(
            {"o": [1, 2], "h": [3, 4], "l": [0, 1], "c": [2, 3]}, index=_DATES[:2]
        )
        d = Dygraph(df).candlestick()
        cfg = d.to_dict()
        # No compress plugin
        extra = cfg.get("extraJs", [])
        assert not any("Compress" in js for js in extra)

    def test_compress_true_injects_plugin(self) -> None:
        df = pd.DataFrame(
            {"o": [1, 2], "h": [3, 4], "l": [0, 1], "c": [2, 3]}, index=_DATES[:2]
        )
        d = Dygraph(df).candlestick(compress=True)
        cfg = d.to_dict()
        extra = cfg.get("extraJs", [])
        assert any("compress" in js.lower() or "Compress" in js for js in extra)
        assert isinstance(cfg["attrs"]["dataHandler"], JS)


# ---------------------------------------------------------------------------
# Generic plugin/plotter/handler
# ---------------------------------------------------------------------------


class TestGenericPlugin:
    def test_plugin_registers(self) -> None:
        d = Dygraph(_df()).plugin("MyPlugin", js="var x=1;", options={"foo": "bar"})
        cfg = d.to_dict()
        p = next(p for p in cfg["plugins"] if p["name"] == "MyPlugin")
        assert p["options"] == {"foo": "bar"}
        assert "var x=1;" in cfg["extraJs"]

    def test_plugin_without_js(self) -> None:
        d = Dygraph(_df()).plugin("External", options=42)
        cfg = d.to_dict()
        p = next(p for p in cfg["plugins"] if p["name"] == "External")
        assert p["options"] == 42

    def test_plugin_chaining(self) -> None:
        d = Dygraph(_df()).plugin("A").plugin("B")
        names = [p["name"] for p in d.to_dict()["plugins"]]
        assert names == ["A", "B"]


class TestCustomPlotter:
    def test_custom_plotter_sets_attr(self) -> None:
        js_code = "function myPlotter(e) { /* custom */ }"
        d = Dygraph(_df()).custom_plotter(js_code)
        cfg = d.to_dict()
        assert isinstance(cfg["attrs"]["plotter"], JS)
        assert cfg["attrs"]["plotter"].code == js_code

    def test_custom_plotter_chainable(self) -> None:
        d = Dygraph(_df()).custom_plotter("function(){}").options(fill_graph=True)
        assert d.to_dict()["attrs"]["fillGraph"] is True


class TestDataHandler:
    def test_data_handler_sets_attr(self) -> None:
        js_code = "function myHandler() {}"
        d = Dygraph(_df()).data_handler(js_code)
        cfg = d.to_dict()
        assert isinstance(cfg["attrs"]["dataHandler"], JS)


# ---------------------------------------------------------------------------
# series_data
# ---------------------------------------------------------------------------


class TestSeriesData:
    def test_adds_column(self) -> None:
        d = Dygraph(_df()).series_data("extra", [10, 20, 30, 40, 50])
        cfg = d.to_dict()
        assert "extra" in cfg["attrs"]["labels"]
        idx = cfg["attrs"]["labels"].index("extra")
        assert cfg["data"][idx] == [10, 20, 30, 40, 50]

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="length"):
            Dygraph(_df()).series_data("bad", [1, 2])

    def test_chainable(self) -> None:
        d = (
            Dygraph(_df())
            .series_data("x1", [1, 2, 3, 4, 5])
            .series_data("x2", [5, 4, 3, 2, 1])
        )
        labels = d.to_dict()["attrs"]["labels"]
        assert "x1" in labels
        assert "x2" in labels


# ---------------------------------------------------------------------------
# group() label and stem_plot params
# ---------------------------------------------------------------------------


class TestGroupNewParams:
    def test_group_with_label(self) -> None:
        d = Dygraph(_df()).group(["a", "b"], label=["Alpha", "Beta"])
        cfg = d.to_dict()
        assert cfg["attrs"]["series"]["a"].get("label") == "Alpha"
        assert cfg["attrs"]["series"]["b"].get("label") == "Beta"

    def test_group_stem_plot(self) -> None:
        d = Dygraph(_df()).group(["a", "b"], stem_plot=True)
        cfg = d.to_dict()
        # stem_plot should set a plotter JS function
        assert isinstance(cfg["attrs"]["series"]["a"]["plotter"], JS)
        assert isinstance(cfg["attrs"]["series"]["b"]["plotter"], JS)

    def test_group_stem_plot_conflicts_with_plotter(self) -> None:
        with pytest.raises(ValueError, match="stem_plot"):
            Dygraph(_df()).group(["a", "b"], stem_plot=True, plotter="function(){}")


# ---------------------------------------------------------------------------
# mobile_disable_y_touch and use_data_timezone
# ---------------------------------------------------------------------------


class TestNewOptions:
    def test_mobile_disable_y_touch_default(self) -> None:
        """Default True — should NOT emit (matches R default)."""
        d = Dygraph(_df()).options()
        assert "mobileDisableYTouch" not in d.to_dict()["attrs"]

    def test_mobile_disable_y_touch_false(self) -> None:
        d = Dygraph(_df()).options(mobile_disable_y_touch=False)
        assert d.to_dict()["attrs"]["mobileDisableYTouch"] is False

    def test_use_data_timezone(self) -> None:
        d = Dygraph(_df()).options(use_data_timezone=True)
        assert d.to_dict()["attrs"]["useDataTimezone"] is True
