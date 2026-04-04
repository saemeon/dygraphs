"""Core Dygraph builder — the main entry point for dash-dygraphs.

Ported from R ``dygraphs/R/dygraph.R`` + all dy* modifier functions.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydygraphs.utils import (
    JS,
    auto_colors,
    merge_dicts,
    resolve_stroke_pattern,
)

if TYPE_CHECKING:
    import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POINT_SHAPES = (
    "dot",
    "triangle",
    "square",
    "diamond",
    "pentagon",
    "hexagon",
    "circle",
    "star",
    "plus",
    "ex",
)

ASSETS_DIR = Path(__file__).parent / "assets"

# Stem-plot plotter JS (from R series.R resolveStemPlot)
_STEM_PLOTTER_JS = """\
function stemPlotter(e) {
  var ctx = e.drawingContext;
  var points = e.points;
  var y_bottom = e.dygraph.toDomYCoord(0);
  ctx.fillStyle = e.color;
  for (var i = 0; i < points.length; i++) {
    var p = points[i];
    var center_x = p.canvasx;
    var center_y = p.canvasy;
    ctx.beginPath();
    ctx.moveTo(center_x, y_bottom);
    ctx.lineTo(center_x, center_y);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(center_x, center_y, 3, 0, 2*Math.PI);
    ctx.stroke();
  }
}"""


# ---------------------------------------------------------------------------
# Helper: read a bundled JS plotter file
# ---------------------------------------------------------------------------


def _read_plotter(name: str) -> str:
    path = ASSETS_DIR / "plotters" / f"{name}.js"
    return path.read_text()


def _read_plugin(name: str) -> str:
    path = ASSETS_DIR / "plugins" / f"{name}.js"
    return path.read_text()


# ---------------------------------------------------------------------------
# Dygraph builder
# ---------------------------------------------------------------------------


class Dygraph:
    """Builder for a dygraphs chart.

    Mirrors the R ``dygraph()`` constructor and its family of ``dy*()`` pipe
    functions, expressed as chained method calls.

    Parameters
    ----------
    data
        A pandas DataFrame, Series, dict of lists, or 2-D list.  For
        DataFrames the index is used as the x-axis; for dicts the first key
        is x.
    title
        Chart title (``main`` in R).
    xlab, ylab
        Axis labels.
    group
        Synchronisation group name (x-axis zoom is synced across group).
    width, height
        Chart dimensions in pixels (``None`` = auto).
    """

    # ---- construction ------------------------------------------------

    def __init__(
        self,
        data: pd.DataFrame | pd.Series | dict[str, Any] | list[list[Any]] | str,
        title: str | None = None,
        xlab: str | None = None,
        ylab: str | None = None,
        group: str | None = None,
        width: int | None = None,
        height: int | None = None,
        # ---- declarative params (optional) ----
        options: Any = None,
        axes: dict[str, Any] | list[Any] | None = None,
        series: list[Any] | None = None,
        legend: Any = None,
        highlight: Any = None,
        annotations: list[Any] | None = None,
        shadings: list[Any] | None = None,
        events: list[Any] | None = None,
        limits: list[Any] | None = None,
        range_selector: Any = None,
        roller: Any = None,
        callbacks: Any = None,
        plotter: str | None = None,
    ) -> None:
        self._width = width
        self._height = height

        # Normalise data into (labels, columns, format)
        labels, columns, fmt = self._normalise_data(data)

        # attrs = JS dygraph options
        attrs: dict[str, Any] = {}
        if title is not None:
            attrs["title"] = title
        if xlab is not None:
            attrs["xlabel"] = xlab
        if ylab is not None:
            attrs["ylabel"] = ylab
        attrs["labels"] = list(labels)
        attrs["legend"] = "auto"
        attrs["retainDateWindow"] = False
        attrs["axes"] = {"x": {"pixelsPerLabel": 60}}

        self._attrs = attrs
        self._format: str = fmt  # "date" or "numeric"
        self._data: list[list[Any]] = columns  # list of columns (incl. x)
        self._annotations: list[dict[str, Any]] = []
        self._shadings: list[dict[str, Any]] = []
        self._events: list[dict[str, Any]] = []
        self._plugins: list[dict[str, Any]] = []
        self._css: str | None = None
        self._point_shapes: dict[str, str] = {}
        self._group = group
        self._extra_js: list[str] = []  # plotter / plugin JS to inject

        # Apply declarative params (if provided)
        self._apply_declarative(
            options=options,
            axes=axes,
            series=series,
            legend=legend,
            highlight=highlight,
            annotations=annotations,
            shadings=shadings,
            events=events,
            limits=limits,
            range_selector=range_selector,
            roller=roller,
            callbacks=callbacks,
            plotter=plotter,
        )

    # ---- declarative application ------------------------------------

    def _apply_declarative(
        self,
        *,
        options: Any = None,
        axes: dict[str, Any] | list[Any] | None = None,
        series: list[Any] | None = None,
        legend: Any = None,
        highlight: Any = None,
        annotations: list[Any] | None = None,
        shadings: list[Any] | None = None,
        events: list[Any] | None = None,
        limits: list[Any] | None = None,
        range_selector: Any = None,
        roller: Any = None,
        callbacks: Any = None,
        plotter: str | None = None,
    ) -> None:
        """Apply declarative dataclass/dict params by delegating to builder methods."""
        from pydygraphs.declarative import _to_kwargs

        if options is not None:
            self.options(**_to_kwargs(options))
        if plotter is not None:
            _plotter_methods: dict[str, str] = {
                "bar_chart": "bar_chart",
                "stacked_bar_chart": "stacked_bar_chart",
                "multi_column": "multi_column",
                "candlestick": "candlestick",
            }
            method_name = _plotter_methods.get(plotter)
            if method_name:
                getattr(self, method_name)()
            else:
                self.options(plotter=plotter)
        if axes is not None:
            items = axes.values() if isinstance(axes, dict) else axes
            for ax in items:
                self.axis(**_to_kwargs(ax))
        if series is not None:
            for s in series:
                self.series(**_to_kwargs(s))
        if legend is not None:
            self.legend(**_to_kwargs(legend))
        if highlight is not None:
            self.highlight(**_to_kwargs(highlight))
        if annotations is not None:
            for a in annotations:
                self.annotation(**_to_kwargs(a))
        if shadings is not None:
            for s in shadings:
                self.shading(**_to_kwargs(s))
        if events is not None:
            for e in events:
                self.event(**_to_kwargs(e))
        if limits is not None:
            for lim in limits:
                self.limit(**_to_kwargs(lim))
        if range_selector is not None:
            self.range_selector(**_to_kwargs(range_selector))
        if roller is not None:
            self.roller(**_to_kwargs(roller))
        if callbacks is not None:
            self.callbacks(**_to_kwargs(callbacks))

    # ---- data normalisation ------------------------------------------

    @staticmethod
    def _normalise_data(
        data: Any,
    ) -> tuple[list[str], list[list[Any]], str]:
        """Return (labels, columns_as_lists, format_string)."""
        import pandas as pd

        # CSV string input
        if isinstance(data, str):
            import io

            data = pd.read_csv(io.StringIO(data))
            # If first column looks like dates, use it as index
            first_col_name = data.columns[0]
            first_col = data[first_col_name]
            if pd.api.types.is_string_dtype(first_col):
                # Only try date parsing on string columns
                try:
                    date_idx = pd.to_datetime(first_col)
                    data = data.drop(columns=[first_col_name]).set_index(date_idx)
                except (ValueError, TypeError):
                    data = data.set_index(first_col_name)
            else:
                data = data.set_index(first_col_name)

        if isinstance(data, pd.Series):
            data = data.to_frame()

        if isinstance(data, pd.DataFrame):
            idx = data.index
            if isinstance(idx, pd.DatetimeIndex):
                # DatetimeIndex → ISO strings
                x_vals = [
                    t.isoformat() + "Z" if t.tzinfo is None else t.isoformat()
                    for t in idx
                ]
                fmt = "date"
                x_label = idx.name or "Date"
            else:
                x_vals = idx.tolist()
                fmt = "numeric"
                x_label = idx.name or "x"
            labels = [str(x_label)] + [str(c) for c in data.columns]
            columns: list[list[Any]] = [
                x_vals,
                *(data[col].tolist() for col in data.columns),
            ]
            return labels, columns, fmt

        if isinstance(data, dict):
            keys = list(data.keys())
            if not keys:
                msg = "data dict must not be empty"
                raise ValueError(msg)
            fmt = "numeric"
            labels: list[str] = [str(k) for k in keys]
            columns: list[list[Any]] = [list(v) for v in data.values()]
            return labels, columns, fmt

        # numpy array → treat as 2D array (columns)
        try:
            import numpy as np

            if isinstance(data, np.ndarray):
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                n_cols = data.shape[1]
                labels = [f"V{i}" for i in range(n_cols)]
                columns = [data[:, i].tolist() for i in range(n_cols)]
                fmt = "numeric"
                return labels, columns, fmt
        except ImportError:
            pass

        if isinstance(data, list):
            if not data or not isinstance(data[0], list):
                msg = "When data is a list it must be a list of rows (list of lists)"
                raise TypeError(msg)
            n_cols = len(data[0])
            labels = [f"V{i}" for i in range(n_cols)]
            columns = [[] for _ in range(n_cols)]
            for row in data:
                for i, v in enumerate(row):
                    columns[i].append(v)
            fmt = "numeric"
            return labels, columns, fmt

        msg = f"Unsupported data type: {type(data)}"
        raise TypeError(msg)

    # ---- options (dyOptions) -----------------------------------------

    def options(
        self,
        *,
        stacked_graph: bool = False,
        fill_graph: bool = False,
        fill_alpha: float = 0.15,
        step_plot: bool = False,
        stem_plot: bool = False,
        draw_points: bool = False,
        point_size: float = 1.0,
        point_shape: str = "dot",
        draw_gap_edge_points: bool = False,
        connect_separated_points: bool = False,
        stroke_width: float = 1.0,
        stroke_pattern: str | list[int] | None = None,
        stroke_border_width: float | None = None,
        stroke_border_color: str = "white",
        plotter: str | None = None,
        colors: list[str] | None = None,
        color_value: float = 0.5,
        color_saturation: float = 1.0,
        draw_x_axis: bool = True,
        draw_y_axis: bool = True,
        include_zero: bool = False,
        draw_axes_at_zero: bool = False,
        logscale: bool = False,
        axis_tick_size: float = 3.0,
        axis_line_color: str = "black",
        axis_line_width: float = 0.3,
        axis_label_color: str = "black",
        axis_label_font_size: int = 14,
        axis_label_width: int = 60,
        draw_grid: bool = True,
        grid_line_color: str | None = None,
        grid_line_width: float = 0.3,
        title_height: int | None = None,
        right_gap: int = 5,
        digits_after_decimal: int = 2,
        labels_kmb: bool = False,
        labels_kmg2: bool = False,
        labels_utc: bool = False,
        max_number_width: int = 6,
        sig_figs: int | None = None,
        pan_edge_fraction: float | None = None,
        animated_zooms: bool = False,
        disable_zoom: bool = False,
        retain_date_window: bool = False,
        # Error bars
        error_bars: bool = False,
        custom_bars: bool = False,
        sigma: float | None = None,
        fractions: bool = False,
        wilson_interval: bool = True,
        # Visibility
        visibility: list[bool] | None = None,
        # Legend
        legend_formatter: str | None = None,
        # Range selector fine styling
        range_selector_plot_line_width: float | None = None,
        range_selector_plot_fill_gradient_color: str | None = None,
        range_selector_background_line_width: float | None = None,
        range_selector_background_stroke_color: str | None = None,
        range_selector_foreground_stroke_color: str | None = None,
        range_selector_foreground_line_width: float | None = None,
        range_selector_alpha: float | None = None,
        # Grid
        grid_line_pattern: list[int] | None = None,
        # Resize
        resizable: str | None = None,
        pixel_ratio: float | None = None,
    ) -> Dygraph:
        """Set global chart options (mirrors R ``dyOptions``)."""
        if stem_plot:
            if plotter is not None:
                msg = "stem_plot provides its own plotter, cannot combine with plotter="
                raise ValueError(msg)
            plotter = _STEM_PLOTTER_JS

        opts: dict[str, Any] = {
            "stackedGraph": stacked_graph,
            "fillGraph": fill_graph,
            "fillAlpha": fill_alpha,
            "stepPlot": step_plot,
            "drawPoints": draw_points,
            "pointSize": point_size,
            "drawGapEdgePoints": draw_gap_edge_points,
            "connectSeparatedPoints": connect_separated_points,
            "strokeWidth": stroke_width,
            "strokeBorderColor": stroke_border_color,
            "colorValue": color_value,
            "colorSaturation": color_saturation,
            "includeZero": include_zero,
            "drawAxesAtZero": draw_axes_at_zero,
            "logscale": logscale,
            "axisTickSize": axis_tick_size,
            "axisLineColor": axis_line_color,
            "axisLineWidth": axis_line_width,
            "axisLabelColor": axis_label_color,
            "axisLabelFontSize": axis_label_font_size,
            "axisLabelWidth": axis_label_width,
            "drawGrid": draw_grid,
            "gridLineWidth": grid_line_width,
            "rightGap": right_gap,
            "digitsAfterDecimal": digits_after_decimal,
            "labelsKMB": labels_kmb,
            "labelsKMG2": labels_kmg2,
            "labelsUTC": labels_utc,
            "maxNumberWidth": max_number_width,
            "animatedZooms": animated_zooms,
            "disableZoom": disable_zoom,
            "retainDateWindow": retain_date_window,
        }
        if stroke_pattern is not None:
            opts["strokePattern"] = resolve_stroke_pattern(stroke_pattern)
        if stroke_border_width is not None:
            opts["strokeBorderWidth"] = stroke_border_width
        if plotter is not None:
            opts["plotter"] = JS(plotter)
        if colors is not None:
            opts["colors"] = list(colors)
        if grid_line_color is not None:
            opts["gridLineColor"] = grid_line_color
        if title_height is not None:
            opts["titleHeight"] = title_height
        if sig_figs is not None:
            opts["sigFigs"] = sig_figs
        if pan_edge_fraction is not None:
            opts["panEdgeFraction"] = pan_edge_fraction
        # Error bars
        if error_bars:
            opts["errorBars"] = True
        if custom_bars:
            opts["customBars"] = True
        if sigma is not None:
            opts["sigma"] = sigma
        if fractions:
            opts["fractions"] = True
            opts["wilsonInterval"] = wilson_interval
        # Visibility
        if visibility is not None:
            opts["visibility"] = visibility
        # Legend formatter
        if legend_formatter is not None:
            opts["legendFormatter"] = JS(legend_formatter)
        # Range selector fine styling
        if range_selector_plot_line_width is not None:
            opts["rangeSelectorPlotLineWidth"] = range_selector_plot_line_width
        if range_selector_plot_fill_gradient_color is not None:
            opts["rangeSelectorPlotFillGradientColor"] = (
                range_selector_plot_fill_gradient_color
            )
        if range_selector_background_line_width is not None:
            opts["rangeSelectorBackgroundLineWidth"] = (
                range_selector_background_line_width
            )
        if range_selector_background_stroke_color is not None:
            opts["rangeSelectorBackgroundStrokeColor"] = (
                range_selector_background_stroke_color
            )
        if range_selector_foreground_stroke_color is not None:
            opts["rangeSelectorForegroundStrokeColor"] = (
                range_selector_foreground_stroke_color
            )
        if range_selector_foreground_line_width is not None:
            opts["rangeSelectorForegroundLineWidth"] = (
                range_selector_foreground_line_width
            )
        if range_selector_alpha is not None:
            opts["rangeSelectorAlpha"] = range_selector_alpha
        # Grid line pattern
        if grid_line_pattern is not None:
            opts["gridLinePattern"] = grid_line_pattern
        # Resize
        if resizable is not None:
            opts["resizable"] = resizable
        if pixel_ratio is not None:
            opts["pixelRatio"] = pixel_ratio

        # axes sub-options
        opts.setdefault("axes", {})
        opts["axes"]["x"] = {"drawAxis": draw_x_axis}
        opts["axes"]["y"] = {"drawAxis": draw_y_axis}

        # point shape
        if point_shape != "dot":
            if point_shape not in POINT_SHAPES:
                msg = f"Invalid point_shape {point_shape!r}, must be one of {POINT_SHAPES}"
                raise ValueError(msg)
            self._point_shapes["__global__"] = point_shape

        self._attrs = merge_dicts(self._attrs, opts)
        return self

    # ---- axis (dyAxis) -----------------------------------------------

    def axis(
        self,
        name: Literal["x", "y", "y2"],
        *,
        label: str | None = None,
        value_range: tuple[float | None, float | None] | None = None,
        logscale: bool | None = None,
        ticker: str | None = None,
        range_pad: float | None = None,
        label_width: int | None = None,
        label_height: int | None = None,
        axis_height: int | None = None,
        axis_line_color: str | None = None,
        axis_line_width: float | None = None,
        pixels_per_label: int | None = None,
        axis_label_color: str | None = None,
        axis_label_font_size: int | None = None,
        axis_label_width: int | None = None,
        axis_label_formatter: str | None = None,
        value_formatter: str | None = None,
        draw_grid: bool | None = None,
        grid_line_color: str | None = None,
        grid_line_width: float | None = None,
        independent_ticks: bool | None = None,
    ) -> Dygraph:
        """Configure a specific axis (mirrors R ``dyAxis``)."""
        if name not in ("x", "y", "y2"):
            msg = f"Axis name must be 'x', 'y', or 'y2', got {name!r}"
            raise ValueError(msg)

        extra_attrs: dict[str, Any] = {}
        axis_opts: dict[str, Any] = {}

        if label is not None:
            extra_attrs[f"{name}label"] = label
        if value_range is not None:
            axis_opts["valueRange"] = list(value_range)
        if logscale is not None:
            if name == "x":
                axis_opts["logscale"] = logscale
            else:
                extra_attrs["logscale"] = logscale
        if ticker is not None:
            axis_opts["ticker"] = JS(ticker)
        if axis_height is not None:
            if name != "x":
                msg = "axis_height is only applicable to the x axis"
                raise ValueError(msg)
            extra_attrs["xAxisHeight"] = axis_height
        if range_pad is not None:
            extra_attrs[f"{name}RangePad"] = range_pad
        if label_width is not None:
            extra_attrs[f"{name}LabelWidth"] = label_width
        if label_height is not None:
            extra_attrs[f"{name}LabelHeight"] = label_height
        if axis_line_color is not None:
            axis_opts["axisLineColor"] = axis_line_color
        if axis_line_width is not None:
            axis_opts["axisLineWidth"] = axis_line_width
        if pixels_per_label is not None:
            axis_opts["pixelsPerLabel"] = pixels_per_label
        if axis_label_color is not None:
            axis_opts["axisLabelColor"] = axis_label_color
        if axis_label_font_size is not None:
            axis_opts["axisLabelFontSize"] = axis_label_font_size
        if axis_label_width is not None:
            axis_opts["axisLabelWidth"] = axis_label_width
        if axis_label_formatter is not None:
            axis_opts["axisLabelFormatter"] = JS(axis_label_formatter)
        if value_formatter is not None:
            axis_opts["valueFormatter"] = JS(value_formatter)
        if draw_grid is not None:
            axis_opts["drawGrid"] = draw_grid
        if grid_line_color is not None:
            axis_opts["gridLineColor"] = grid_line_color
        if grid_line_width is not None:
            axis_opts["gridLineWidth"] = grid_line_width
        if independent_ticks is not None:
            axis_opts["independentTicks"] = independent_ticks

        extra_attrs.setdefault("axes", {})
        extra_attrs["axes"][name] = axis_opts
        self._attrs = merge_dicts(self._attrs, extra_attrs)
        return self

    # ---- series (dySeries) -------------------------------------------

    def series(
        self,
        name: str | None = None,
        *,
        label: str | None = None,
        color: str | None = None,
        axis: Literal["y", "y2"] = "y",
        step_plot: bool | None = None,
        stem_plot: bool | None = None,
        fill_graph: bool | None = None,
        draw_points: bool | None = None,
        point_size: float | None = None,
        point_shape: str | None = None,
        stroke_width: float | None = None,
        stroke_pattern: str | list[int] | None = None,
        stroke_border_width: float | None = None,
        stroke_border_color: str | None = None,
        plotter: str | None = None,
    ) -> Dygraph:
        """Configure a data series (mirrors R ``dySeries``)."""
        labels = self._attrs["labels"]

        if name is None:
            # Auto-bind: first unprocessed series
            name = labels[1] if len(labels) > 1 else None
            if name is None:
                msg = "No series available to bind"
                raise ValueError(msg)

        if name not in labels:
            msg = f"Series {name!r} not found. Valid series names: {labels[1:]}"
            raise ValueError(msg)

        if stem_plot:
            if plotter is not None:
                msg = "stem_plot provides its own plotter, cannot combine with plotter="
                raise ValueError(msg)
            plotter = _STEM_PLOTTER_JS

        series_label = label or name
        series_opts: dict[str, Any] = {"axis": axis}

        if step_plot is not None:
            series_opts["stepPlot"] = step_plot
        if fill_graph is not None:
            series_opts["fillGraph"] = fill_graph
        if draw_points is not None:
            series_opts["drawPoints"] = draw_points
        if point_size is not None:
            series_opts["pointSize"] = point_size
        if stroke_width is not None:
            series_opts["strokeWidth"] = stroke_width
        if stroke_pattern is not None:
            series_opts["strokePattern"] = resolve_stroke_pattern(stroke_pattern)
        if stroke_border_width is not None:
            series_opts["strokeBorderWidth"] = stroke_border_width
        if stroke_border_color is not None:
            series_opts["strokeBorderColor"] = stroke_border_color
        if plotter is not None:
            series_opts["plotter"] = JS(plotter)

        # Handle color
        if color is not None:
            n_series = len(labels) - 1
            if "colors" not in self._attrs:
                self._attrs["colors"] = auto_colors(
                    n_series,
                    self._attrs.get("colorSaturation", 1.0),
                    self._attrs.get("colorValue", 0.5),
                )
            idx = labels.index(name) - 1
            self._attrs["colors"][idx] = color

        # Rename if label differs
        if series_label != name:
            idx = labels.index(name)
            self._attrs["labels"][idx] = series_label

        self._attrs.setdefault("series", {})
        self._attrs["series"][series_label] = merge_dicts(
            self._attrs["series"].get(series_label, {}),
            series_opts,
        )

        if point_shape is not None and point_shape != "dot":
            if point_shape not in POINT_SHAPES:
                msg = f"Invalid point_shape {point_shape!r}"
                raise ValueError(msg)
            self._point_shapes[series_label] = point_shape

        return self

    # ---- group (dyGroup) ---------------------------------------------

    def group(
        self,
        names: list[str],
        *,
        color: list[str] | None = None,
        axis: Literal["y", "y2"] = "y",
        step_plot: bool | None = None,
        fill_graph: bool | None = None,
        draw_points: bool | None = None,
        point_size: float | None = None,
        point_shape: list[str] | None = None,
        stroke_width: float | None = None,
        stroke_pattern: str | list[int] | None = None,
        stroke_border_width: float | None = None,
        stroke_border_color: str | None = None,
        plotter: str | None = None,
    ) -> Dygraph:
        """Configure a group of series (mirrors R ``dyGroup``)."""
        if len(names) == 1:
            return self.series(
                names[0], color=color[0] if color else None, plotter=plotter
            )

        labels = self._attrs["labels"]
        for n in names:
            if n not in labels:
                msg = f"Series {n!r} not found. Valid: {labels[1:]}"
                raise ValueError(msg)

        group_id = "".join(names)
        self._attrs.setdefault("series", {})

        for i, n in enumerate(names):
            series_opts: dict[str, Any] = {"axis": axis, "group": group_id}
            if step_plot is not None:
                series_opts["stepPlot"] = step_plot
            if fill_graph is not None:
                series_opts["fillGraph"] = fill_graph
            if draw_points is not None:
                series_opts["drawPoints"] = draw_points
            if point_size is not None:
                series_opts["pointSize"] = point_size
            if stroke_width is not None:
                series_opts["strokeWidth"] = stroke_width
            if stroke_pattern is not None:
                series_opts["strokePattern"] = resolve_stroke_pattern(stroke_pattern)
            if stroke_border_width is not None:
                series_opts["strokeBorderWidth"] = stroke_border_width
            if stroke_border_color is not None:
                series_opts["strokeBorderColor"] = stroke_border_color
            if plotter is not None:
                series_opts["plotter"] = JS(plotter)

            if color is not None:
                if "colors" not in self._attrs:
                    n_series = len(labels) - 1
                    self._attrs["colors"] = auto_colors(n_series)
                idx = labels.index(n) - 1
                self._attrs["colors"][idx] = color[i % len(color)]

            self._attrs["series"][n] = merge_dicts(
                self._attrs["series"].get(n, {}), series_opts
            )

            if point_shape is not None:
                shape = point_shape[i % len(point_shape)]
                if shape != "dot":
                    self._point_shapes[n] = shape

        return self

    # ---- legend (dyLegend) -------------------------------------------

    def legend(
        self,
        show: Literal["auto", "always", "onmouseover", "follow", "never"] = "auto",
        width: int = 250,
        show_zero_values: bool = True,
        labels_div: str | None = None,
        labels_separate_lines: bool = False,
        hide_on_mouse_out: bool = True,
    ) -> Dygraph:
        """Configure legend (mirrors R ``dyLegend``)."""
        opts: dict[str, Any] = {}
        if show == "never":
            opts["showLabelsOnHighlight"] = False
        else:
            opts["legend"] = show
        opts["labelsDivWidth"] = width
        opts["labelsShowZeroValues"] = show_zero_values
        if labels_div is not None:
            opts["labelsDiv"] = labels_div
        opts["labelsSeparateLines"] = labels_separate_lines
        opts["hideOverlayOnMouseOut"] = hide_on_mouse_out
        self._attrs = merge_dicts(self._attrs, opts)
        return self

    # ---- highlight (dyHighlight) -------------------------------------

    def highlight(
        self,
        circle_size: int = 3,
        series_background_alpha: float = 0.5,
        series_opts: dict[str, Any] | None = None,
        hide_on_mouse_out: bool = True,
    ) -> Dygraph:
        """Configure highlight behaviour (mirrors R ``dyHighlight``)."""
        opts: dict[str, Any] = {
            "highlightCircleSize": circle_size,
            "highlightSeriesBackgroundAlpha": series_background_alpha,
            "hideOverlayOnMouseOut": hide_on_mouse_out,
        }
        if series_opts:
            opts["highlightSeriesOpts"] = series_opts
        self._attrs = merge_dicts(self._attrs, opts)
        return self

    # ---- annotation (dyAnnotation) -----------------------------------

    def annotation(
        self,
        x: Any,
        text: str,
        *,
        tooltip: str | None = None,
        width: int | None = None,
        height: int | None = None,
        css_class: str | None = None,
        tick_height: int | None = None,
        attach_at_bottom: bool = False,
        click_handler: str | None = None,
        mouse_over_handler: str | None = None,
        mouse_out_handler: str | None = None,
        dbl_click_handler: str | None = None,
        series: str | None = None,
    ) -> Dygraph:
        """Add an annotation (mirrors R ``dyAnnotation``)."""
        if self._format == "date" and not isinstance(x, str):
            import pandas as pd

            x = pd.Timestamp(x).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        if series is not None and series not in self._attrs["labels"]:
            msg = f"Series {series!r} not found. Valid: {self._attrs['labels'][1:]}"
            raise ValueError(msg)
        if series is None:
            series = self._attrs["labels"][-1]

        ann: dict[str, Any] = {
            "x": x,
            "shortText": text,
            "series": series,
            "attachAtBottom": attach_at_bottom,
        }
        if tooltip is not None:
            ann["text"] = tooltip
        if width is not None:
            ann["width"] = width
        if height is not None:
            ann["height"] = height
        if css_class is not None:
            ann["cssClass"] = css_class
        if tick_height is not None:
            ann["tickHeight"] = tick_height
        if click_handler is not None:
            ann["clickHandler"] = JS(click_handler)
        if mouse_over_handler is not None:
            ann["mouseOverHandler"] = JS(mouse_over_handler)
        if mouse_out_handler is not None:
            ann["mouseOutHandler"] = JS(mouse_out_handler)
        if dbl_click_handler is not None:
            ann["dblClickHandler"] = JS(dbl_click_handler)

        self._annotations.append(ann)
        return self

    # ---- shading (dyShading) -----------------------------------------

    def shading(
        self,
        from_: Any,
        to: Any,
        color: str = "#EFEFEF",
        axis: Literal["x", "y"] = "x",
    ) -> Dygraph:
        """Add background shading (mirrors R ``dyShading``)."""
        if axis == "x" and self._format == "date":
            import pandas as pd

            if not isinstance(from_, str):
                from_ = pd.Timestamp(from_).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            if not isinstance(to, str):
                to = pd.Timestamp(to).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        self._shadings.append({"from": from_, "to": to, "color": color, "axis": axis})
        return self

    # ---- event (dyEvent) ---------------------------------------------

    def event(
        self,
        x: Any,
        label: str | None = None,
        *,
        label_loc: Literal["top", "bottom"] = "top",
        color: str = "black",
        stroke_pattern: str | list[int] = "dashed",
    ) -> Dygraph:
        """Add a vertical event line (mirrors R ``dyEvent``)."""
        if self._format == "date" and not isinstance(x, str):
            import pandas as pd

            x = pd.Timestamp(x).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        self._events.append(
            {
                "pos": x,
                "label": label,
                "labelLoc": label_loc,
                "color": color,
                "strokePattern": resolve_stroke_pattern(stroke_pattern),
                "axis": "x",
            }
        )
        return self

    # ---- limit (dyLimit) ---------------------------------------------

    def limit(
        self,
        value: float,
        label: str | None = None,
        *,
        label_loc: Literal["left", "right"] = "left",
        color: str = "black",
        stroke_pattern: str | list[int] = "dashed",
    ) -> Dygraph:
        """Add a horizontal limit line (mirrors R ``dyLimit``)."""
        self._events.append(
            {
                "pos": value,
                "label": label,
                "labelLoc": label_loc,
                "color": color,
                "strokePattern": resolve_stroke_pattern(stroke_pattern),
                "axis": "y",
            }
        )
        return self

    # ---- range selector (dyRangeSelector) ----------------------------

    def range_selector(
        self,
        date_window: tuple[Any, Any] | None = None,
        height: int = 40,
        fill_color: str = "#A7B1C4",
        stroke_color: str = "#808FAB",
        keep_mouse_zoom: bool = True,
        retain_date_window: bool = False,
    ) -> Dygraph:
        """Add a range selector widget (mirrors R ``dyRangeSelector``)."""
        opts: dict[str, Any] = {
            "showRangeSelector": True,
            "rangeSelectorHeight": height,
            "rangeSelectorPlotFillColor": fill_color,
            "rangeSelectorPlotStrokeColor": stroke_color,
        }
        if date_window is not None:
            if self._format == "date":
                import pandas as pd

                opts["dateWindow"] = [
                    pd.Timestamp(d).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    for d in date_window
                ]
            else:
                opts["dateWindow"] = list(date_window)
        if retain_date_window:
            opts["retainDateWindow"] = True
        if keep_mouse_zoom:
            opts["interactionModel"] = JS("Dygraph.Interaction.defaultModel")
        self._attrs = merge_dicts(self._attrs, opts)
        return self

    # ---- roller (dyRoller) -------------------------------------------

    def roller(
        self,
        show: bool = True,
        roll_period: int = 1,
    ) -> Dygraph:
        """Add rolling average control (mirrors R ``dyRoller``)."""
        self._attrs = merge_dicts(
            self._attrs,
            {"showRoller": show, "rollPeriod": roll_period},
        )
        return self

    # ---- callbacks (dyCallbacks) -------------------------------------

    def callbacks(
        self,
        *,
        click: str | None = None,
        draw: str | None = None,
        highlight: str | None = None,
        point_click: str | None = None,
        underlay: str | None = None,
        unhighlight: str | None = None,
        zoom: str | None = None,
        draw_highlight_point: str | None = None,
        draw_point: str | None = None,
        annotation_click: str | None = None,
        annotation_mouse_over: str | None = None,
        annotation_mouse_out: str | None = None,
        annotation_dbl_click: str | None = None,
    ) -> Dygraph:
        """Set JS callbacks (mirrors R ``dyCallbacks``)."""
        mapping = {
            "clickCallback": click,
            "drawCallback": draw,
            "highlightCallback": highlight,
            "pointClickCallback": point_click,
            "underlayCallback": underlay,
            "unhighlightCallback": unhighlight,
            "zoomCallback": zoom,
            "drawHighlightPointCallback": draw_highlight_point,
            "drawPointCallback": draw_point,
            "annotationClickHandler": annotation_click,
            "annotationMouseOverHandler": annotation_mouse_over,
            "annotationMouseOutHandler": annotation_mouse_out,
            "annotationDblClickHandler": annotation_dbl_click,
        }
        cb: dict[str, Any] = {}
        for js_name, val in mapping.items():
            if val is not None:
                cb[js_name] = JS(val)
        self._attrs = merge_dicts(self._attrs, cb)
        return self

    # ---- CSS (dyCSS) -------------------------------------------------

    def css(self, path: str | Path) -> Dygraph:
        """Apply custom CSS file (mirrors R ``dyCSS``)."""
        self._css = Path(path).read_text()
        return self

    # ---- plotters (Plotters) -----------------------------------------

    def bar_chart(self) -> Dygraph:
        """Bar chart plotter (mirrors R ``dyBarChart``)."""
        n_series = len(self._data) - 1
        if n_series > 1:
            js = _read_plotter("multicolumn")
            self._attrs["plotter"] = JS(js)
        else:
            js = _read_plotter("barchart")
            self._attrs["plotter"] = JS(js)
        self._extra_js.append(js)
        return self

    def stacked_bar_chart(self) -> Dygraph:
        """Stacked bar chart (mirrors R ``dyStackedBarChart``)."""
        js = _read_plotter("stackedbarchart")
        self._attrs["plotter"] = JS(js)
        self._extra_js.append(js)
        return self

    def multi_column(self) -> Dygraph:
        """Multi-column bar chart (mirrors R ``dyMultiColumn``)."""
        js = _read_plotter("multicolumn")
        self._attrs["plotter"] = JS(js)
        self._extra_js.append(js)
        return self

    def bar_series(self, name: str, **kwargs: Any) -> Dygraph:
        """Bar plotter for a single series (mirrors R ``dyBarSeries``)."""
        js = _read_plotter("barseries")
        return self.series(name, plotter=js, **kwargs)

    def stem_series(self, name: str, **kwargs: Any) -> Dygraph:
        """Stem plotter for a single series (mirrors R ``dyStemSeries``)."""
        js = _read_plotter("stemplot")
        return self.series(name, plotter=js, **kwargs)

    def shadow(self, name: str, **kwargs: Any) -> Dygraph:
        """Fill-only plotter for a single series (mirrors R ``dyShadow``)."""
        js = _read_plotter("fillplotter")
        return self.series(name, plotter=js, **kwargs)

    def filled_line(self, name: str, **kwargs: Any) -> Dygraph:
        """Filled line plotter for a single series (mirrors R ``dyFilledLine``)."""
        js = _read_plotter("filledline")
        return self.series(name, plotter=js, **kwargs)

    def error_fill(self, name: str, **kwargs: Any) -> Dygraph:
        """Error bar plotter for a single series (mirrors R ``dyErrorFill``)."""
        js = _read_plotter("errorplotter")
        return self.series(name, plotter=js, **kwargs)

    def candlestick(self) -> Dygraph:
        """Candlestick chart for OHLC data (mirrors R ``dyCandlestick``)."""
        js = _read_plotter("candlestick")
        self._attrs["plotter"] = JS(js)
        self._extra_js.append(js)
        return self

    def multi_column_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Multi-column on a subset of series (mirrors R ``dyMultiColumnGroup``)."""
        js = _read_plotter("multicolumngroup")
        return self.group(names, plotter=js, **kwargs)

    def candlestick_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Candlestick on a subset (mirrors R ``dyCandlestickGroup``)."""
        js = _read_plotter("candlestickgroup")
        return self.group(names, plotter=js, **kwargs)

    def stacked_bar_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Stacked bars on a subset (mirrors R ``dyStackedBarGroup``)."""
        js = _read_plotter("stackedbargroup")
        return self.group(names, plotter=js, **kwargs)

    def stacked_line_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Stacked lines on a subset (mirrors R ``dyStackedLineGroup``)."""
        js = _read_plotter("stackedlinegroup")
        return self.group(names, plotter=js, **kwargs)

    def stacked_ribbon_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Stacked ribbons on a subset (mirrors R ``dyStackedRibbonGroup``)."""
        js = _read_plotter("stackedribbongroup")
        return self.group(names, plotter=js, **kwargs)

    # ---- plugins (dyUnzoom, dyCrosshair, dyRibbon, dyRebase) ---------

    def unzoom(self) -> Dygraph:
        """Enable unzoom button plugin (mirrors R ``dyUnzoom``)."""
        self._plugins.append({"name": "Unzoom", "options": None})
        self._extra_js.append(_read_plugin("unzoom"))
        return self

    def crosshair(
        self,
        direction: Literal["both", "horizontal", "vertical"] = "both",
    ) -> Dygraph:
        """Enable crosshair plugin (mirrors R ``dyCrosshair``)."""
        self._plugins.append({"name": "Crosshair", "options": {"direction": direction}})
        self._extra_js.append(_read_plugin("crosshair"))
        return self

    def ribbon(
        self,
        data: list[float] | None = None,
        palette: list[str] | None = None,
        parser: str | None = None,
        top: float = 1.0,
        bottom: float = 0.0,
    ) -> Dygraph:
        """Enable ribbon plugin (mirrors R ``dyRibbon``)."""
        inner_opts: dict[str, Any] = {"top": top, "bottom": bottom}
        if palette is not None:
            inner_opts["palette"] = palette
        plugin_opts: dict[str, Any] = {"options": inner_opts}
        if data is not None:
            plugin_opts["data"] = data
        if parser is not None:
            plugin_opts["parser"] = JS(parser)
        self._plugins.append({"name": "Ribbon", "options": plugin_opts})
        self._extra_js.append(_read_plugin("ribbon"))
        return self

    def rebase(
        self,
        value: float = 100,
        percent: bool = False,
    ) -> Dygraph:
        """Enable rebase/straw-broom plugin (mirrors R ``dyRebase``)."""
        base: Any = "percent" if percent else value
        self._plugins.append({"name": "Rebase", "options": base})
        self._extra_js.append(_read_plugin("rebase"))
        return self

    # ---- serialisation -----------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the full dygraph config to a plain dict.

        This is the JSON payload that gets sent to the browser, equivalent
        to the ``x`` list in R's ``htmlwidgets::createWidget``.
        """
        x: dict[str, Any] = {
            "attrs": copy.deepcopy(self._attrs),
            "data": self._data,
            "format": self._format,
            "group": self._group,
            "annotations": self._annotations,
            "shadings": self._shadings,
            "events": self._events,
            "plugins": self._plugins,
        }
        if self._point_shapes:
            x["pointShape"] = self._point_shapes
        if self._css:
            x["css"] = self._css
        return x

    def to_json(self, **kwargs: Any) -> str:
        """Serialise to JSON, handling ``JS`` objects as raw strings."""

        def _default(obj: Any) -> Any:
            if isinstance(obj, JS):
                # Mark for post-processing
                return f"__JS__:{obj.code}:__JS__"
            msg = f"Object of type {type(obj)} is not JSON serializable"
            raise TypeError(msg)

        raw = json.dumps(self.to_dict(), default=_default, **kwargs)
        # Un-quote JS markers
        import re

        raw = re.sub(r'"__JS__:(.*?):__JS__"', r"\1", raw)
        return raw

    # ---- Dash integration --------------------------------------------

    def to_dash(
        self,
        app: Any = None,
        *,
        component_id: str | None = None,
        height: str | int = "400px",
        width: str = "100%",
        modebar: bool = True,
    ) -> Any:
        """Render into a Dash component tree.

        Parameters
        ----------
        app
            Dash app instance. If provided, clientside callbacks are
            auto-registered.
        component_id
            Unique DOM id prefix. Auto-generated if omitted.
        height, width
            CSS dimensions for the chart container.
        modebar
            Show overlay buttons (capture, reset zoom).

        Returns
        -------
        dash.html.Div
            Component ready to place in a Dash layout.
        """
        from pydygraphs.dash.component import dygraph_to_dash

        return dygraph_to_dash(
            self,
            app=app,
            component_id=component_id,
            height=height,
            width=width,
            modebar=modebar,
        )

    def to_shiny(
        self,
        element_id: str,
        *,
        height: str = "400px",
        width: str = "100%",
    ) -> Any:
        """Create Shiny UI components for this chart.

        Returns a ``TagList`` to include in your Shiny app's UI.
        Use ``render_dygraph(session, element_id, dg)`` in a reactive
        effect to send/update data.

        Requires ``pydygraphs[shiny]``.

        Parameters
        ----------
        element_id
            Unique DOM id for the chart container.
        height, width
            CSS dimensions.
        """
        from pydygraphs.shiny.component import dygraph_ui

        return dygraph_ui(element_id, height=height, width=width)

    # ---- to_html (standalone export) ---------------------------------

    def to_html(
        self,
        *,
        height: str | int = "400px",
        width: str = "100%",
        title: str | None = None,
        cdn: bool = True,
    ) -> str:
        """Render a self-contained HTML page with the dygraph chart.

        Useful for reports, emails, or embedding in iframes — no server
        needed.

        Parameters
        ----------
        height, width
            CSS dimensions for the chart container.
        title
            HTML ``<title>`` tag. Defaults to the chart title.
        cdn
            If True, load dygraphs from CDN. If False, inline the JS.
        """
        height_css = f"{height}px" if isinstance(height, int) else height
        page_title = title or self._attrs.get("title", "pydygraphs chart")
        config_json = self.to_json()

        if cdn:
            js_include = (
                '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/dygraph/2.2.1/dygraph.min.css">\n'
                '<script src="https://cdnjs.cloudflare.com/ajax/libs/dygraph/2.2.1/dygraph.min.js"></script>'
            )
        else:
            dygraph_js = (ASSETS_DIR / "dygraph-combined.js").read_text()
            dygraph_css = (ASSETS_DIR / "dygraph.css").read_text()
            js_include = f"<style>{dygraph_css}</style>\n<script>{dygraph_js}</script>"

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{page_title}</title>
{js_include}
</head><body>
<div id="chart" style="width:{width}; height:{height_css};"></div>
<script>
(function() {{
    var config = {config_json};
    var data = config.data;
    var nRows = data[0].length, nCols = data.length, rows = [];
    for (var i = 0; i < nRows; i++) {{
        var row = [];
        for (var j = 0; j < nCols; j++) {{
            var val = data[j][i];
            if (j === 0 && config.format === 'date' && typeof val === 'string') val = new Date(val);
            row.push(val);
        }}
        rows.push(row);
    }}
    var opts = config.attrs;
    var g = new Dygraph(document.getElementById('chart'), rows, opts);
    if (config.annotations && config.annotations.length > 0) {{
        g.setAnnotations(config.annotations.map(function(a) {{
            return {{
                series: a.series,
                x: config.format === 'date' ? new Date(a.x).getTime() : a.x,
                shortText: a.shortText, text: a.text || '',
                attachAtBottom: a.attachAtBottom || false
            }};
        }}));
    }}
}})();
</script></body></html>"""

    # ---- update (modify config) --------------------------------------

    def update(self, **kwargs: Any) -> Dygraph:
        """Apply declarative params or builder-style overrides to this chart.

        Accepts the same keyword arguments as the constructor's declarative
        params (``options``, ``axes``, ``series``, ``legend``, etc.).

        Returns self for chaining.
        """
        self._apply_declarative(**kwargs)
        return self

    # ---- copy --------------------------------------------------------

    def copy(self) -> Dygraph:
        """Return a deep copy of this Dygraph.

        Useful for forking a base config into variants.
        """
        return copy.deepcopy(self)

    # ---- from_csv (class method) -------------------------------------

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        **kwargs: Any,
    ) -> Dygraph:
        """Create a Dygraph from a CSV file path.

        Parameters
        ----------
        path
            Path to a CSV file. The first column is used as x-axis.
        **kwargs
            Passed to ``Dygraph()``.
        """
        csv_text = Path(path).read_text()
        return cls(csv_text, **kwargs)
