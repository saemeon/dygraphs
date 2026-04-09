"""Tests for the dygraphs.dash.outputs helper module.

Two layers of coverage:

1. Behavioural — :func:`data` and :func:`opts` return ``Output``
   objects with the expected component id and property.
2. Drift guard — the id format used by the helpers
   (``f"{cid}-store"``, ``f"{cid}-opts"``) must match the format used
   inside ``component.py`` when the chart is built. The two are
   asserted to live in the same source so a future rename of one
   side has to touch the other.
"""

from __future__ import annotations

from pathlib import Path

import pytest

dash = pytest.importorskip("dash")

from dygraphs.dash import data, opts  # noqa: E402


class TestDataHelper:
    def test_returns_output_instance(self) -> None:
        from dash.dependencies import Output

        out = data("my-chart")
        assert isinstance(out, Output)

    def test_component_id_is_store_suffix(self) -> None:
        out = data("my-chart")
        assert out.component_id == "my-chart-store"

    def test_property_is_data(self) -> None:
        out = data("my-chart")
        assert out.component_property == "data"

    def test_handles_uuid_style_ids(self) -> None:
        out = data("dygraph-abc12345")
        assert out.component_id == "dygraph-abc12345-store"


class TestOptsHelper:
    def test_returns_output_instance(self) -> None:
        from dash.dependencies import Output

        out = opts("my-chart")
        assert isinstance(out, Output)

    def test_component_id_is_opts_suffix(self) -> None:
        out = opts("my-chart")
        assert out.component_id == "my-chart-opts"

    def test_property_is_data(self) -> None:
        out = opts("my-chart")
        assert out.component_property == "data"


class TestHelperMatchesComponentSource:
    """Lock in that the helper id format matches the actual chart layout.

    If someone renames ``{cid}-store`` to ``{cid}-data`` inside
    ``component.py`` and forgets to update the helper, callbacks built
    via ``data(cid)`` will silently target a non-existent store. Catch
    that here.
    """

    @pytest.fixture
    def component_source(self) -> str:
        return (
            Path(__file__).parent.parent.parent
            / "src"
            / "dygraphs"
            / "dash"
            / "component.py"
        ).read_text()

    def test_store_id_format_in_component(self, component_source: str) -> None:
        assert 'store_id = f"{cid}-store"' in component_source

    def test_opts_id_format_in_component(self, component_source: str) -> None:
        assert 'opts_store_id = f"{cid}-opts"' in component_source


class TestReExportFromDashSubpackage:
    def test_data_importable_from_dygraphs_dash(self) -> None:
        from dygraphs.dash import data as data_export

        assert data_export is data

    def test_opts_importable_from_dygraphs_dash(self) -> None:
        from dygraphs.dash import opts as opts_export

        assert opts_export is opts
