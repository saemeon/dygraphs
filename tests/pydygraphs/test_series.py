"""Tests for series configuration — ports R test-series.R + extensions."""

from __future__ import annotations

import pandas as pd
import pytest

from pydygraphs import Dygraph


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame({"mdeaths": [10, 12, 11, 14, 13], "fdeaths": [5, 3, 7, 2, 6]}, index=idx)


class TestSeries:
    """Port of R ``context("dySeries")``."""

    def test_series_label(self) -> None:
        d = Dygraph(_df()).series("mdeaths", label="Male Deaths", fill_graph=False)
        cfg = d.to_dict()
        # Label renamed in labels list
        assert "Male Deaths" in cfg["attrs"]["labels"]
        assert cfg["attrs"]["series"]["Male Deaths"]["fillGraph"] is False

    def test_series_color(self) -> None:
        d = Dygraph(_df()).series("mdeaths", color="blue")
        cfg = d.to_dict()
        assert "colors" in cfg["attrs"]
        # mdeaths is index 0 (first after x)
        assert cfg["attrs"]["colors"][0] == "blue"

    def test_series_axis_y2(self) -> None:
        d = Dygraph(_df()).series("fdeaths", axis="y2")
        assert d.to_dict()["attrs"]["series"]["fdeaths"]["axis"] == "y2"

    def test_series_not_found(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            Dygraph(_df()).series("nonexistent")

    def test_series_step_plot(self) -> None:
        d = Dygraph(_df()).series("mdeaths", step_plot=True)
        assert d.to_dict()["attrs"]["series"]["mdeaths"]["stepPlot"] is True

    def test_series_stroke_pattern(self) -> None:
        d = Dygraph(_df()).series("mdeaths", stroke_pattern="dashed")
        assert d.to_dict()["attrs"]["series"]["mdeaths"]["strokePattern"] == [7, 3]

    def test_series_point_shape(self) -> None:
        d = Dygraph(_df()).series("mdeaths", point_shape="star")
        cfg = d.to_dict()
        assert cfg["pointShape"]["mdeaths"] == "star"

    def test_invalid_point_shape(self) -> None:
        with pytest.raises(ValueError, match="Invalid point_shape"):
            Dygraph(_df()).series("mdeaths", point_shape="invalid")
