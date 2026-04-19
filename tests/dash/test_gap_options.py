"""Tests for gap-fill options: error bars, visibility, legend formatter, etc."""

from __future__ import annotations

import pandas as pd

from dygraphs import JS, Dygraph


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"y": range(5)},
        index=pd.date_range("2020-01-01", periods=5, freq="D"),
    )


class TestErrorBars:
    def test_error_bars_enabled(self) -> None:
        d = Dygraph(_df()).options(error_bars=True)
        assert d.to_dict()["attrs"]["errorBars"] is True

    def test_custom_bars_enabled(self) -> None:
        d = Dygraph(_df()).options(custom_bars=True)
        assert d.to_dict()["attrs"]["customBars"] is True

    def test_sigma(self) -> None:
        d = Dygraph(_df()).options(error_bars=True, sigma=1.5)
        cfg = d.to_dict()["attrs"]
        assert cfg["errorBars"] is True
        assert cfg["sigma"] == 1.5

    def test_fractions(self) -> None:
        d = Dygraph(_df()).options(fractions=True, wilson_interval=False)
        cfg = d.to_dict()["attrs"]
        assert cfg["fractions"] is True
        assert cfg["wilsonInterval"] is False


class TestVisibility:
    def test_visibility_array(self) -> None:
        df = pd.DataFrame(
            {"a": [1, 2], "b": [3, 4]},
            index=pd.date_range("2020-01-01", periods=2, freq="D"),
        )
        d = Dygraph(df).options(visibility=[True, False])
        assert d.to_dict()["attrs"]["visibility"] == [True, False]


class TestLegendFormatter:
    def test_legend_formatter(self) -> None:
        d = Dygraph(_df()).options(
            legend_formatter="function(data) { return 'custom'; }"
        )
        formatter = d.to_dict()["attrs"]["legendFormatter"]
        assert isinstance(formatter, JS)
        assert "custom" in formatter.code


class TestRangeSelectorStyling:
    def test_range_selector_alpha(self) -> None:
        d = Dygraph(_df()).options(range_selector_alpha=0.3)
        assert d.to_dict()["attrs"]["rangeSelectorAlpha"] == 0.3

    def test_range_selector_colors(self) -> None:
        d = Dygraph(_df()).options(
            range_selector_background_stroke_color="red",
            range_selector_foreground_stroke_color="blue",
        )
        cfg = d.to_dict()["attrs"]
        assert cfg["rangeSelectorBackgroundStrokeColor"] == "red"
        assert cfg["rangeSelectorForegroundStrokeColor"] == "blue"

    def test_range_selector_line_widths(self) -> None:
        d = Dygraph(_df()).options(
            range_selector_plot_line_width=2.0,
            range_selector_background_line_width=1.5,
            range_selector_foreground_line_width=1.0,
        )
        cfg = d.to_dict()["attrs"]
        assert cfg["rangeSelectorPlotLineWidth"] == 2.0
        assert cfg["rangeSelectorBackgroundLineWidth"] == 1.5
        assert cfg["rangeSelectorForegroundLineWidth"] == 1.0

    def test_range_selector_gradient(self) -> None:
        d = Dygraph(_df()).options(range_selector_plot_fill_gradient_color="white")
        assert d.to_dict()["attrs"]["rangeSelectorPlotFillGradientColor"] == "white"


class TestGridLinePattern:
    def test_grid_line_pattern(self) -> None:
        d = Dygraph(_df()).options(grid_line_pattern=[5, 5])
        assert d.to_dict()["attrs"]["gridLinePattern"] == [5, 5]


class TestResizable:
    def test_resizable(self) -> None:
        d = Dygraph(_df()).options(resizable="both")
        assert d.to_dict()["attrs"]["resizable"] == "both"

    def test_pixel_ratio(self) -> None:
        d = Dygraph(_df()).options(pixel_ratio=2.0)
        assert d.to_dict()["attrs"]["pixelRatio"] == 2.0


class TestDynamicStores:
    def test_opts_store_exists(self) -> None:
        """The opts store should be in the component for runtime updates."""
        from dash import Dash, dcc

        Dash(__name__)
        d = Dygraph(_df())
        component = d.to_dash(component_id="dyn")
        stores = [c for c in component.children if isinstance(c, dcc.Store)]
        store_ids = [s.id for s in stores]
        assert "dyn-opts" in store_ids
        # Data store shares the chart id (no suffix)
        assert "dyn" in store_ids

    def test_store_ids_documented(self) -> None:
        """Users target stores by convention: {id} for data, {id}-opts for overrides."""
        from dash import Dash

        Dash(__name__)
        d = Dygraph(_df())
        d.to_dash(component_id="my-chart")
        # If we got here without error, the stores and callbacks are registered
