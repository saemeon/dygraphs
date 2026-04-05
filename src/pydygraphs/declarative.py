"""Declarative API — dataclasses mirroring every builder method.

Each dataclass can be passed to ``Dygraph(...)`` as a keyword argument,
or as a plain ``dict`` with the same keys. Both produce identical output.

Example::

    from pydygraphs import Dygraph, Series, Axis, Legend, RangeSelector

    chart = Dygraph(
        df,
        title="Weather",
        options={"fill_graph": True, "draw_points": True},
        series=[
            Series("temp", color="red", stroke_width=2),
            {"name": "rain", "axis": "y2"},
        ],
        axes={"y": Axis("y", label="Temp"), "y2": {"name": "y2", "label": "Rain"}},
        legend=Legend(show="always"),
        range_selector=RangeSelector(height=30),
    )
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Literal


def _to_kwargs(obj: Any) -> dict[str, Any]:
    """Convert a dataclass or dict to keyword arguments.

    For dataclasses: returns ``asdict()`` with ``None`` values removed
    (so defaults in the builder method are used).
    For dicts: returns as-is.
    """
    if isinstance(obj, dict):
        return obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: v for k, v in dataclasses.asdict(obj).items() if v is not None}
    msg = f"Expected a dataclass or dict, got {type(obj)}"
    raise TypeError(msg)


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Options:
    """Global chart options (mirrors ``.options()`` builder method)."""

    stacked_graph: bool = False
    fill_graph: bool = False
    fill_alpha: float = 0.15
    step_plot: bool = False
    stem_plot: bool = False
    draw_points: bool = False
    point_size: float = 1.0
    point_shape: str = "dot"
    draw_gap_edge_points: bool = False
    connect_separated_points: bool = False
    stroke_width: float = 1.0
    stroke_pattern: str | list[int] | None = None
    stroke_border_width: float | None = None
    stroke_border_color: str = "white"
    plotter: str | None = None
    colors: list[str] | None = field(default=None)
    color_value: float = 0.5
    color_saturation: float = 1.0
    draw_x_axis: bool = True
    draw_y_axis: bool = True
    include_zero: bool = False
    draw_axes_at_zero: bool = False
    logscale: bool = False
    axis_tick_size: float = 3.0
    axis_line_color: str = "black"
    axis_line_width: float = 0.3
    axis_label_color: str = "black"
    axis_label_font_size: int = 14
    axis_label_width: int = 60
    draw_grid: bool = True
    grid_line_color: str | None = None
    grid_line_width: float = 0.3
    title_height: int | None = None
    right_gap: int = 5
    digits_after_decimal: int = 2
    labels_kmb: bool = False
    labels_kmg2: bool = False
    labels_utc: bool = False
    max_number_width: int = 6
    sig_figs: int | None = None
    pan_edge_fraction: float | None = None
    animated_zooms: bool = False
    disable_zoom: bool = False
    retain_date_window: bool = False
    error_bars: bool = False
    custom_bars: bool = False
    sigma: float | None = None
    fractions: bool = False
    wilson_interval: bool = True
    visibility: list[bool] | None = field(default=None)
    legend_formatter: str | None = None
    range_selector_plot_line_width: float | None = None
    range_selector_plot_fill_gradient_color: str | None = None
    range_selector_background_line_width: float | None = None
    range_selector_background_stroke_color: str | None = None
    range_selector_foreground_stroke_color: str | None = None
    range_selector_foreground_line_width: float | None = None
    range_selector_alpha: float | None = None
    grid_line_pattern: list[int] | None = field(default=None)
    resizable: str | None = None
    pixel_ratio: float | None = None
    stacked_graph_nan_fill: str | None = None
    animate_background_fade: bool = True
    x_label_height: int | None = None
    y_label_width: int | None = None
    legend_follow_offset_x: int | None = None
    legend_follow_offset_y: int | None = None
    range_selector_veil_colour: str | None = None
    delimiter: str | None = None
    x_value_parser: str | None = None
    display_annotations: bool = False
    data_handler: str | None = None


# ---------------------------------------------------------------------------
# Axis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Axis:
    """Per-axis configuration (mirrors ``.axis()`` builder method)."""

    name: Literal["x", "y", "y2"]
    label: str | None = None
    value_range: tuple[float | None, float | None] | None = None
    logscale: bool | None = None
    ticker: str | None = None
    range_pad: float | None = None
    label_width: int | None = None
    label_height: int | None = None
    axis_height: int | None = None
    axis_line_color: str | None = None
    axis_line_width: float | None = None
    pixels_per_label: int | None = None
    axis_label_color: str | None = None
    axis_label_font_size: int | None = None
    axis_label_width: int | None = None
    axis_label_formatter: str | None = None
    value_formatter: str | None = None
    draw_grid: bool | None = None
    grid_line_color: str | None = None
    grid_line_width: float | None = None
    independent_ticks: bool | None = None


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Series:
    """Per-series configuration (mirrors ``.series()`` builder method)."""

    name: str | None = None
    label: str | None = None
    color: str | None = None
    axis: Literal["y", "y2"] = "y"
    step_plot: bool | None = None
    stem_plot: bool | None = None
    fill_graph: bool | None = None
    draw_points: bool | None = None
    point_size: float | None = None
    point_shape: str | None = None
    stroke_width: float | None = None
    stroke_pattern: str | list[int] | None = None
    stroke_border_width: float | None = None
    stroke_border_color: str | None = None
    plotter: str | None = None
    highlight_circle_size: int | None = None
    show_in_range_selector: bool | None = None


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Legend:
    """Legend configuration (mirrors ``.legend()`` builder method)."""

    show: Literal["auto", "always", "onmouseover", "follow", "never"] = "auto"
    width: int = 250
    show_zero_values: bool = True
    labels_div: str | None = None
    labels_separate_lines: bool = False
    hide_on_mouse_out: bool = True


# ---------------------------------------------------------------------------
# Highlight
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Highlight:
    """Highlight configuration (mirrors ``.highlight()`` builder method)."""

    circle_size: int = 3
    series_background_alpha: float = 0.5
    series_background_color: str | None = None
    series_opts: dict[str, Any] | None = field(default=None)
    hide_on_mouse_out: bool = True


# ---------------------------------------------------------------------------
# Annotation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Annotation:
    """Data point annotation (mirrors ``.annotation()`` builder method)."""

    x: Any = None
    text: str = ""
    tooltip: str | None = None
    width: int | None = None
    height: int | None = None
    css_class: str | None = None
    tick_height: int | None = None
    tick_color: str | None = None
    tick_width: int | None = None
    attach_at_bottom: bool = False
    icon: str | None = None
    click_handler: str | None = None
    mouse_over_handler: str | None = None
    mouse_out_handler: str | None = None
    dbl_click_handler: str | None = None
    series: str | None = None


# ---------------------------------------------------------------------------
# Shading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Shading:
    """Background region shading (mirrors ``.shading()`` builder method)."""

    from_: Any = None
    to: Any = None
    color: str = "#EFEFEF"
    axis: Literal["x", "y"] = "x"


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Event:
    """Vertical event line (mirrors ``.event()`` builder method)."""

    x: Any = None
    label: str | None = None
    label_loc: Literal["top", "bottom"] = "top"
    color: str = "black"
    stroke_pattern: str | list[int] = "dashed"


# ---------------------------------------------------------------------------
# Limit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Limit:
    """Horizontal limit line (mirrors ``.limit()`` builder method)."""

    value: float = 0.0
    label: str | None = None
    label_loc: Literal["left", "right"] = "left"
    color: str = "black"
    stroke_pattern: str | list[int] = "dashed"


# ---------------------------------------------------------------------------
# RangeSelector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RangeSelector:
    """Range selector widget (mirrors ``.range_selector()`` builder method)."""

    date_window: tuple[Any, Any] | None = None
    height: int = 40
    fill_color: str = "#A7B1C4"
    stroke_color: str = "#808FAB"
    keep_mouse_zoom: bool = True
    retain_date_window: bool = False


# ---------------------------------------------------------------------------
# Roller
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Roller:
    """Rolling average control (mirrors ``.roller()`` builder method)."""

    show: bool = True
    roll_period: int = 1


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Callbacks:
    """JavaScript event callbacks (mirrors ``.callbacks()`` builder method)."""

    click: str | None = None
    draw: str | None = None
    highlight: str | None = None
    point_click: str | None = None
    underlay: str | None = None
    unhighlight: str | None = None
    zoom: str | None = None
    draw_highlight_point: str | None = None
    draw_point: str | None = None
    annotation_click: str | None = None
    annotation_mouse_over: str | None = None
    annotation_mouse_out: str | None = None
    annotation_dbl_click: str | None = None
