"""Tests for the dygraphs Dash store-id convention and DygraphChart layout.

The chart's identity is its ``dcc.Store``, whose id equals the
user-facing ``id``. The container div sits next to it at
``{id}-container``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("dash")


class TestDygraphChartLayout:
    """DygraphChart emits the two-sibling tree and preserves id conventions."""

    @pytest.fixture
    def chart(self):  # noqa: ANN201
        import pandas as pd

        from dygraphs import Dygraph
        from dygraphs.dash import DygraphChart

        df = pd.DataFrame(
            {"y": [1, 2, 3]},
            index=pd.date_range("2024-01-01", periods=3),
        )
        return DygraphChart(figure=Dygraph(df), id="my-chart")

    def test_cid_equals_store_id(self, chart) -> None:  # noqa: ANN001
        # chart.cid exposes the inner Store's id. (We don't expose
        # .id because Dash's layout validation walks all components'
        # .id to detect duplicates — a proxied id would trip it.)
        assert chart.cid == "my-chart"

    def test_set_random_id_resolves_to_inner(self, chart) -> None:  # noqa: ANN001
        # Callback resolution path: Output(chart, "data") ends up
        # calling _set_random_id, which walks to the inner Store.
        assert chart._set_random_id() == "my-chart"

    def test_layout_contains_store_and_container(self, chart) -> None:  # noqa: ANN001
        ids = {
            c.id for c in chart.children if hasattr(c, "id") and c.id is not None
        }
        assert ids == {"my-chart", "my-chart-container"}

    def test_outer_div_has_no_id(self, chart) -> None:  # noqa: ANN001
        # ComponentWrapper's _set_random_id override deliberately does
        # NOT set an id on the outer div (prevents DuplicateIdError
        # when inner's id is also proxied).
        pj = chart.to_plotly_json()
        assert "id" not in pj["props"]

    def test_isinstance_spoof_reports_dcc_store(self, chart) -> None:  # noqa: ANN001
        # dash-wrap's __class__ property makes isinstance report the
        # inner component's type. Honest docs say so; users shouldn't
        # be surprised.
        from dash import dcc, html

        assert isinstance(chart, dcc.Store)
        # And the wrapper is still a real html.Div at the type level —
        # Dash's serialiser uses type(chart), not __class__, for the
        # DOM emission.
        assert isinstance(chart, html.Div)


class TestEmptyPlaceholder:
    """``DygraphChart(None, id=...)`` is a valid empty placeholder.

    The store holds ``data=None``; the clientside renderer
    early-returns on falsy config (``dash_render.js`` ``if (!config)
    return;``), so the chart is a no-op until a callback pushes real
    data.
    """

    def test_empty_chart_has_none_data(self) -> None:
        from dygraphs.dash import DygraphChart

        chart = DygraphChart(None, id="empty")
        primary = next(c for c in chart.children if c.id == "empty")
        assert primary.data is None

    def test_empty_chart_has_store_and_container(self) -> None:
        from dygraphs.dash import DygraphChart

        chart = DygraphChart(None, id="empty")
        ids = {c.id for c in chart.children if hasattr(c, "id") and c.id}
        assert ids == {"empty", "empty-container"}

    def test_empty_chart_is_still_dcc_store(self) -> None:
        from dash import dcc

        from dygraphs.dash import DygraphChart

        chart = DygraphChart(None, id="empty")
        assert isinstance(chart, dcc.Store)
        assert chart.cid == "empty"
