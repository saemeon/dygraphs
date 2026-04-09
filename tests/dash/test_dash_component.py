"""Tests for Dash component generation and sync/stacked_bar utilities."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import Dygraph


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame({"y": [1, 2, 3, 4, 5]}, index=idx)


class TestDygraphToDash:
    def test_to_dash_returns_div(self) -> None:
        from dash import Dash, html

        app = Dash(__name__)
        dg = Dygraph(_df(), title="Test")
        component = dg.to_dash(app=app, component_id="tc")
        assert isinstance(component, html.Div)
        assert component.id == "tc"

    def test_to_dash_auto_id(self) -> None:
        from dash import Dash, html

        app = Dash(__name__)
        dg = Dygraph(_df())
        component = dg.to_dash(app=app)
        assert isinstance(component, html.Div)
        assert component.id.startswith("dygraph-")

    def test_to_dash_contains_store_and_graph(self) -> None:
        from dash import Dash, dcc

        app = Dash(__name__)
        dg = Dygraph(_df())
        component = dg.to_dash(app=app, component_id="x")
        children = component.children
        store = [c for c in children if isinstance(c, dcc.Store)]
        graphs = [c for c in children if isinstance(c, dcc.Graph)]
        assert len(store) == 2  # data store + opts store
        assert len(graphs) == 1  # hidden graph

    def test_to_dash_height_int(self) -> None:
        from dash import Dash

        app = Dash(__name__)
        dg = Dygraph(_df())
        component = dg.to_dash(app=app, component_id="h", height=500)
        assert isinstance(component, object)  # just verify no error

    def test_to_dash_no_modebar(self) -> None:
        from dash import Dash

        app = Dash(__name__)
        dg = Dygraph(_df())
        component = dg.to_dash(app=app, component_id="nm", modebar=False)
        assert component is not None

    def test_to_dash_without_app(self) -> None:
        dg = Dygraph(_df())
        component = dg.to_dash(component_id="no-app")
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


class TestStackedBar:
    def test_stacked_bar_returns_div(self) -> None:
        from dash import Dash, html

        app = Dash(__name__)
        component = __import__("dygraphs").stacked_bar(
            app, "sb", initial_data="Date,A,B\n2024-01-01,1,2\n2024-01-02,3,4"
        )
        assert isinstance(component, html.Div)


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
        j = d.to_json()
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
        assert "true, false)" in strategy.capture  # hide=true, debug=false

    def test_dygraph_strategy_no_hide(self) -> None:
        from dygraphs.dash.capture import dygraph_strategy

        try:
            strategy = dygraph_strategy(hide_range_selector=False)
        except ImportError:
            pytest.skip("dash-capture not installed")
        assert "false, false)" in strategy.capture  # hide=false, debug=false

    def test_dygraph_strategy_debug(self) -> None:
        from dygraphs.dash.capture import dygraph_strategy

        try:
            strategy = dygraph_strategy(debug=True)
        except ImportError:
            pytest.skip("dash-capture not installed")
        assert "true, true)" in strategy.capture  # hide=true, debug=true

    def test_modebar_uses_shared_js(self) -> None:
        """component.py's __dyCap_ embeds the same shared JS constant."""
        from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS
        from dygraphs.dash.component import _build_render_js

        js = _build_render_js("g", "g-container", "g-chart", 320, modebar=True)
        assert MULTI_CANVAS_CAPTURE_JS in js
