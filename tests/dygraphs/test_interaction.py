"""Tests for interaction features — ports R test-range-selector.R, test-roller.R, test-callbacks.R."""

from __future__ import annotations

import pandas as pd

from dygraphs import JS, Dygraph


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"y": range(10)},
        index=pd.date_range("2020-01-01", periods=10, freq="D"),
    )


class TestRangeSelector:
    """Port of R ``context("dyRangeSelector")``."""

    def test_range_selector_enabled(self) -> None:
        d = Dygraph(_df()).range_selector()
        assert d.to_dict()["attrs"]["showRangeSelector"] is True

    def test_range_selector_height(self) -> None:
        d = Dygraph(_df()).range_selector(height=20)
        assert d.to_dict()["attrs"]["rangeSelectorHeight"] == 20

    def test_range_selector_date_window(self) -> None:
        d = Dygraph(_df()).range_selector(date_window=("2020-01-03", "2020-01-08"))
        dw = d.to_dict()["attrs"]["dateWindow"]
        assert len(dw) == 2
        assert "2020-01-03" in dw[0]

    def test_range_selector_colors(self) -> None:
        d = Dygraph(_df()).range_selector(fill_color="red", stroke_color="blue")
        cfg = d.to_dict()["attrs"]
        assert cfg["rangeSelectorPlotFillColor"] == "red"
        assert cfg["rangeSelectorPlotStrokeColor"] == "blue"


class TestRoller:
    """Port of R ``context("dyRoller")``."""

    def test_roller_creation(self) -> None:
        d = Dygraph(_df()).roller(roll_period=5)
        cfg = d.to_dict()["attrs"]
        assert cfg["showRoller"] is True
        assert cfg["rollPeriod"] == 5


class TestCallbacks:
    """Port of R ``context("dyCallbacks")``."""

    def test_callback_creation(self) -> None:
        d = Dygraph(_df()).callbacks(click="function(e, x, points) {}")
        click_cb = d.to_dict()["attrs"]["clickCallback"]
        assert isinstance(click_cb, JS)
        assert "function" in click_cb.code

    def test_multiple_callbacks(self) -> None:
        d = Dygraph(_df()).callbacks(
            click="function(e){}",
            zoom="function(min, max, yRanges){}",
            highlight="function(e, x, pts, row){}",
        )
        cfg = d.to_dict()["attrs"]
        assert isinstance(cfg["clickCallback"], JS)
        assert isinstance(cfg["zoomCallback"], JS)
        assert isinstance(cfg["highlightCallback"], JS)
