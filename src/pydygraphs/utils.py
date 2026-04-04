"""Utility functions for dash-dygraphs, ported from R dygraphs/utils.R."""

from __future__ import annotations

import colorsys
import math
from typing import Any


def merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *overlay* into *base*, returning a new dict.

    Mirrors R ``mergeLists``.
    """
    if not base:
        return dict(overlay)
    if not overlay:
        return dict(base)
    merged = dict(base)
    for key, val in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = merge_dicts(merged[key], val)
        else:
            merged[key] = val
    return merged


def resolve_stroke_pattern(
    pattern: str | list[int] | None,
) -> list[int] | None:
    """Convert named stroke patterns to numeric arrays.

    Mirrors R ``resolveStrokePattern``.
    """
    if pattern is None:
        return None
    if isinstance(pattern, str):
        mapping = {
            "dotted": [2, 2],
            "dashed": [7, 3],
            "dotdash": [7, 2, 2, 2],
            "solid": [1, 0],
        }
        if pattern not in mapping:
            msg = (
                f"Invalid stroke pattern {pattern!r}: "
                f"valid values are {', '.join(mapping)}"
            )
            raise ValueError(msg)
        return mapping[pattern]
    return list(pattern)


def hsv_to_hex(hue: float, saturation: float, value: float) -> str:
    """Convert HSV (each 0-1) to ``#RRGGBB`` hex string.

    Mirrors R ``hsvToRGB``.
    """
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return f"#{math.floor(255 * r + 0.5):02x}{math.floor(255 * g + 0.5):02x}{math.floor(255 * b + 0.5):02x}"


def auto_colors(
    n: int,
    saturation: float = 1.0,
    value: float = 0.5,
) -> list[str]:
    """Generate *n* equally-spaced colors on a colour wheel.

    Mirrors R ``dygraphColors``.
    """
    half = math.ceil(n / 2)
    colors: list[str] = []
    for i in range(n):
        idx = (half + (i + 1) // 2) if i % 2 else math.ceil((i + 1) / 2)
        hue = 1.0 * idx / (1 + n)
        colors.append(hsv_to_hex(hue, saturation, value))
    return colors


class JS:
    """Wrapper to mark a string as raw JavaScript (like R's ``htmlwidgets::JS``).

    When serialised to JSON the string is emitted verbatim (without quotes) so
    that the browser can evaluate it.
    """

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code

    def __repr__(self) -> str:
        return f"JS({self.code!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, JS):
            return self.code == other.code
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.code)


def make_error_bar_data(
    x: list[Any],
    y: list[float],
    error: list[float],
    *,
    labels: tuple[str, str, str] = ("x", "value", "error"),
) -> dict[str, list[Any]]:
    """Build a data dict with symmetric error bars for ``Dygraph()``.

    Pass the result to ``Dygraph(data, options={"error_bars": True})``.
    Dygraphs expects ``[x, value, error]`` format when ``errorBars=True``.

    Parameters
    ----------
    x
        X-axis values (dates or numbers).
    y
        Y-axis values.
    error
        Error values (± around y).
    labels
        Column labels ``(x_label, y_label, error_label)``.
    """
    return {labels[0]: x, labels[1]: y, labels[2]: error}


def make_custom_bar_data(
    x: list[Any],
    low: list[float],
    mid: list[float],
    high: list[float],
    *,
    labels: tuple[str, str, str, str] = ("x", "low", "mid", "high"),
) -> dict[str, list[Any]]:
    """Build a data dict with custom (asymmetric) bars for ``Dygraph()``.

    Pass the result to ``Dygraph(data, options={"custom_bars": True})``.

    Parameters
    ----------
    x
        X-axis values.
    low, mid, high
        Low, middle, and high values for each point.
    labels
        Column labels.
    """
    return {labels[0]: x, labels[1]: low, labels[2]: mid, labels[3]: high}
