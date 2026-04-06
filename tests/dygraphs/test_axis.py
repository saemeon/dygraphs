"""Tests for axis configuration — ports R test-axis.R + extensions."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import Dygraph


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"y": range(5)},
        index=pd.date_range("2020-01-01", periods=5, freq="D"),
    )


class TestAxis:
    """Port of R ``context("dyAxis")``."""

    def test_axis_label_and_grid(self) -> None:
        d = Dygraph(_df()).axis("x", label="x-axis", draw_grid=False)
        cfg = d.to_dict()
        assert cfg["attrs"]["xlabel"] == "x-axis"
        assert cfg["attrs"]["axes"]["x"]["drawGrid"] is False

    def test_y_axis_value_range(self) -> None:
        d = Dygraph(_df()).axis("y", value_range=(0, 100))
        assert d.to_dict()["attrs"]["axes"]["y"]["valueRange"] == [0, 100]

    def test_y2_axis(self) -> None:
        d = Dygraph(_df()).axis("y2", label="Secondary", independent_ticks=True)
        cfg = d.to_dict()
        assert cfg["attrs"]["y2label"] == "Secondary"
        assert cfg["attrs"]["axes"]["y2"]["independentTicks"] is True

    def test_invalid_axis_name(self) -> None:
        with pytest.raises(ValueError, match="Axis name"):
            Dygraph(_df()).axis("z")  # type: ignore[arg-type]

    def test_axis_height_only_x(self) -> None:
        d = Dygraph(_df()).axis("x", axis_height=30)
        assert d.to_dict()["attrs"]["xAxisHeight"] == 30

        with pytest.raises(ValueError, match="only applicable"):
            Dygraph(_df()).axis("y", axis_height=30)

    def test_pixels_per_label(self) -> None:
        d = Dygraph(_df()).axis("y", pixels_per_label=50)
        assert d.to_dict()["attrs"]["axes"]["y"]["pixelsPerLabel"] == 50
