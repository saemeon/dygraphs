"""Tests for the Shiny adapter (unit tests, no running Shiny server)."""

from __future__ import annotations

import pandas as pd
import pytest

from pydygraphs import Dygraph

_shiny_available = True
try:
    import shiny  # noqa: F401
except ImportError:
    _shiny_available = False

skip_no_shiny = pytest.mark.skipif(not _shiny_available, reason="shiny not installed")


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"y": range(5)},
        index=pd.date_range("2020-01-01", periods=5, freq="D"),
    )


class TestShinyComponent:
    @skip_no_shiny
    def test_dygraph_ui_returns_taglist(self) -> None:
        from pydygraphs.shiny.component import dygraph_ui

        result = dygraph_ui("test-chart", height="300px")
        assert result is not None
        html_str = str(result)
        assert "test-chart" in html_str
        assert "dygraph" in html_str.lower()

    @skip_no_shiny
    def test_dygraph_ui_includes_cdn(self) -> None:
        from pydygraphs.shiny.component import dygraph_ui

        result = dygraph_ui("chart1")
        html_str = str(result)
        assert "cdnjs.cloudflare.com" in html_str

    @skip_no_shiny
    def test_dygraph_ui_includes_handler(self) -> None:
        from pydygraphs.shiny.component import dygraph_ui

        result = dygraph_ui("mychart")
        html_str = str(result)
        assert "pydygraphs_mychart" in html_str
        assert "addCustomMessageHandler" in html_str

    @skip_no_shiny
    def test_to_shiny_returns_ui(self) -> None:
        d = Dygraph(_df(), title="Test")
        result = d.to_shiny("my-element")
        assert result is not None

    def test_serialise_handles_js(self) -> None:
        from pydygraphs.shiny.component import _serialise
        from pydygraphs.utils import JS

        result = _serialise({"cb": JS("function(){}")})
        assert result["cb"] == "__JS__:function(){}:__JS__"

    def test_serialise_nested(self) -> None:
        from pydygraphs.shiny.component import _serialise

        result = _serialise({"a": [1, {"b": 2}]})
        assert result == {"a": [1, {"b": 2}]}
