"""Tests for legend — ports R test-legend.R + extensions."""

from __future__ import annotations

import pandas as pd

from dygraphs import Dygraph


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"y": range(5)},
        index=pd.date_range("2020-01-01", periods=5, freq="D"),
    )


class TestLegend:
    """Port of R ``context("dyLegend")``."""

    def test_legend_show_always(self) -> None:
        d = Dygraph(_df()).legend(show="always", hide_on_mouse_out=True)
        cfg = d.to_dict()
        assert cfg["attrs"]["legend"] == "always"
        assert cfg["attrs"]["hideOverlayOnMouseOut"] is True

    def test_legend_never(self) -> None:
        d = Dygraph(_df()).legend(show="never")
        cfg = d.to_dict()
        assert cfg["attrs"]["showLabelsOnHighlight"] is False

    def test_legend_width(self) -> None:
        d = Dygraph(_df()).legend(width=400)
        assert d.to_dict()["attrs"]["labelsDivWidth"] == 400

    def test_legend_follow(self) -> None:
        d = Dygraph(_df()).legend(show="follow")
        assert d.to_dict()["attrs"]["legend"] == "follow"
