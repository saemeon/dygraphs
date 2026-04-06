"""Tests for utility functions."""

from __future__ import annotations

import pytest

from dygraphs.utils import (
    JS,
    auto_colors,
    hsv_to_hex,
    merge_dicts,
    resolve_stroke_pattern,
)


class TestMergeDicts:
    def test_empty_base(self) -> None:
        assert merge_dicts({}, {"a": 1}) == {"a": 1}

    def test_empty_overlay(self) -> None:
        assert merge_dicts({"a": 1}, {}) == {"a": 1}

    def test_simple_merge(self) -> None:
        result = merge_dicts({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_recursive_merge(self) -> None:
        base = {"axes": {"x": {"drawGrid": True}}}
        overlay = {"axes": {"x": {"label": "X"}, "y": {"label": "Y"}}}
        result = merge_dicts(base, overlay)
        assert result["axes"]["x"] == {"drawGrid": True, "label": "X"}
        assert result["axes"]["y"] == {"label": "Y"}

    def test_does_not_mutate(self) -> None:
        base = {"a": 1}
        overlay = {"b": 2}
        merge_dicts(base, overlay)
        assert "b" not in base


class TestResolveStrokePattern:
    def test_named_patterns(self) -> None:
        assert resolve_stroke_pattern("dotted") == [2, 2]
        assert resolve_stroke_pattern("dashed") == [7, 3]
        assert resolve_stroke_pattern("dotdash") == [7, 2, 2, 2]
        assert resolve_stroke_pattern("solid") == [1, 0]

    def test_none(self) -> None:
        assert resolve_stroke_pattern(None) is None

    def test_custom(self) -> None:
        assert resolve_stroke_pattern([5, 5]) == [5, 5]

    def test_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid"):
            resolve_stroke_pattern("unknown")


class TestHsvToHex:
    def test_red(self) -> None:
        assert hsv_to_hex(0.0, 1.0, 1.0) == "#ff0000"

    def test_black(self) -> None:
        assert hsv_to_hex(0.0, 0.0, 0.0) == "#000000"


class TestAutoColors:
    def test_generates_n_colors(self) -> None:
        colors = auto_colors(5)
        assert len(colors) == 5
        assert all(c.startswith("#") for c in colors)

    def test_unique(self) -> None:
        colors = auto_colors(10)
        assert len(set(colors)) == 10


class TestJS:
    def test_repr(self) -> None:
        j = JS("function(){}")
        assert "function" in repr(j)

    def test_equality(self) -> None:
        assert JS("a") == JS("a")
        assert JS("a") != JS("b")

    def test_hash(self) -> None:
        s = {JS("a"), JS("a"), JS("b")}
        assert len(s) == 2
