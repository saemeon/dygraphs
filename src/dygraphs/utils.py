"""Utility functions for dash-dygraphs, ported from R dygraphs/utils.R."""

from __future__ import annotations

import colorsys
import math
import re
from typing import Any

# ---------------------------------------------------------------------------
# Dygraphs JS library version & CDN URLs (single source of truth)
# ---------------------------------------------------------------------------

DYGRAPH_VERSION = "2.2.1"
DYGRAPH_JS_CDN = (
    f"https://cdnjs.cloudflare.com/ajax/libs/dygraph/{DYGRAPH_VERSION}/dygraph.min.js"
)
DYGRAPH_CSS_CDN = (
    f"https://cdnjs.cloudflare.com/ajax/libs/dygraph/{DYGRAPH_VERSION}/dygraph.min.css"
)


def merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *overlay* into *base*, returning a new dict.

    Mirrors R ``mergeLists``. Nested dicts are merged recursively;
    other values in *overlay* overwrite those in *base*.

    Parameters
    ----------
    base : dict[str, Any]
        Base dictionary.
    overlay : dict[str, Any]
        Dictionary whose values take precedence.

    Returns
    -------
    dict[str, Any]
        Merged dictionary (new object, does not mutate inputs).
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

    Parameters
    ----------
    pattern : str | list[int] | None
        A predefined name (``"dotted"``, ``"dashed"``, ``"dotdash"``,
        ``"solid"``) or a custom array of draw/space lengths in
        pixels, or None for a solid line.

    Returns
    -------
    list[int] | None
        Numeric dash array, or None for a solid line.

    Raises
    ------
    ValueError
        If *pattern* is a string that does not match a predefined
        name.
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
    """Convert HSV colour to a ``#rrggbb`` hex string.

    Mirrors R ``hsvToRGB``.

    Parameters
    ----------
    hue : float
        Hue component (0.0--1.0).
    saturation : float
        Saturation component (0.0--1.0).
    value : float
        Value/brightness component (0.0--1.0).

    Returns
    -------
    str
        Hex colour string, e.g. ``"#ff8000"``.
    """
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return f"#{math.floor(255 * r + 0.5):02x}{math.floor(255 * g + 0.5):02x}{math.floor(255 * b + 0.5):02x}"


def auto_colors(
    n: int,
    saturation: float = 1.0,
    value: float = 0.5,
) -> list[str]:
    """Generate *n* equally-spaced colours on a colour wheel.

    Mirrors R ``dygraphColors``.

    Parameters
    ----------
    n : int
        Number of colours to generate.
    saturation : float, optional
        HSV saturation (0.0--1.0). By default 1.0.
    value : float, optional
        HSV value/brightness (0.0--1.0). By default 0.5.

    Returns
    -------
    list[str]
        List of ``#rrggbb`` hex colour strings.
    """
    half = math.ceil(n / 2)
    colors: list[str] = []
    for i in range(n):
        idx = (half + (i + 1) // 2) if i % 2 else math.ceil((i + 1) / 2)
        hue = 1.0 * idx / (1 + n)
        colors.append(hsv_to_hex(hue, saturation, value))
    return colors


class JS:
    """Wrapper to mark a string as raw JavaScript.

    Mirrors R ``htmlwidgets::JS``. When serialised to JSON the string
    is emitted verbatim (without quotes) so that the browser can
    evaluate it as code.

    Parameters
    ----------
    code : str
        Raw JavaScript source code.
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


def _unescape_json_string(m: re.Match[str]) -> str:
    """Unwrap a ``__JS__`` marker and reverse JSON string escaping."""
    code = m.group(1)
    # json.dumps escapes these inside strings; reverse them so the JS is valid.
    # Process \\\\ first so that \\n (literal backslash-n in JS) is not
    # confused with \n (JSON newline escape).
    code = code.replace("\\\\", "\x00BACKSLASH\x00")
    code = code.replace("\\n", "\n")
    code = code.replace("\\t", "\t")
    code = code.replace('\\"', '"')
    code = code.replace("\x00BACKSLASH\x00", "\\")
    # Wrap bare `function` in parens so it's an expression, not a declaration.
    # `"plotter": function(e){...}` is invalid JS; `(function(e){...})` is valid.
    stripped = code.lstrip()
    if stripped.startswith("function") and stripped[8:9] in ("(", " "):
        code = f"({code})"
    return code


def unwrap_js_markers(json_str: str) -> str:
    """Remove ``__JS__:...:__JS__`` quote wrappers from serialised JSON.

    When ``JS`` objects are serialised via ``json.dumps`` they are
    encoded as ``"__JS__:<code>:__JS__"`` strings. This function
    strips the surrounding double-quotes and markers so the code
    appears as raw JS in the output, with JSON string escapes
    reversed.

    Parameters
    ----------
    json_str : str
        JSON string potentially containing JS markers.

    Returns
    -------
    str
        JSON string with JS markers unwrapped.
    """
    return re.sub(
        r'"__JS__:(.*?):__JS__"', _unescape_json_string, json_str, flags=re.DOTALL
    )


def serialise_js(obj: Any) -> Any:
    """Recursively convert ``JS`` objects to ``__JS__`` marker strings."""
    if isinstance(obj, JS):
        return f"__JS__:{obj.code}:__JS__"
    if isinstance(obj, dict):
        return {k: serialise_js(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialise_js(v) for v in obj]
    return obj


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
    labels : tuple[str, str, str], optional
        Column labels ``(x_label, y_label, error_label)``.
        By default ``("x", "value", "error")``.

    Returns
    -------
    dict[str, list[Any]]
        Data dict suitable for ``Dygraph()``.
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
    labels : tuple[str, str, str, str], optional
        Column labels. By default ``("x", "low", "mid", "high")``.

    Returns
    -------
    dict[str, list[Any]]
        Data dict suitable for ``Dygraph()``.
    """
    return {labels[0]: x, labels[1]: low, labels[2]: mid, labels[3]: high}
