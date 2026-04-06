"""Tests for options — ports R test-plotter.R (custom plotter) + extensions."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import JS, Dygraph


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"y": range(5)},
        index=pd.date_range("2020-01-01", periods=5, freq="D"),
    )


class TestOptions:
    """Port of R ``context("dyOptions")`` (custom plotter test)."""

    def test_custom_plotter(self) -> None:
        d = Dygraph(_df()).options(plotter="function(){}")
        plotter = d.to_dict()["attrs"]["plotter"]
        assert isinstance(plotter, JS)

    def test_fill_graph(self) -> None:
        d = Dygraph(_df()).options(fill_graph=True, fill_alpha=0.3)
        cfg = d.to_dict()["attrs"]
        assert cfg["fillGraph"] is True
        assert cfg["fillAlpha"] == 0.3

    def test_step_plot(self) -> None:
        d = Dygraph(_df()).options(step_plot=True)
        assert d.to_dict()["attrs"]["stepPlot"] is True

    def test_stem_plot(self) -> None:
        d = Dygraph(_df()).options(stem_plot=True)
        plotter = d.to_dict()["attrs"]["plotter"]
        assert isinstance(plotter, JS)
        assert "stemPlotter" in plotter.code

    def test_stem_plot_conflicts_with_plotter(self) -> None:
        with pytest.raises(ValueError, match="stem_plot"):
            Dygraph(_df()).options(stem_plot=True, plotter="function(){}")

    def test_colors(self) -> None:
        d = Dygraph(_df()).options(colors=["red", "blue"])
        assert d.to_dict()["attrs"]["colors"] == ["red", "blue"]

    def test_axis_visibility(self) -> None:
        d = Dygraph(_df()).options(draw_x_axis=False, draw_y_axis=False)
        cfg = d.to_dict()["attrs"]
        assert cfg["axes"]["x"]["drawAxis"] is False
        assert cfg["axes"]["y"]["drawAxis"] is False

    def test_grid(self) -> None:
        d = Dygraph(_df()).options(draw_grid=False, grid_line_color="#ccc")
        cfg = d.to_dict()["attrs"]
        assert cfg["drawGrid"] is False
        assert cfg["gridLineColor"] == "#ccc"

    def test_labels_kmb(self) -> None:
        d = Dygraph(_df()).options(labels_kmb=True)
        assert d.to_dict()["attrs"]["labelsKMB"] is True

    def test_animated_zooms(self) -> None:
        d = Dygraph(_df()).options(animated_zooms=True)
        assert d.to_dict()["attrs"]["animatedZooms"] is True

    def test_disable_zoom(self) -> None:
        d = Dygraph(_df()).options(disable_zoom=True)
        assert d.to_dict()["attrs"]["disableZoom"] is True

    def test_include_zero(self) -> None:
        d = Dygraph(_df()).options(include_zero=True)
        assert d.to_dict()["attrs"]["includeZero"] is True

    def test_logscale(self) -> None:
        d = Dygraph(_df()).options(logscale=True)
        assert d.to_dict()["attrs"]["logscale"] is True

    def test_stroke_pattern(self) -> None:
        d = Dygraph(_df()).options(stroke_pattern="dashed")
        assert d.to_dict()["attrs"]["strokePattern"] == [7, 3]

    def test_point_shape_global(self) -> None:
        d = Dygraph(_df()).options(point_shape="star")
        assert d.to_dict()["pointShape"]["__global__"] == "star"

    def test_invalid_point_shape(self) -> None:
        with pytest.raises(ValueError, match="Invalid point_shape"):
            Dygraph(_df()).options(point_shape="banana")
