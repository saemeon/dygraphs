"""Tests for Dash component generation (DygraphChart, StackedBarChart)."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import Dygraph


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame({"y": [1, 2, 3, 4, 5]}, index=idx)


class TestDygraphChartConstruction:
    def test_returns_html_div(self) -> None:
        from dash import Dash, html

        from dygraphs.dash import DygraphChart

        Dash(__name__)
        dg = Dygraph(_df(), title="Test")
        component = DygraphChart(figure=dg, id="tc")
        # DygraphChart inherits from ComponentWrapper, which inherits
        # from html.Div — so the outer is a real Div.
        assert isinstance(component, html.Div)
        # The outer div has no id (dash-wrap convention: prevents
        # DuplicateIdError against the inner store). The chart's id
        # is exposed via .chart_id and matches the inner store's id.
        assert component.chart_id == "tc"

    def test_auto_id(self) -> None:
        from dash import Dash, html

        from dygraphs.dash import DygraphChart

        Dash(__name__)
        dg = Dygraph(_df())
        component = DygraphChart(figure=dg)
        assert isinstance(component, html.Div)
        assert component.chart_id.startswith("dygraph-")

    def test_contains_single_store_and_container(self) -> None:
        """Layout = 1 dcc.Store + 1 html.Div container, no hidden graph.

        The clientside callback writes back to the data store with
        ``allow_duplicate=True`` and returns ``no_update`` from JS, so
        there's no need for a hidden ``dcc.Graph`` sink.
        """
        from dash import Dash, dcc, html

        from dygraphs.dash import DygraphChart

        Dash(__name__)
        dg = Dygraph(_df())
        component = DygraphChart(figure=dg, id="x")
        children = component.children
        stores = [c for c in children if isinstance(c, dcc.Store)]
        graphs = [c for c in children if isinstance(c, dcc.Graph)]
        divs = [c for c in children if isinstance(c, html.Div)]
        assert len(stores) == 1  # chart data store
        assert len(graphs) == 0  # hidden graph dropped
        assert len(divs) == 1  # container div

    def test_height_int(self) -> None:
        from dash import Dash

        from dygraphs.dash import DygraphChart

        Dash(__name__)
        dg = Dygraph(_df())
        component = DygraphChart(figure=dg, id="h", height=500)
        assert isinstance(component, object)  # just verify no error

    def test_no_modebar(self) -> None:
        from dash import Dash

        from dygraphs.dash import DygraphChart

        Dash(__name__)
        dg = Dygraph(_df())
        component = DygraphChart(figure=dg, id="nm", modebar=False)
        assert component is not None

    def test_without_app(self) -> None:
        from dygraphs.dash import DygraphChart

        dg = Dygraph(_df())
        component = DygraphChart(figure=dg, id="no-app")
        assert component is not None


class TestGroupSync:
    def test_group_included_in_config(self) -> None:
        dg = Dygraph(_df(), group="my-sync-group")
        cfg = dg.to_dict()
        assert cfg["group"] == "my-sync-group"

    def test_group_none_by_default(self) -> None:
        dg = Dygraph(_df())
        cfg = dg.to_dict()
        assert cfg["group"] is None


class TestStackedBarChart:
    def test_returns_html_div(self) -> None:
        from dash import Dash, html

        from dygraphs.dash import StackedBarChart

        Dash(__name__)
        component = StackedBarChart(
            id="sb", initial_data="Date,A,B\n2024-01-01,1,2\n2024-01-02,3,4"
        )
        assert isinstance(component, html.Div)
        assert component.chart_id == "sb"


class TestToDict:
    def test_to_dict_structure(self) -> None:
        d = Dygraph(_df(), title="T").options(fill_graph=True)
        cfg = d.to_dict()
        assert "attrs" in cfg
        assert "data" in cfg
        assert "format" in cfg
        assert "annotations" in cfg
        assert "shadings" in cfg
        assert "events" in cfg
        assert "plugins" in cfg

    def test_to_json(self) -> None:
        d = Dygraph(_df()).callbacks(click="function(){}")
        j = d._to_json()
        assert "function(){}" in j
        assert "__JS__" not in j  # markers should be removed


class TestGroup:
    def test_group_basic(self) -> None:
        df = pd.DataFrame(
            {"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]},
            index=pd.date_range("2020-01-01", periods=3, freq="D"),
        )
        d = Dygraph(df).group(["a", "b"], color=["red", "blue"])
        cfg = d.to_dict()
        assert cfg["attrs"]["series"]["a"]["group"] == "a\x1fb"
        assert cfg["attrs"]["series"]["b"]["group"] == "a\x1fb"
        assert cfg["attrs"]["colors"][0] == "red"
        assert cfg["attrs"]["colors"][1] == "blue"

    def test_group_single_delegates_to_series(self) -> None:
        df = pd.DataFrame(
            {"a": [1, 2], "b": [3, 4]},
            index=pd.date_range("2020-01-01", periods=2, freq="D"),
        )
        d = Dygraph(df).group(["a"], color=["red"])
        cfg = d.to_dict()
        assert cfg["attrs"]["colors"][0] == "red"

    def test_group_not_found(self) -> None:
        df = pd.DataFrame({"a": [1]}, index=pd.date_range("2020-01-01", periods=1))
        with pytest.raises(ValueError, match="not found"):
            Dygraph(df).group(["a", "nonexistent"])


class TestCSS:
    def test_css_from_string(self, tmp_path) -> None:
        css_file = tmp_path / "test.css"
        css_file.write_text(".dygraph-title { color: red; }")
        d = Dygraph(_df()).css(css_file)
        assert ".dygraph-title" in d.to_dict()["css"]


class TestCapture:
    def test_dygraph_strategy_basic(self) -> None:
        """dygraph_strategy() returns a CaptureStrategy with the shared JS."""
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS, dygraph_strategy

        try:
            strategy = dygraph_strategy(hide_range_selector=True)
        except ImportError:
            pytest.skip("dash-capture not installed")
        assert strategy.format == "png"
        # preprocess is None — hide/restore is internal to the shared IIFE
        assert strategy.preprocess is None
        assert MULTI_CANVAS_CAPTURE_JS in strategy.capture
        # Selectors array baked into the call site, debug=false.
        assert ".dygraph-rangesel-fgcanvas" in strategy.capture
        assert ".dygraph-rangesel-bgcanvas" in strategy.capture
        assert ".dygraph-rangesel-zoomhandle" in strategy.capture
        assert "], false)" in strategy.capture  # closes selectors array, debug=false

    def test_dygraph_strategy_no_hide(self) -> None:
        from dygraphs.dash.capture import dygraph_strategy

        try:
            strategy = dygraph_strategy(hide_range_selector=False)
        except ImportError:
            pytest.skip("dash-capture not installed")
        # Empty selectors array, debug=false.
        assert "[], false)" in strategy.capture
        assert ".dygraph-rangesel" not in strategy.capture.split(
            "})"
        )[1]  # only inside the inlined IIFE body, not the args

    def test_dygraph_strategy_debug(self) -> None:
        from dygraphs.dash.capture import dygraph_strategy

        try:
            strategy = dygraph_strategy(debug=True)
        except ImportError:
            pytest.skip("dash-capture not installed")
        # Selectors array, debug=true.
        assert "], true)" in strategy.capture
