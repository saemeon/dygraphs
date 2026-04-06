"""Tests for core Dygraph builder — ports R test-dygraph.R + extensions."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import Dygraph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_df() -> pd.DataFrame:
    """Simple time-series DataFrame for testing."""
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {"temp": [10, 12, 11, 14, 13], "rain": [5, 3, 7, 2, 6]}, index=idx
    )


def _sample_numeric_df() -> pd.DataFrame:
    """Numeric (non-date) DataFrame."""
    return pd.DataFrame(
        {"x": [1, 2, 3, 4], "y": [10, 20, 30, 40], "z": [5, 15, 25, 35]}
    )


# ---------------------------------------------------------------------------
# R port: test-dygraph.R
# ---------------------------------------------------------------------------


class TestDygraphCreation:
    """Port of R ``context("dygraph")``."""

    def test_create_from_dataframe(self) -> None:
        df = _sample_df()
        d = Dygraph(df)
        cfg = d.to_dict()
        assert cfg["format"] == "date"
        assert len(cfg["data"]) == 3  # x + 2 series
        assert len(cfg["attrs"]["labels"]) == 3

    def test_xlab(self) -> None:
        d = Dygraph(_sample_df(), xlab="X-Axis")
        assert d.to_dict()["attrs"]["xlabel"] == "X-Axis"

    def test_ylab(self) -> None:
        d = Dygraph(_sample_df(), ylab="Y-Axis")
        assert d.to_dict()["attrs"]["ylabel"] == "Y-Axis"

    def test_title(self) -> None:
        d = Dygraph(_sample_df(), title="My Chart")
        assert d.to_dict()["attrs"]["title"] == "My Chart"


# ---------------------------------------------------------------------------
# Data input formats
# ---------------------------------------------------------------------------


class TestDataFormats:
    def test_series_input(self) -> None:
        s = pd.Series([1, 2, 3], name="vals")
        d = Dygraph(s)
        assert len(d.to_dict()["data"]) == 2

    def test_dict_input(self) -> None:
        d = Dygraph({"x": [1, 2, 3], "y": [10, 20, 30]})
        cfg = d.to_dict()
        assert cfg["format"] == "numeric"
        assert cfg["attrs"]["labels"] == ["x", "y"]

    def test_list_input(self) -> None:
        d = Dygraph([[1, 10], [2, 20], [3, 30]])
        cfg = d.to_dict()
        assert cfg["format"] == "numeric"
        assert len(cfg["data"]) == 2

    def test_numeric_df(self) -> None:
        df = _sample_numeric_df().set_index("x")
        d = Dygraph(df)
        assert d.to_dict()["format"] == "numeric"

    def test_empty_dict_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            Dygraph({})

    def test_bad_type_raises(self) -> None:
        with pytest.raises(TypeError):
            Dygraph(12345)  # type: ignore[arg-type]

    def test_csv_string_input(self) -> None:
        csv = "Date,A,B\n2024-01-01,1,2\n2024-01-02,3,4\n2024-01-03,5,6"
        d = Dygraph(csv)
        cfg = d.to_dict()
        assert cfg["format"] == "date"
        assert "A" in cfg["attrs"]["labels"]
        assert "B" in cfg["attrs"]["labels"]
        assert len(cfg["data"][0]) == 3  # 3 rows

    def test_csv_string_numeric(self) -> None:
        csv = "x,y\n1,10\n2,20\n3,30"
        d = Dygraph(csv)
        cfg = d.to_dict()
        assert cfg["format"] == "numeric"


# ---------------------------------------------------------------------------
# Method chaining
# ---------------------------------------------------------------------------


class TestChaining:
    def test_methods_return_self(self) -> None:
        df = _sample_df()
        result = (
            Dygraph(df, title="Test")
            .options(fill_graph=True)
            .axis("y", label="Temp")
            .series("temp", color="red")
            .legend(show="always")
            .highlight(circle_size=5)
            .range_selector()
            .roller(roll_period=3)
        )
        assert isinstance(result, Dygraph)

    def test_full_pipeline_serialises(self) -> None:
        df = _sample_df()
        d = (
            Dygraph(df, title="Full Test")
            .options(fill_graph=True, draw_points=True)
            .axis("y", label="Temp", value_range=(0, 20))
            .series("temp", color="red", stroke_width=2)
            .legend(show="always")
            .highlight(circle_size=5, series_background_alpha=0.2)
            .annotation("2020-01-03", "A", tooltip="Annotation")
            .shading("2020-01-01", "2020-01-02")
            .event("2020-01-04", "Event")
            .limit(12.0, "Limit")
            .range_selector(height=30)
            .roller(roll_period=2)
            .callbacks(click="function(e){}")
        )
        cfg = d.to_dict()
        assert cfg["attrs"]["title"] == "Full Test"
        assert cfg["attrs"]["fillGraph"] is True
        assert len(cfg["annotations"]) == 1
        assert len(cfg["shadings"]) == 1
        assert len(cfg["events"]) == 2  # event + limit
