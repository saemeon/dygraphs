"""Tests for highlight — ports R test-highlight.R + extensions."""

from __future__ import annotations

import pandas as pd

from pydygraphs import Dygraph


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1]}, index=idx)


class TestHighlight:
    """Port of R ``context("dyHighlight")``."""

    def test_highlight_options(self) -> None:
        d = Dygraph(_df()).highlight(
            circle_size=5,
            series_background_alpha=0.2,
            hide_on_mouse_out=False,
        )
        cfg = d.to_dict()
        assert cfg["attrs"]["highlightCircleSize"] == 5
        assert cfg["attrs"]["highlightSeriesBackgroundAlpha"] == 0.2
        assert cfg["attrs"]["hideOverlayOnMouseOut"] is False

    def test_highlight_series_opts(self) -> None:
        d = Dygraph(_df()).highlight(series_opts={"strokeWidth": 3})
        cfg = d.to_dict()
        assert cfg["attrs"]["highlightSeriesOpts"]["strokeWidth"] == 3
