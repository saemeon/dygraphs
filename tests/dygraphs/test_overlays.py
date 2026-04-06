"""Tests for overlays — ports R test-event.R, test-shading.R + extensions."""

from __future__ import annotations

import pandas as pd
import pytest

from dygraphs import Dygraph


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    return pd.DataFrame({"y": range(10)}, index=idx)


class TestShading:
    """Port of R ``context("dyShading")``."""

    def test_shading_creation(self) -> None:
        d = (
            Dygraph(_df())
            .shading("2020-01-01", "2020-01-03")
            .shading("2020-01-05", "2020-01-07")
        )
        cfg = d.to_dict()
        assert len(cfg["shadings"]) == 2
        assert len(cfg["shadings"][0]) == 4  # from, to, color, axis
        assert len(cfg["shadings"][1]) == 4

    def test_shading_defaults(self) -> None:
        d = Dygraph(_df()).shading("2020-01-01", "2020-01-03")
        s = d.to_dict()["shadings"][0]
        assert s["color"] == "#EFEFEF"
        assert s["axis"] == "x"

    def test_shading_y_axis(self) -> None:
        d = Dygraph({"x": [1, 2, 3], "y": [10, 20, 30]}).shading(15, 25, axis="y")
        s = d.to_dict()["shadings"][0]
        assert s["from"] == 15
        assert s["to"] == 25
        assert s["axis"] == "y"


class TestEvent:
    """Port of R ``context("dyEvent")``."""

    def test_event_creation(self) -> None:
        d = (
            Dygraph(_df())
            .event("2020-01-03", "Event A", label_loc="bottom")
            .event("2020-01-07", "Event B", label_loc="bottom")
        )
        cfg = d.to_dict()
        assert len(cfg["events"]) == 2
        assert cfg["events"][0]["label"] == "Event A"
        assert cfg["events"][1]["label"] == "Event B"

    def test_event_defaults(self) -> None:
        d = Dygraph(_df()).event("2020-01-03", "E")
        e = d.to_dict()["events"][0]
        assert e["color"] == "black"
        assert e["strokePattern"] == [7, 3]  # dashed
        assert e["axis"] == "x"


class TestLimit:
    def test_limit_creation(self) -> None:
        d = Dygraph(_df()).limit(5.0, "Max", color="blue", stroke_pattern="solid")
        e = d.to_dict()["events"][0]
        assert e["pos"] == 5.0
        assert e["label"] == "Max"
        assert e["color"] == "blue"
        assert e["axis"] == "y"
        assert e["strokePattern"] == [1, 0]

    def test_limit_label_loc(self) -> None:
        d = Dygraph(_df()).limit(5.0, "Max", label_loc="right")
        assert d.to_dict()["events"][0]["labelLoc"] == "right"


class TestAnnotation:
    def test_annotation_basic(self) -> None:
        d = Dygraph(_df()).annotation("2020-01-03", "A", tooltip="Test")
        ann = d.to_dict()["annotations"][0]
        assert ann["shortText"] == "A"
        assert ann["text"] == "Test"
        assert ann["series"] == "y"  # default to last series

    def test_annotation_series(self) -> None:
        df = pd.DataFrame(
            {"a": [1, 2], "b": [3, 4]},
            index=pd.date_range("2020-01-01", periods=2, freq="D"),
        )
        d = Dygraph(df).annotation("2020-01-01", "X", series="a")
        assert d.to_dict()["annotations"][0]["series"] == "a"

    def test_annotation_invalid_series(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            Dygraph(_df()).annotation("2020-01-01", "X", series="nonexistent")
