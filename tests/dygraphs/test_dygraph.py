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


class TestPeriodicityOverride:
    """``periodicity=`` constructor kwarg (R: ``dygraph(..., periodicity=)``)."""

    def test_autodetect_is_default(self) -> None:
        """Daily index without an override is auto-detected as ``"daily"``."""
        d = Dygraph(_sample_df())
        assert d.to_dict()["scale"] == "daily"

    def test_override_replaces_autodetected_scale(self) -> None:
        """Passing ``periodicity="monthly"`` on a daily index wins."""
        d = Dygraph(_sample_df(), periodicity="monthly")
        assert d.to_dict()["scale"] == "monthly"

    @pytest.mark.parametrize(
        "value",
        [
            "yearly",
            "quarterly",
            "monthly",
            "weekly",
            "daily",
            "hourly",
            "minute",
            "seconds",
            "milliseconds",
        ],
    )
    def test_all_valid_values_accepted(self, value: str) -> None:
        d = Dygraph(_sample_df(), periodicity=value)
        assert d.to_dict()["scale"] == value

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError, match="periodicity must be one of"):
            Dygraph(_sample_df(), periodicity="fortnightly")

    def test_invalid_value_error_lists_valid_options(self) -> None:
        """The error should name the actual offending value and list alternatives."""
        with pytest.raises(ValueError, match="'fortnightly'") as exc_info:
            Dygraph(_sample_df(), periodicity="fortnightly")
        msg = str(exc_info.value)
        for valid in ("yearly", "monthly", "daily", "milliseconds"):
            assert valid in msg

    def test_numeric_data_rejects_override(self) -> None:
        """Non-date data has no meaningful scale — raise clearly."""
        with pytest.raises(ValueError, match="only be set for date-formatted"):
            Dygraph(_sample_numeric_df(), periodicity="daily")

    def test_override_survives_to_html(self) -> None:
        """The overridden scale must reach the rendered HTML config."""
        html = Dygraph(_sample_df(), periodicity="yearly").to_html()
        # to_html serialises via to_json, which puts "scale":"yearly" in the
        # embedded config payload.
        assert '"scale": "yearly"' in html or '"scale":"yearly"' in html


class TestJupyterDisplay:
    """``_repr_html_`` and ``.show()`` for Jupyter / IPython integration."""

    def test_repr_html_returns_full_html(self) -> None:
        """Jupyter calls ``_repr_html_`` automatically when a chart is the
        last expression in a cell — the result must be a complete page."""
        d = Dygraph(_sample_df(), title="My Chart")
        html = d._repr_html_()
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "<title>My Chart</title>" in html

    def test_repr_html_matches_to_html(self) -> None:
        """``_repr_html_`` is just a thin alias for ``.to_html()``."""
        d = Dygraph(_sample_df())
        assert d._repr_html_() == d.to_html()

    def test_show_without_ipython_prints_hint(self, capsys) -> None:
        """When IPython is unavailable, ``.show()`` falls back gracefully."""
        import sys

        # Sabotage the import — leave existing IPython modules alone but
        # make a *new* import attempt fail.
        saved = sys.modules.get("IPython")
        sys.modules["IPython"] = None  # type: ignore[assignment]
        try:
            result = Dygraph(_sample_df()).show()
        finally:
            if saved is not None:
                sys.modules["IPython"] = saved
            else:
                sys.modules.pop("IPython", None)
        captured = capsys.readouterr()
        assert result is None
        assert "IPython" in captured.out


class TestCssRawString:
    """``.css()`` accepts both file paths and raw CSS strings."""

    def test_css_path_string(self, tmp_path) -> None:
        """A path-like string with no braces is read as a file (R-compatible)."""
        css_file = tmp_path / "style.css"
        css_file.write_text(".x { color: red }")
        d = Dygraph(_sample_df()).css(str(css_file))
        assert d.to_dict()["css"] == ".x { color: red }"

    def test_css_path_object(self, tmp_path) -> None:
        """An explicit Path always reads from disk."""
        css_file = tmp_path / "style.css"
        css_file.write_text(".y { color: blue }")
        d = Dygraph(_sample_df()).css(css_file)
        assert d.to_dict()["css"] == ".y { color: blue }"

    def test_css_raw_string(self) -> None:
        """A string with a brace is treated as raw CSS — no file lookup."""
        d = Dygraph(_sample_df()).css(".dygraph-title { color: tomato; }")
        assert d.to_dict()["css"] == ".dygraph-title { color: tomato; }"

    def test_css_raw_string_emitted_to_html(self) -> None:
        """Raw CSS reaches the rendered HTML payload."""
        html = Dygraph(_sample_df()).css(".my-cls { font-weight: bold }").to_html()
        assert ".my-cls { font-weight: bold }" in html


class TestSyncGroupAlias:
    """``.sync_group(name)`` is a builder alias for the constructor's
    ``group=`` kwarg — exposes the cross-chart sync feature through
    autocomplete and disambiguates from the unrelated ``.group([names])``
    method (which is the ``dyGroup`` port)."""

    def test_sync_group_method_sets_group(self) -> None:
        d = Dygraph(_sample_df()).sync_group("foo")
        assert d.to_dict()["group"] == "foo"

    def test_sync_group_equivalent_to_constructor_kwarg(self) -> None:
        a = Dygraph(_sample_df(), group="bar").to_dict()["group"]
        b = Dygraph(_sample_df()).sync_group("bar").to_dict()["group"]
        assert a == b == "bar"

    def test_sync_group_none_clears(self) -> None:
        d = Dygraph(_sample_df(), group="x").sync_group(None)
        assert d.to_dict()["group"] is None


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
