"""Tests for the dygraphs Dash store-id convention and DygraphChart layout.

The primary identity of a ``DygraphChart`` is its data ``dcc.Store``,
whose id equals the user-facing ``id``. The opts store is a sibling
at ``{id}-opts``; the container div is at ``{id}-container``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("dash")


class TestDygraphChartLayout:
    """DygraphChart emits the three-sibling tree and preserves id conventions."""

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

    def test_cid_equals_primary_store_id(self, chart) -> None:  # noqa: ANN001
        # chart.cid exposes the inner Store's id. (We don't expose
        # .id because Dash's layout validation walks all components'
        # .id to detect duplicates — a proxied id would trip it.)
        assert chart.cid == "my-chart"

    def test_set_random_id_resolves_to_inner(self, chart) -> None:  # noqa: ANN001
        # Callback resolution path: Output(chart, "data") ends up
        # calling _set_random_id, which walks to the inner Store.
        assert chart._set_random_id() == "my-chart"

    def test_layout_contains_primary_and_opts_stores(self, chart) -> None:  # noqa: ANN001
        store_ids = [
            c.id for c in chart.children if hasattr(c, "id") and c.id is not None
        ]
        assert "my-chart" in store_ids
        assert "my-chart-opts" in store_ids
        assert "my-chart-container" in store_ids

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

    def test_opts_property_returns_opts_store(self, chart) -> None:  # noqa: ANN001
        from dash import dcc

        assert isinstance(chart.opts, dcc.Store)
        assert chart.opts.id == "my-chart-opts"

    def test_opts_via_string_id_matches_property(self, chart) -> None:  # noqa: ANN001
        # Both ways of addressing the opts store should reach the
        # same component — documented equivalence.
        assert chart.opts.id == f"{chart.cid}-opts"


class TestEmptyPlaceholder:
    """``DygraphChart(None, id=...)`` is a valid empty placeholder.

    The primary store holds ``data=None``; the clientside renderer
    early-returns on falsy config (``dash_render.js`` line 403), so
    the chart is a no-op until a callback pushes real data.
    """

    def test_empty_chart_has_none_data(self) -> None:
        from dygraphs.dash import DygraphChart

        chart = DygraphChart(None, id="empty")
        primary = next(c for c in chart.children if c.id == "empty")
        assert primary.data is None

    def test_empty_chart_still_has_opts_and_container(self) -> None:
        from dygraphs.dash import DygraphChart

        chart = DygraphChart(None, id="empty")
        ids = {c.id for c in chart.children if hasattr(c, "id") and c.id}
        assert ids == {"empty", "empty-opts", "empty-container"}

    def test_empty_chart_is_still_dcc_store(self) -> None:
        from dash import dcc

        from dygraphs.dash import DygraphChart

        chart = DygraphChart(None, id="empty")
        assert isinstance(chart, dcc.Store)
        assert chart.cid == "empty"


class TestDygraphToDashAlias:
    """``dygraph_to_dash`` is a thin functional wrapper over DygraphChart."""

    def test_returns_dygraphchart_instance(self) -> None:
        import pandas as pd

        from dygraphs import Dygraph
        from dygraphs.dash import DygraphChart, dygraph_to_dash

        df = pd.DataFrame(
            {"y": [1, 2, 3]},
            index=pd.date_range("2024-01-01", periods=3),
        )
        comp = dygraph_to_dash(Dygraph(df), component_id="fn-chart")
        assert isinstance(comp, DygraphChart)
        assert comp.cid == "fn-chart"
