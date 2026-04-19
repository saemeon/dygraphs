"""Tests for the dygraphs Dash store-id convention.

Verifies that the data store shares the chart's ``id`` so that
``Output("my-chart", "data")`` targets it directly, and the opts
store uses the ``{id}-opts`` suffix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

dash = pytest.importorskip("dash")


class TestStoreIdConvention:
    """The data store id must equal the component_id (no suffix)."""

    @pytest.fixture
    def component_source(self) -> str:
        return (
            Path(__file__).parent.parent.parent
            / "src"
            / "dygraphs"
            / "dash"
            / "component.py"
        ).read_text()

    def test_data_store_id_equals_cid(self, component_source: str) -> None:
        assert "store_id = cid" in component_source

    def test_opts_store_id_has_opts_suffix(self, component_source: str) -> None:
        assert 'opts_store_id = f"{cid}-opts"' in component_source


class TestDyGraphLayout:
    """DyGraph wrapper produces the expected layout structure."""

    def test_data_store_has_chart_id(self) -> None:
        import pandas as pd

        from dygraphs import Dygraph
        from dygraphs.dash import DyGraph

        df = pd.DataFrame(
            {"y": [1, 2, 3]},
            index=pd.date_range("2024-01-01", periods=3),
        )
        comp = DyGraph(figure=Dygraph(df), id="my-chart")

        # The component's id should be the chart id
        assert comp.id == "my-chart"

        # The underlying layout should contain a store with id="my-chart"
        store_ids = [
            c.id for c in comp.children if hasattr(c, "id") and c.id is not None
        ]
        assert "my-chart" in store_ids
        assert "my-chart-opts" in store_ids

    def test_wrapper_div_has_derived_id(self) -> None:
        import pandas as pd

        from dygraphs import Dygraph
        from dygraphs.dash import DyGraph

        df = pd.DataFrame(
            {"y": [1, 2, 3]},
            index=pd.date_range("2024-01-01", periods=3),
        )
        comp = DyGraph(figure=Dygraph(df), id="my-chart")

        # The wrapper div id should NOT be "my-chart" (that's the store)
        pj = comp.to_plotly_json()
        assert pj["props"]["id"] == "my-chart-wrap"
