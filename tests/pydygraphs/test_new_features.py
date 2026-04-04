"""Tests for new features: numpy input, to_html, from_csv, update, copy, error bar helpers, plotter declarative, mixed usage."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pydygraphs import (
    Dygraph,
    Legend,
    Options,
    Series,
    make_custom_bar_data,
    make_error_bar_data,
)


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame({"temp": [10, 12, 11, 14, 13], "rain": [5, 3, 7, 2, 6]}, index=idx)


# ---------------------------------------------------------------------------
# 1. Numpy array input
# ---------------------------------------------------------------------------


class TestNumpyInput:
    def test_1d_array(self) -> None:
        d = Dygraph(np.array([1, 2, 3, 4, 5]))
        cfg = d.to_dict()
        assert cfg["format"] == "numeric"
        assert len(cfg["data"]) == 1
        assert cfg["data"][0] == [1, 2, 3, 4, 5]

    def test_2d_array(self) -> None:
        arr = np.array([[1, 10, 100], [2, 20, 200], [3, 30, 300]])
        d = Dygraph(arr)
        cfg = d.to_dict()
        assert len(cfg["data"]) == 3
        assert cfg["data"][0] == [1, 2, 3]
        assert cfg["data"][1] == [10, 20, 30]
        assert cfg["data"][2] == [100, 200, 300]

    def test_labels_auto_generated(self) -> None:
        d = Dygraph(np.arange(6).reshape(3, 2))
        assert d.to_dict()["attrs"]["labels"] == ["V0", "V1"]


# ---------------------------------------------------------------------------
# 2. to_html
# ---------------------------------------------------------------------------


class TestToHtml:
    def test_produces_valid_html(self) -> None:
        html = Dygraph(_df(), title="Test").to_html()
        assert "<!DOCTYPE html>" in html
        assert "<title>Test</title>" in html
        assert "new Dygraph" in html
        assert "cdnjs.cloudflare.com" in html

    def test_inline_js(self) -> None:
        html = Dygraph(_df()).to_html(cdn=False)
        assert "cdnjs.cloudflare.com" not in html
        # Should contain inlined JS
        assert "Dygraph" in html

    def test_custom_dimensions(self) -> None:
        html = Dygraph(_df()).to_html(height=500, width="80%")
        assert "height:500px" in html
        assert "width:80%" in html

    def test_default_title_from_chart(self) -> None:
        html = Dygraph(_df(), title="My Chart").to_html()
        assert "<title>My Chart</title>" in html

    def test_annotations_included(self) -> None:
        html = Dygraph(_df()).annotation("2020-01-03", "A").to_html()
        assert "setAnnotations" in html


# ---------------------------------------------------------------------------
# 3. Error bar helpers
# ---------------------------------------------------------------------------


class TestErrorBarHelpers:
    def test_make_error_bar_data(self) -> None:
        data = make_error_bar_data(
            x=[1, 2, 3], y=[10, 20, 30], error=[1, 2, 3]
        )
        assert data == {"x": [1, 2, 3], "value": [10, 20, 30], "error": [1, 2, 3]}

    def test_make_error_bar_data_custom_labels(self) -> None:
        data = make_error_bar_data(
            x=[1], y=[10], error=[1], labels=("Time", "Temp", "StdDev")
        )
        assert "Time" in data
        assert "Temp" in data
        assert "StdDev" in data

    def test_make_custom_bar_data(self) -> None:
        data = make_custom_bar_data(
            x=[1, 2], low=[8, 18], mid=[10, 20], high=[12, 22]
        )
        assert data == {"x": [1, 2], "low": [8, 18], "mid": [10, 20], "high": [12, 22]}


# ---------------------------------------------------------------------------
# 4. from_csv
# ---------------------------------------------------------------------------


class TestFromCsv:
    def test_from_csv_file(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("Date,A,B\n2024-01-01,1,2\n2024-01-02,3,4")
        d = Dygraph.from_csv(csv_file, title="From File")
        cfg = d.to_dict()
        assert cfg["format"] == "date"
        assert cfg["attrs"]["title"] == "From File"
        assert "A" in cfg["attrs"]["labels"]

    def test_from_csv_numeric(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "num.csv"
        csv_file.write_text("x,y\n1,10\n2,20\n3,30")
        d = Dygraph.from_csv(csv_file)
        assert d.to_dict()["format"] == "numeric"


# ---------------------------------------------------------------------------
# 5. update
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_update_options(self) -> None:
        d = Dygraph(_df()).update(options={"fill_graph": True})
        assert d.to_dict()["attrs"]["fillGraph"] is True

    def test_update_legend(self) -> None:
        d = Dygraph(_df()).update(legend=Legend(show="always"))
        assert d.to_dict()["attrs"]["legend"] == "always"

    def test_update_returns_self(self) -> None:
        d = Dygraph(_df())
        assert d.update(options={"stroke_width": 3}) is d

    def test_update_adds_annotations(self) -> None:
        d = Dygraph(_df()).update(annotations=[{"x": "2020-01-03", "text": "X"}])
        assert len(d.to_dict()["annotations"]) == 1


# ---------------------------------------------------------------------------
# 6. Plotter declarative
# ---------------------------------------------------------------------------


class TestPlotterDeclarative:
    def test_bar_chart_by_name(self) -> None:
        d = Dygraph(_df(), plotter="bar_chart")
        from pydygraphs.utils import JS

        assert isinstance(d.to_dict()["attrs"]["plotter"], JS)

    def test_candlestick_by_name(self) -> None:
        d = Dygraph(_df(), plotter="candlestick")
        from pydygraphs.utils import JS

        assert isinstance(d.to_dict()["attrs"]["plotter"], JS)

    def test_custom_js_plotter(self) -> None:
        d = Dygraph(_df(), plotter="function(e){}")
        from pydygraphs.utils import JS

        assert isinstance(d.to_dict()["attrs"]["plotter"], JS)


# ---------------------------------------------------------------------------
# 7. copy
# ---------------------------------------------------------------------------


class TestCopy:
    def test_copy_is_independent(self) -> None:
        original = Dygraph(_df(), title="Original")
        forked = original.copy()
        forked.options(fill_graph=True)

        assert original.to_dict()["attrs"].get("fillGraph") is not True
        assert forked.to_dict()["attrs"]["fillGraph"] is True

    def test_copy_preserves_data(self) -> None:
        original = Dygraph(_df(), title="Test")
        forked = original.copy()
        assert forked.to_dict()["data"] == original.to_dict()["data"]
        assert forked.to_dict()["attrs"]["title"] == "Test"


# ---------------------------------------------------------------------------
# 8. Mixed declarative + builder
# ---------------------------------------------------------------------------


class TestMixedUsage:
    def test_declarative_then_builder(self) -> None:
        d = Dygraph(
            _df(),
            title="Mixed",
            options=Options(fill_graph=True),
            series=[Series("temp", color="red")],
        ).annotation("2020-01-03", "A").range_selector(height=25)

        cfg = d.to_dict()
        assert cfg["attrs"]["fillGraph"] is True
        assert cfg["attrs"]["colors"][0] == "red"
        assert len(cfg["annotations"]) == 1
        assert cfg["attrs"]["showRangeSelector"] is True

    def test_builder_then_update(self) -> None:
        d = (
            Dygraph(_df(), title="Build")
            .options(fill_graph=True)
            .update(legend={"show": "always"})
        )
        cfg = d.to_dict()["attrs"]
        assert cfg["fillGraph"] is True
        assert cfg["legend"] == "always"

    def test_copy_then_modify(self) -> None:
        base = Dygraph(_df(), title="Base", options=Options(stroke_width=2))
        variant_a = base.copy().options(colors=["red"])
        variant_b = base.copy().options(colors=["blue"])

        assert variant_a.to_dict()["attrs"]["colors"] == ["red"]
        assert variant_b.to_dict()["attrs"]["colors"] == ["blue"]
        assert "colors" not in base.to_dict()["attrs"]
