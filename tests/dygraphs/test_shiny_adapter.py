"""Tests for the Shiny adapter (unit tests, no running Shiny server)."""

from __future__ import annotations

import pytest

_shiny_available = True
try:
    import shiny  # noqa: F401
except ImportError:
    _shiny_available = False

skip_no_shiny = pytest.mark.skipif(not _shiny_available, reason="shiny not installed")


class TestShinyComponent:
    @skip_no_shiny
    def test_dygraph_ui_returns_taglist(self) -> None:
        from dygraphs.shiny.component import dygraph_ui

        result = dygraph_ui("test-chart", height="300px")
        assert result is not None
        html_str = str(result)
        assert "test-chart" in html_str
        assert "dygraph" in html_str.lower()

    @skip_no_shiny
    def test_dygraph_ui_includes_cdn(self) -> None:
        from dygraphs.shiny.component import dygraph_ui

        result = dygraph_ui("chart1")
        html_str = str(result)
        assert "cdnjs.cloudflare.com" in html_str

    @skip_no_shiny
    def test_dygraph_ui_includes_handler(self) -> None:
        from dygraphs.shiny.component import dygraph_ui

        result = dygraph_ui("mychart")
        html_str = str(result)
        assert "dygraphs_mychart" in html_str
        assert "addCustomMessageHandler" in html_str

    @skip_no_shiny
    def test_dygraph_ui_with_size(self) -> None:
        from dygraphs.shiny.component import dygraph_ui

        result = dygraph_ui("my-element", height="500px", width="80%")
        assert result is not None

    def test_serialise_handles_js(self) -> None:
        from dygraphs.utils import JS, serialise_js

        result = serialise_js({"cb": JS("function(){}")})
        assert result["cb"] == "__JS__:function(){}:__JS__"

    def test_serialise_nested(self) -> None:
        from dygraphs.utils import serialise_js

        result = serialise_js({"a": [1, {"b": 2}]})
        assert result == {"a": [1, {"b": 2}]}
