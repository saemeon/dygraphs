"""Tests for declarative API — dataclasses and dict inputs produce same output as builder."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import (
    Annotation,
    Axis,
    Callbacks,
    Dygraph,
    Event,
    Highlight,
    Legend,
    Limit,
    Options,
    RangeSelector,
    Roller,
    Series,
    Shading,
)


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame(
        {"temp": [10, 12, 11, 14, 13], "rain": [5, 3, 7, 2, 6]}, index=idx
    )


# ---------------------------------------------------------------------------
# Dataclass construction
# ---------------------------------------------------------------------------


class TestDeclarativeDataclasses:
    def test_options_dataclass(self) -> None:
        d = Dygraph(_df(), options=Options(fill_graph=True, draw_points=True))
        cfg = d.to_dict()["attrs"]
        assert cfg["fillGraph"] is True
        assert cfg["drawPoints"] is True

    def test_axis_dataclass(self) -> None:
        d = Dygraph(_df(), axes=[Axis("y", label="Temp", value_range=(0, 20))])
        cfg = d.to_dict()["attrs"]
        assert cfg["ylabel"] == "Temp"
        assert cfg["axes"]["y"]["valueRange"] == [0, 20]

    def test_axes_dict_of_dataclasses(self) -> None:
        d = Dygraph(
            _df(),
            axes={
                "y": Axis("y", label="Left"),
                "y2": Axis("y2", label="Right"),
            },
        )
        cfg = d.to_dict()["attrs"]
        assert cfg["ylabel"] == "Left"
        assert cfg["y2label"] == "Right"

    def test_series_dataclass(self) -> None:
        d = Dygraph(_df(), series=[Series("temp", color="red", stroke_width=2)])
        cfg = d.to_dict()
        assert cfg["attrs"]["colors"][0] == "red"
        assert cfg["attrs"]["series"]["temp"]["strokeWidth"] == 2

    def test_legend_dataclass(self) -> None:
        d = Dygraph(_df(), legend=Legend(show="always", width=400))
        cfg = d.to_dict()["attrs"]
        assert cfg["legend"] == "always"
        assert cfg["labelsDivWidth"] == 400

    def test_highlight_dataclass(self) -> None:
        d = Dygraph(_df(), highlight=Highlight(circle_size=8))
        assert d.to_dict()["attrs"]["highlightCircleSize"] == 8

    def test_annotation_dataclass(self) -> None:
        d = Dygraph(
            _df(), annotations=[Annotation(x="2020-01-03", text="A", tooltip="Hi")]
        )
        ann = d.to_dict()["annotations"]
        assert len(ann) == 1
        assert ann[0]["shortText"] == "A"

    def test_shading_dataclass(self) -> None:
        d = Dygraph(_df(), shadings=[Shading(from_="2020-01-01", to="2020-01-03")])
        assert len(d.to_dict()["shadings"]) == 1

    def test_event_dataclass(self) -> None:
        d = Dygraph(_df(), events=[Event(x="2020-01-03", label="E")])
        assert d.to_dict()["events"][0]["label"] == "E"

    def test_limit_dataclass(self) -> None:
        d = Dygraph(_df(), limits=[Limit(value=12.0, label="Max")])
        ev = d.to_dict()["events"][0]
        assert ev["pos"] == 12.0
        assert ev["axis"] == "y"

    def test_range_selector_dataclass(self) -> None:
        d = Dygraph(_df(), range_selector=RangeSelector(height=25))
        assert d.to_dict()["attrs"]["rangeSelectorHeight"] == 25
        assert d.to_dict()["attrs"]["showRangeSelector"] is True

    def test_roller_dataclass(self) -> None:
        d = Dygraph(_df(), roller=Roller(roll_period=7))
        assert d.to_dict()["attrs"]["rollPeriod"] == 7

    def test_callbacks_dataclass(self) -> None:
        from dygraphs import JS

        d = Dygraph(_df(), callbacks=Callbacks(click="function(){}"))
        cb = d.to_dict()["attrs"]["clickCallback"]
        assert isinstance(cb, JS)


# ---------------------------------------------------------------------------
# Dict inputs
# ---------------------------------------------------------------------------


class TestDeclarativeDict:
    def test_options_dict(self) -> None:
        d = Dygraph(_df(), options={"fill_graph": True, "stroke_width": 3})
        cfg = d.to_dict()["attrs"]
        assert cfg["fillGraph"] is True
        assert cfg["strokeWidth"] == 3

    def test_axis_dict(self) -> None:
        d = Dygraph(_df(), axes=[{"name": "y", "label": "Value"}])
        assert d.to_dict()["attrs"]["ylabel"] == "Value"

    def test_series_dict(self) -> None:
        d = Dygraph(_df(), series=[{"name": "temp", "color": "blue"}])
        assert d.to_dict()["attrs"]["colors"][0] == "blue"

    def test_legend_dict(self) -> None:
        d = Dygraph(_df(), legend={"show": "follow"})
        assert d.to_dict()["attrs"]["legend"] == "follow"

    def test_annotation_dict(self) -> None:
        d = Dygraph(_df(), annotations=[{"x": "2020-01-02", "text": "B"}])
        assert d.to_dict()["annotations"][0]["shortText"] == "B"

    def test_shading_dict(self) -> None:
        d = Dygraph(_df(), shadings=[{"from_": "2020-01-01", "to": "2020-01-02"}])
        assert len(d.to_dict()["shadings"]) == 1

    def test_event_dict(self) -> None:
        d = Dygraph(_df(), events=[{"x": "2020-01-03", "label": "Evt"}])
        assert d.to_dict()["events"][0]["label"] == "Evt"

    def test_limit_dict(self) -> None:
        d = Dygraph(_df(), limits=[{"value": 10.0}])
        assert d.to_dict()["events"][0]["pos"] == 10.0

    def test_range_selector_dict(self) -> None:
        d = Dygraph(_df(), range_selector={"height": 50})
        assert d.to_dict()["attrs"]["rangeSelectorHeight"] == 50

    def test_callbacks_dict(self) -> None:
        d = Dygraph(_df(), callbacks={"click": "function(){}"})
        from dygraphs import JS

        assert isinstance(d.to_dict()["attrs"]["clickCallback"], JS)


# ---------------------------------------------------------------------------
# Mixed inputs
# ---------------------------------------------------------------------------


class TestDeclarativeMixed:
    def test_mixed_series(self) -> None:
        d = Dygraph(
            _df(),
            series=[
                Series("temp", color="red"),
                {"name": "rain", "color": "blue"},
            ],
        )
        colors = d.to_dict()["attrs"]["colors"]
        assert colors[0] == "red"
        assert colors[1] == "blue"

    def test_mixed_axes(self) -> None:
        d = Dygraph(
            _df(),
            axes={
                "y": Axis("y", label="Left"),
                "y2": {"name": "y2", "label": "Right"},
            },
        )
        cfg = d.to_dict()["attrs"]
        assert cfg["ylabel"] == "Left"
        assert cfg["y2label"] == "Right"


# ---------------------------------------------------------------------------
# Equivalence: declarative == builder
# ---------------------------------------------------------------------------


class TestEquivalence:
    def test_full_declarative_equals_builder(self) -> None:
        df = _df()

        declarative = Dygraph(
            df,
            title="Test",
            options=Options(fill_graph=True, draw_points=True, stroke_width=2),
            axes=[Axis("y", label="Temp", value_range=(0, 20))],
            series=[Series("temp", color="red")],
            legend=Legend(show="always"),
            highlight=Highlight(circle_size=5),
            range_selector=RangeSelector(height=30),
            roller=Roller(roll_period=3),
        )

        builder = (
            Dygraph(df, title="Test")
            .options(fill_graph=True, draw_points=True, stroke_width=2)
            .axis("y", label="Temp", value_range=(0, 20))
            .series("temp", color="red")
            .legend(show="always")
            .highlight(circle_size=5)
            .range_selector(height=30)
            .roller(roll_period=3)
        )

        assert declarative.to_dict() == builder.to_dict()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_invalid_type_raises(self) -> None:
        from dygraphs.declarative import _to_kwargs

        with pytest.raises(TypeError, match="Expected"):
            _to_kwargs(42)

    def test_none_values_filtered(self) -> None:
        """Dataclass fields with None are not passed to builder (uses builder defaults)."""
        d = Dygraph(_df(), series=[Series("temp")])
        # Should work without error — only name is passed, rest uses defaults
        assert "temp" in d.to_dict()["attrs"]["labels"]
