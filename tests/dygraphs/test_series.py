"""Tests for series configuration — ports R test-series.R + extensions."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import Dygraph


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {"mdeaths": [10, 12, 11, 14, 13], "fdeaths": [5, 3, 7, 2, 6]}, index=idx
    )


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

    def test_unknown_point_shape_warns(self) -> None:
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            d = Dygraph(_df()).series("mdeaths", point_shape="custom_shape")
            assert len(w) == 1
            assert "Unrecognised" in str(w[0].message)
        assert d.to_dict()["pointShape"]["mdeaths"] == "custom_shape"


class TestSeriesRStyleErrorBands:
    """``.series([...])`` is sugar for ``.series(columns=[...])``.

    Mirrors R's ``dySeries(c("low","mid","high"))`` idiom — the most
    natural way to declare a custom error band from three columns.
    """

    @staticmethod
    def _band_df() -> pd.DataFrame:
        idx = pd.date_range("2020-01-01", periods=4, freq="D")
        return pd.DataFrame(
            {"lwr": [1, 2, 3, 4], "fit": [2, 3, 4, 5], "upr": [3, 4, 5, 6]}, index=idx
        )

    def test_three_column_band_via_positional_list(self) -> None:
        """``.series(["lwr","fit","upr"])`` enables custom bars."""
        d = Dygraph(self._band_df()).series(["lwr", "fit", "upr"], label="band")
        cfg = d.to_dict()
        assert cfg["attrs"]["customBars"] is True
        assert "band" in cfg["attrs"]["labels"]

    def test_two_column_error_via_positional_list(self) -> None:
        """``.series(["value","error"])`` enables symmetric error bars."""
        idx = pd.date_range("2020-01-01", periods=3, freq="D")
        df = pd.DataFrame({"y": [10, 20, 30], "err": [1, 2, 3]}, index=idx)
        d = Dygraph(df).series(["y", "err"], label="signal")
        cfg = d.to_dict()
        assert cfg["attrs"]["errorBars"] is True
        assert "signal" in cfg["attrs"]["labels"]

    def test_tuple_also_works(self) -> None:
        """A tuple is just as valid as a list — same Python idiom."""
        d = Dygraph(self._band_df()).series(("lwr", "fit", "upr"), label="band")
        assert d.to_dict()["attrs"]["customBars"] is True

    def test_passing_both_list_and_columns_kwarg_raises(self) -> None:
        """Belt-and-braces: refuse the ambiguous form rather than silently
        picking one."""
        with pytest.raises(ValueError, match="cannot pass both"):
            Dygraph(self._band_df()).series(
                ["lwr", "fit"], columns=["fit", "upr"], label="x"
            )

    def test_string_name_still_works_unchanged(self) -> None:
        """Regression: passing a single string must NOT be misread as a list."""
        d = Dygraph(self._band_df()).series("fit", color="red")
        assert d.to_dict()["attrs"]["colors"][1] == "red"
