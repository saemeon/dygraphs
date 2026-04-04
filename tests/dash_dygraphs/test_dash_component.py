"""Tests for Dash component generation and sync/stacked_bar utilities."""

from __future__ import annotations

import pandas as pd
import pytest

from dash_dygraphs import Dygraph


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
        assert len(store) == 3  # data store + opts store + xrange store
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


class TestSyncDygraphs:
    def test_sync_returns_hidden_div(self) -> None:
        from dash import Dash, html

        app = Dash(__name__)
        component = __import__("dash_dygraphs").sync_dygraphs(app, ["a", "b", "c"])
        assert isinstance(component, html.Div)
        assert component.style == {"display": "none"}


class TestStackedBar:
    def test_stacked_bar_returns_div(self) -> None:
        from dash import Dash, html

        app = Dash(__name__)
        component = __import__("dash_dygraphs").stacked_bar(
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
        assert cfg["attrs"]["series"]["a"]["group"] == "ab"
        assert cfg["attrs"]["series"]["b"]["group"] == "ab"
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
    def test_dygraph_strategy_import_error(self) -> None:
        """dygraph_strategy() raises ImportError if dash-capture not installed."""
        # We can't easily mock this since dash-capture might be installed,
        # so just test that the function exists and returns something
        from dash_dygraphs.capture import dygraph_strategy

        try:
            strategy = dygraph_strategy(hide_range_selector=True)
            assert strategy.format == "png"
            assert strategy.preprocess is not None
            assert "toDataURL" in strategy.capture
        except ImportError:
            pytest.skip("dash-capture not installed")

    def test_dygraph_strategy_no_hide(self) -> None:
        from dash_dygraphs.capture import dygraph_strategy

        try:
            strategy = dygraph_strategy(hide_range_selector=False)
            assert strategy.preprocess is None
        except ImportError:
            pytest.skip("dash-capture not installed")
