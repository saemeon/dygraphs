"""Core Dygraph builder — the main entry point for dash-dygraphs.

Ported from R ``dygraphs/R/dygraph.R`` + all dy* modifier functions.
"""

from __future__ import annotations

import contextlib
import copy
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from dygraphs.utils import (
    DYGRAPH_CSS_CDN,
    DYGRAPH_JS_CDN,
    JS,
    auto_colors,
    merge_dicts,
    resolve_stroke_pattern,
    unwrap_js_markers,
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
# Helpers
# ---------------------------------------------------------------------------


def _detect_scale(idx: Any) -> str:
    """Detect periodicity of a DatetimeIndex (mirrors R ``periodicity``).

    Returns one of: ``"yearly"``, ``"quarterly"``, ``"monthly"``,
    ``"weekly"``, ``"daily"``, ``"hourly"``, ``"minute"``, ``"seconds"``.
    """
    if len(idx) < 2:
        return "daily"
    import pandas as pd

    try:
        freq = idx.freq or pd.infer_freq(idx)
    except ValueError:
        freq = None
    if freq is not None:
        freq_str = str(freq).upper()
        if freq_str.startswith(("YE", "YS", "A", "BA", "BY")):
            return "yearly"
        if freq_str.startswith(("QE", "QS", "Q", "BQ")):
            return "quarterly"
        if freq_str.startswith(("ME", "MS", "M", "BM")):
            return "monthly"
        if freq_str.startswith("W"):
            return "weekly"
        if freq_str in ("B", "C") or freq_str.startswith(("D", "BD")):
            return "daily"
        if freq_str.startswith("H") or freq_str.startswith("BH"):
            return "hourly"
        if freq_str.startswith(("T", "MIN")):
            return "minute"
        if freq_str.startswith("S"):
            return "seconds"
    # Fallback: look at median gap
    diffs = idx[1:] - idx[:-1]
    median_ns = int(diffs.median().value) if len(diffs) > 0 else 86400 * 10**9
    seconds = median_ns / 10**9
    if seconds < 60:
        return "seconds"
    if seconds < 3600:
        return "minute"
    if seconds < 86400:
        return "hourly"
    if seconds < 7 * 86400:
        return "daily"
    if seconds < 28 * 86400:
        return "weekly"
    if seconds < 90 * 86400:
        return "monthly"
    if seconds < 366 * 86400:
        return "quarterly"
    return "yearly"


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

    Examples
    --------
    From a pandas DataFrame:

    >>> import pandas as pd
    >>> df = pd.DataFrame(
    ...     {"temp": [10, 12, 11], "rain": [5, 3, 7]},
    ...     index=pd.date_range("2024-01-01", periods=3),
    ... )
    >>> chart = Dygraph(df, title="Weather")

    From a plain dict:

    >>> chart = Dygraph({"x": [1, 2, 3], "y": [10, 20, 30]})

    Using the declarative API:

    >>> from dygraphs import Options, Series
    >>> chart = Dygraph(
    ...     df,
    ...     title="Weather",
    ...     options=Options(fill_graph=True),
    ...     series=[Series("temp", color="red")],
    ... )
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

        # Normalise data into (labels, columns, format, tzone, scale)
        labels, columns, fmt, tzone, scale = self._normalise_data(data)

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
        self._tzone: str | None = tzone  # IANA timezone or None
        self._scale: str | None = scale  # "yearly"/"monthly"/"daily"/etc.
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
        from dygraphs.declarative import _to_kwargs

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
    ) -> tuple[list[str], list[list[Any]], str, str | None, str | None]:
        """Return (labels, columns_as_lists, format_string, tzone, scale).

        *tzone* is the IANA timezone string (e.g. ``"US/Eastern"``) if the
        data has timezone-aware timestamps, else ``None``.
        *scale* is the detected periodicity (``"yearly"``, ``"quarterly"``,
        ``"monthly"``, ``"weekly"``, ``"daily"``, ``"hourly"``, ``"minute"``,
        ``"seconds"``) or ``None``.
        """
        try:
            import pandas as pd
        except ImportError:
            pd = None  # ty: ignore[invalid-assignment]  # type: ignore[assignment]

        # CSV string input
        if isinstance(data, str):
            if pd is None:
                msg = "pandas is required to parse CSV string data"
                raise ImportError(msg)
            import io

            try:
                data = pd.read_csv(io.StringIO(data))
            except Exception as exc:
                msg = f"Failed to parse CSV data: {exc}"
                raise ValueError(msg) from exc
            if data.empty or len(data.columns) < 2:
                msg = f"CSV data must have at least 2 columns (got {len(data.columns)})"
                raise ValueError(msg)
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

        if pd is not None and isinstance(data, pd.Series):
            data = data.to_frame()

        if pd is not None and isinstance(data, pd.DataFrame):
            idx = data.index
            tzone: str | None = None
            scale: str | None = None
            if isinstance(idx, pd.DatetimeIndex):
                # DatetimeIndex → ISO strings
                x_vals = [
                    t.isoformat() + "Z" if t.tzinfo is None else t.isoformat()
                    for t in idx
                ]
                fmt = "date"
                x_label = idx.name or "Date"
                # Detect timezone (R: tzone from xts)
                if idx.tz is not None:
                    tzone = str(idx.tz)
                # Detect scale/periodicity (R: periodicity)
                scale = _detect_scale(idx)
            else:
                x_vals = idx.tolist()
                fmt = "numeric"
                x_label = idx.name or "x"
            labels = [str(x_label)] + [str(c) for c in data.columns]
            columns: list[list[Any]] = [
                x_vals,
                *(data[col].tolist() for col in data.columns),
            ]
            return labels, columns, fmt, tzone, scale

        if isinstance(data, dict):
            keys = list(data.keys())
            if not keys:
                msg = "data dict must not be empty"
                raise ValueError(msg)
            fmt = "numeric"
            labels: list[str] = [str(k) for k in keys]
            columns: list[list[Any]] = [list(v) for v in data.values()]
            return labels, columns, fmt, None, None

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
                return labels, columns, fmt, None, None
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
            return labels, columns, fmt, None, None

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
        # Stacked graph NaN handling
        stacked_graph_nan_fill: Literal["all", "inside", "none"] | None = None,
        # Background fade animation
        animate_background_fade: bool = True,
        # Label sizing
        x_label_height: int | None = None,
        y_label_width: int | None = None,
        # Legend follow offsets
        legend_follow_offset_x: int | None = None,
        legend_follow_offset_y: int | None = None,
        # Range selector veil colour
        range_selector_veil_colour: str | None = None,
        # CSV parsing
        delimiter: str | None = None,
        x_value_parser: str | None = None,
        # Display annotations from data columns
        display_annotations: bool = False,
        # Custom data handler (advanced/undocumented)
        data_handler: str | None = None,
        # Mobile / timezone (R parity)
        mobile_disable_y_touch: bool = True,
        use_data_timezone: bool = False,
    ) -> Dygraph:
        """Set global chart options.

        Mirrors R ``dyOptions``.

        Parameters
        ----------
        stacked_graph : bool, optional
            If set, stack series on top of one another rather than
            drawing them independently. By default False.
        fill_graph : bool, optional
            Fill the area underneath the graph. Not compatible with
            error bars. Can also be set per-series. By default False.
        fill_alpha : float, optional
            Transparency for filled regions (0.0 = invisible,
            1.0 = as dark as the line). By default 0.15.
        step_plot : bool, optional
            Display as a step plot instead of a line plot. Can also
            be set per-series. By default False.
        stem_plot : bool, optional
            Display as a stem plot instead of a line plot. Can also
            be set per-series. By default False.
        draw_points : bool, optional
            Draw a small dot at each data point. Can also be set
            per-series. By default False.
        point_size : float, optional
            Size in pixels of the dot drawn at each point. Also
            controls the size of dots at isolated points.
            By default 1.0.
        point_shape : str, optional
            Shape of the dot drawn at each point. One of ``"dot"``,
            ``"triangle"``, ``"square"``, ``"diamond"``,
            ``"pentagon"``, ``"hexagon"``, ``"circle"``, ``"star"``,
            ``"plus"``, or ``"ex"``. By default ``"dot"``.
        draw_gap_edge_points : bool, optional
            Draw points at the edges of gaps in the data.
            By default False.
        connect_separated_points : bool, optional
            If True, connect points even when there are missing values
            in between (useful when different series have data at
            different x-values). By default False.
        stroke_width : float, optional
            Width in pixels of the lines connecting data points. Can
            also be set per-series. By default 1.0.
        stroke_pattern : str | list[int] | None, optional
            A predefined pattern (``"dotted"``, ``"dashed"``,
            ``"dotdash"``, ``"solid"``) or a custom array where even
            indices are draw lengths and odd are space lengths in
            pixels. Can also be set per-series. By default None
            (solid line).
        stroke_border_width : float | None, optional
            Draw a border around graph lines to make crossing lines
            more distinguishable. Can also be set per-series.
            By default None.
        stroke_border_color : str, optional
            Color for the line border when ``stroke_border_width`` is
            set. Can also be set per-series. By default ``"white"``.
        plotter : str | None, optional
            A JavaScript function (or array of functions) which plots
            each data series. May also be set per-series.
            By default None.
        colors : list[str] | None, optional
            Colors for the data series, e.g. ``"#AABBCC"``,
            ``"rgb(255,100,200)"``, or ``"yellow"``. If not specified,
            equally-spaced points around a colour wheel are used.
            By default None.
        color_value : float, optional
            Value component (0.0--1.0) of auto-generated series
            colours in HSV space. By default 0.5.
        color_saturation : float, optional
            Saturation component (0.0--1.0) of auto-generated series
            colours in HSV space. By default 1.0.
        draw_x_axis : bool, optional
            Whether to draw the x-axis. Setting to False also
            prevents x-axis ticks and reclaims the space.
            By default True.
        draw_y_axis : bool, optional
            Whether to draw the y-axis. Setting to False also
            prevents y-axis ticks and reclaims the space.
            By default True.
        include_zero : bool, optional
            Always include zero in the y-axis range, typically as the
            lowest value. By default False.
        draw_axes_at_zero : bool, optional
            Draw the X axis at Y=0 and the Y axis at X=0 if those
            positions are inside the visible area; otherwise draw at
            the edges as usual. By default False.
        logscale : bool, optional
            Show the y-axis in log scale. Values <= 0 are not
            displayed. By default False.
        axis_tick_size : float, optional
            Spacing between axis labels and tick marks.
            By default 3.0.
        axis_line_color : str, optional
            Color of x- and y-axis lines (CSS string).
            By default ``"black"``.
        axis_line_width : float, optional
            Thickness in pixels of x- and y-axis lines.
            By default 0.3.
        axis_label_color : str, optional
            Color for x- and y-axis labels (CSS string).
            By default ``"black"``.
        axis_label_font_size : int, optional
            Font size in pixels for axis labels.
            By default 14.
        axis_label_width : int, optional
            Width in pixels of the divs containing axis labels.
            By default 60.
        draw_grid : bool, optional
            Whether to display grid lines. Can also be set
            per-axis. By default True.
        grid_line_color : str | None, optional
            Color of grid lines. By default None.
        grid_line_width : float, optional
            Thickness in pixels of grid lines. By default 0.3.
        title_height : int | None, optional
            Height in pixels of the chart title; also controls its
            default font size. By default None.
        right_gap : int, optional
            Pixels of blank space at the right edge, making it
            easier to highlight the rightmost point.
            By default 5.
        digits_after_decimal : int, optional
            Number of digits after the decimal point in normal
            display mode. By default 2.
        labels_kmb : bool, optional
            Show K/M/B for thousands/millions/billions on y-axis.
            By default False.
        labels_kmg2 : bool, optional
            Show k/M/G for kilo/Mega/Giga on y-axis (base 2).
            By default False.
        labels_utc : bool, optional
            Show date/time labels in UTC instead of local time.
            Incompatible with ``use_data_timezone``.
            By default False.
        max_number_width : int, optional
            If a number has more than this many digits left of the
            decimal, switch to scientific notation. By default 6.
        sig_figs : int | None, optional
            Display a fixed number of significant figures instead of
            fixed decimal places. By default None.
        pan_edge_fraction : float | None, optional
            Farthest a graph may be panned, as a fraction of the
            display (e.g. 0.1 = 10%). None means no bounds.
            By default None.
        animated_zooms : bool, optional
            Animate the transition between zoom windows.
            By default False.
        disable_zoom : bool, optional
            Disable click-and-drag zooming. By default False.
        retain_date_window : bool, optional
            Keep the current zoom level when updating the chart
            with new data. By default False.
        error_bars : bool, optional
            Enable symmetric error bars. By default False.
        custom_bars : bool, optional
            Enable custom (asymmetric) bars. By default False.
        sigma : float | None, optional
            When ``error_bars`` is True, number of standard
            deviations to shade. By default None.
        fractions : bool, optional
            If True, values are interpreted as fractions and error
            bars are drawn using a Wilson confidence interval.
            By default False.
        wilson_interval : bool, optional
            Use a Wilson confidence interval when ``fractions`` is
            True. By default True.
        visibility : list[bool] | None, optional
            Array of booleans controlling per-series visibility.
            By default None.
        legend_formatter : str | None, optional
            JavaScript function to format legend values.
            By default None.
        range_selector_plot_line_width : float | None, optional
            Line width in the range selector mini plot.
            By default None.
        range_selector_plot_fill_gradient_color : str | None, optional
            Gradient color in the range selector fill.
            By default None.
        range_selector_background_line_width : float | None, optional
            Background line width in the range selector.
            By default None.
        range_selector_background_stroke_color : str | None, optional
            Background stroke color in the range selector.
            By default None.
        range_selector_foreground_stroke_color : str | None, optional
            Foreground stroke color in the range selector.
            By default None.
        range_selector_foreground_line_width : float | None, optional
            Foreground line width in the range selector.
            By default None.
        range_selector_alpha : float | None, optional
            Alpha transparency of the range selector.
            By default None.
        grid_line_pattern : list[int] | None, optional
            Custom dash pattern for grid lines. By default None.
        resizable : str | None, optional
            If set (e.g. ``"both"``), allow the chart to be
            resized by the user. By default None.
        pixel_ratio : float | None, optional
            Custom pixel ratio for high-DPI rendering.
            By default None.
        stacked_graph_nan_fill : {"all", "inside", "none"} or None, optional
            How to handle NaN in stacked graphs. By default None.
        animate_background_fade : bool, optional
            Animate the background fade effect. By default True.
        x_label_height : int | None, optional
            Height in pixels of the x-axis label.
            By default None.
        y_label_width : int | None, optional
            Width in pixels of the y-axis label.
            By default None.
        legend_follow_offset_x : int | None, optional
            Horizontal pixel offset for the follow legend.
            By default None.
        legend_follow_offset_y : int | None, optional
            Vertical pixel offset for the follow legend.
            By default None.
        range_selector_veil_colour : str | None, optional
            Color of the veil drawn over deselected areas of the
            range selector. By default None.
        delimiter : str | None, optional
            Delimiter for CSV data parsing. By default None.
        x_value_parser : str | None, optional
            JavaScript function to parse x-values from CSV.
            By default None.
        display_annotations : bool, optional
            Display annotations from data columns.
            By default False.
        data_handler : str | None, optional
            Custom JavaScript data handler. By default None.
        mobile_disable_y_touch : bool, optional
            Disable touch events on the Y axis for mobile devices
            to avoid interfering with scrolling.
            By default True.
        use_data_timezone : bool, optional
            Use the timezone of the underlying data for display.
            Incompatible with ``labels_utc``.
            By default False.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).options(
        ...     fill_graph=True,
        ...     draw_points=True,
        ...     colors=["#00d4aa", "#f4a261"],
        ...     stroke_width=2,
        ... )

        Enable stacked graph with grid styling:

        >>> chart = Dygraph(df).options(
        ...     stacked_graph=True,
        ...     grid_line_color="#ddd",
        ...     axis_label_font_size=12,
        ... )

        See Also
        --------
        axis : Per-axis configuration.
        series : Per-series configuration.
        """
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
        # Stacked graph NaN handling
        if stacked_graph_nan_fill is not None:
            opts["stackedGraphNaNFill"] = stacked_graph_nan_fill
        # Background fade
        if not animate_background_fade:
            opts["animateBackgroundFade"] = False
        # Label sizing
        if x_label_height is not None:
            opts["xLabelHeight"] = x_label_height
        if y_label_width is not None:
            opts["yLabelWidth"] = y_label_width
        # Legend follow offsets
        if legend_follow_offset_x is not None:
            opts["legendFollowOffsetX"] = legend_follow_offset_x
        if legend_follow_offset_y is not None:
            opts["legendFollowOffsetY"] = legend_follow_offset_y
        # Range selector veil colour
        if range_selector_veil_colour is not None:
            opts["rangeSelectorVeilColour"] = range_selector_veil_colour
        # CSV parsing
        if delimiter is not None:
            opts["delimiter"] = delimiter
        if x_value_parser is not None:
            opts["xValueParser"] = JS(x_value_parser)
        # Display annotations
        if display_annotations:
            opts["displayAnnotations"] = True
        # Custom data handler
        if data_handler is not None:
            opts["dataHandler"] = JS(data_handler)
        # Mobile / timezone
        if not mobile_disable_y_touch:
            opts["mobileDisableYTouch"] = False
        if use_data_timezone:
            opts["useDataTimezone"] = True

        # axes sub-options — merge into existing axis config to preserve
        # defaults like pixelsPerLabel set in the constructor.
        opts.setdefault("axes", {})
        opts["axes"].setdefault("x", {})
        opts["axes"]["x"]["drawAxis"] = draw_x_axis
        opts["axes"].setdefault("y", {})
        opts["axes"]["y"]["drawAxis"] = draw_y_axis

        # point shape
        if point_shape != "dot":
            if point_shape not in POINT_SHAPES:
                import warnings

                warnings.warn(
                    f"Unrecognised point_shape {point_shape!r}; "
                    f"standard shapes are {POINT_SHAPES}. "
                    f"Using it anyway (custom plotters may define extra shapes).",
                    stacklevel=2,
                )
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
        """Configure a specific axis.

        Mirrors R ``dyAxis``. Options that are not set explicitly use
        the global default from :meth:`options`.

        Parameters
        ----------
        name : {"x", "y", "y2"}
            Axis to configure.
        label : str | None, optional
            Label to display for the axis. By default None.
        value_range : tuple[float | None, float | None] | None, optional
            Explicitly set the range to ``(low, high)``. If either
            limit is None it is calculated automatically.
            By default None.
        logscale : bool | None, optional
            Show this axis in log scale. Values <= 0 are not
            displayed. Ignored for date-based x-axes.
            By default None.
        ticker : str | None, optional
            JavaScript function to generate custom tick marks.
            By default None.
        range_pad : float | None, optional
            Extra space in pixels around the value range to keep
            edge points visible. By default None.
        label_width : int | None, optional
            Width in pixels of the div containing the y-axis label
            (affects the rotated label's height).
            By default None.
        label_height : int | None, optional
            Height in pixels of the x-axis label div.
            By default None.
        axis_height : int | None, optional
            Height in pixels of the x-axis. Only applicable to the
            x-axis. By default None.
        axis_line_color : str | None, optional
            Color of the axis line (CSS string).
            By default None.
        axis_line_width : float | None, optional
            Thickness in pixels of the axis line.
            By default None.
        pixels_per_label : int | None, optional
            Minimum pixel spacing between axis labels. Larger values
            yield a sparser axis. By default None.
        axis_label_color : str | None, optional
            Color for axis labels (CSS string). By default None.
        axis_label_font_size : int | None, optional
            Font size in pixels for axis labels. By default None.
        axis_label_width : int | None, optional
            Width in pixels of axis labels. By default None.
        axis_label_formatter : str | None, optional
            JavaScript function to format tick values displayed on
            the axis. By default None.
        value_formatter : str | None, optional
            JavaScript function to format values shown on mouse-over.
            By default None.
        draw_grid : bool | None, optional
            Whether to display grid lines for this axis.
            By default None.
        grid_line_color : str | None, optional
            Color of grid lines for this axis. By default None.
        grid_line_width : float | None, optional
            Thickness in pixels of grid lines. By default None.
        independent_ticks : bool | None, optional
            Only valid for y and y2. When True, the axis has its
            own independent ticks; when False, ticks align to the
            other y-axis. By default None.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Raises
        ------
        ValueError
            If *name* is not one of ``"x"``, ``"y"``, ``"y2"``, or
            if *axis_height* is specified for a non-x axis.

        Examples
        --------
        >>> chart = Dygraph(df).axis("y", label="Temperature", value_range=(0, 40))

        Dual y-axis with independent ticks:

        >>> chart = Dygraph(df).axis(
        ...     "y2", label="Humidity", independent_ticks=True
        ... )

        See Also
        --------
        options : Global chart options.
        """
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
        highlight_circle_size: int | None = None,
        show_in_range_selector: bool | None = None,
        columns: list[str] | None = None,
    ) -> Dygraph:
        """Configure display options for a data series.

        Mirrors R ``dySeries``. Options not set explicitly use the
        global defaults from :meth:`options`.

        Parameters
        ----------
        name : str | None, optional
            Series name (must match a column label). If None, the
            first unprocessed series is used. By default None.
        label : str | None, optional
            Display label for the series. Uses *name* if not set.
            By default None.
        color : str | None, optional
            CSS color string (e.g. ``"#AABBCC"``, ``"rgb(255,100,200)"``,
            ``"yellow"``). If not specified, the global colour palette
            is used. By default None.
        axis : {"y", "y2"}, optional
            Y-axis to associate the series with.
            By default ``"y"``.
        step_plot : bool | None, optional
            Display as a step plot instead of a line plot.
            By default None.
        stem_plot : bool | None, optional
            Display as a stem plot instead of a line plot.
            By default None.
        fill_graph : bool | None, optional
            Fill the area underneath the series. Not compatible with
            error bars. By default None.
        draw_points : bool | None, optional
            Draw a small dot at each data point. By default None.
        point_size : float | None, optional
            Size in pixels of the dot drawn at each point.
            By default None.
        point_shape : str | None, optional
            Shape of the dot (see :meth:`options` for valid shapes).
            By default None.
        stroke_width : float | None, optional
            Width in pixels of the line connecting points.
            By default None.
        stroke_pattern : str | list[int] | None, optional
            A predefined pattern (``"dotted"``, ``"dashed"``,
            ``"dotdash"``, ``"solid"``) or a custom array of
            draw/space lengths. By default None.
        stroke_border_width : float | None, optional
            Border width around the line to make crossing lines
            more distinguishable. By default None.
        stroke_border_color : str | None, optional
            Color for the line border. By default None.
        plotter : str | None, optional
            JavaScript plotter function for this series.
            By default None.
        highlight_circle_size : int | None, optional
            Size in pixels of the circle drawn over a highlighted
            point. By default None.
        show_in_range_selector : bool | None, optional
            Whether to show this series in the range selector mini
            plot. By default None.
        columns : list[str] | None, optional
            For error bar series, pass 2 or 3 column names:

            - 2 names ``[value, error]`` -- symmetric error bars
              (sets ``errorBars=True``).
            - 3 names ``[low, mid, high]`` -- custom bars
              (sets ``customBars=True``).

            The columns are merged into a single series with tuple
            values and the consumed columns are removed.
            By default None.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).series("temp", color="red", stroke_width=2)

        Step plot with custom point shape:

        >>> chart = Dygraph(df).series(
        ...     "temp", step_plot=True, draw_points=True, point_shape="square"
        ... )

        Assign a series to the secondary y-axis:

        >>> chart = Dygraph(df).series("rain", axis="y2", color="blue")

        See Also
        --------
        group : Configure multiple series at once.
        options : Global chart options.
        """
        labels = self._attrs["labels"]

        # Handle error bar columns (R-style: dySeries(dg, c("low","mid","hi")))
        if columns is not None:
            if len(columns) not in (2, 3):
                msg = "columns must have 2 (value, error) or 3 (low, mid, high) names"
                raise ValueError(msg)
            for col in columns:
                if col not in labels:
                    msg = f"Column {col!r} not found. Valid: {labels[1:]}"
                    raise ValueError(msg)
            col_indices = [labels.index(c) for c in columns]
            n_rows = len(self._data[0]) if self._data else 0

            if len(columns) == 3:
                # Custom bars: [low, mid, high] → single column of [low, mid, high] tuples
                display_name = label or columns[1]  # middle column as display name
                i0, i1, i2 = col_indices
                merged = [
                    [self._data[i0][r], self._data[i1][r], self._data[i2][r]]
                    for r in range(n_rows)
                ]
                self._attrs["customBars"] = True
            else:
                # Error bars: [value, error] → single column of [value, error] tuples
                display_name = label or columns[0]
                i0, i1 = col_indices
                merged = [[self._data[i0][r], self._data[i1][r]] for r in range(n_rows)]
                self._attrs["errorBars"] = True

            # Remove consumed columns (in reverse order to keep indices stable)
            for idx in sorted(col_indices, reverse=True):
                self._data.pop(idx)
                labels.pop(idx)
            # Insert merged column
            labels.append(display_name)
            self._data.append(merged)

            # Use the display name as the series name going forward
            name = display_name

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
        if highlight_circle_size is not None:
            series_opts["highlightCircleSize"] = highlight_circle_size
        if show_in_range_selector is not None:
            series_opts["showInRangeSelector"] = show_in_range_selector

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
                import warnings

                warnings.warn(
                    f"Unrecognised point_shape {point_shape!r} for series "
                    f"{series_label!r}; standard shapes are {POINT_SHAPES}.",
                    stacklevel=2,
                )
            self._point_shapes[series_label] = point_shape

        return self

    # ---- group (dyGroup) ---------------------------------------------

    def group(
        self,
        names: list[str],
        *,
        label: list[str] | None = None,
        color: list[str] | None = None,
        axis: Literal["y", "y2"] = "y",
        step_plot: bool | None = None,
        stem_plot: bool | None = None,
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
        """Configure a group of series with shared options.

        Mirrors R ``dyGroup``. Options are applied uniformly across
        all named series. List arguments (``color``, ``label``,
        ``point_shape``) are cycled if shorter than *names*.

        Note: ``dyGroup`` turns off ``stackedGraph`` in R because
        stacking calculates cumulatives over all series, not just a
        subset.

        Parameters
        ----------
        names : list[str]
            Series names (must match column labels).
        label : list[str] | None, optional
            Display labels for each series. By default None.
        color : list[str] | None, optional
            Colors for each series (CSS strings). By default None.
        axis : {"y", "y2"}, optional
            Y-axis for all series in the group.
            By default ``"y"``.
        step_plot : bool | None, optional
            Display as step plots. By default None.
        stem_plot : bool | None, optional
            Display as stem plots. By default None.
        fill_graph : bool | None, optional
            Fill the area underneath each series. By default None.
        draw_points : bool | None, optional
            Draw a dot at each point. By default None.
        point_size : float | None, optional
            Size in pixels of each dot. By default None.
        point_shape : list[str] | None, optional
            Shapes for each series' dots. By default None.
        stroke_width : float | None, optional
            Line width in pixels. By default None.
        stroke_pattern : str | list[int] | None, optional
            Stroke pattern (see :meth:`options`). By default None.
        stroke_border_width : float | None, optional
            Border width around lines. By default None.
        stroke_border_color : str | None, optional
            Border color for lines. By default None.
        plotter : str | None, optional
            JavaScript plotter function for the group (used for
            grouped custom plotters like multi-column).
            By default None.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).group(
        ...     ["temp", "rain"], color=["red", "blue"], draw_points=True
        ... )

        See Also
        --------
        series : Configure a single series.
        """
        if len(names) == 1:
            return self.series(
                names[0], color=color[0] if color else None, plotter=plotter
            )

        labels = self._attrs["labels"]
        for n in names:
            if n not in labels:
                msg = f"Series {n!r} not found. Valid: {labels[1:]}"
                raise ValueError(msg)

        group_id = "\x1f".join(sorted(names))
        self._attrs.setdefault("series", {})

        # Resolve stem_plot plotter
        if stem_plot and plotter is not None:
            msg = "stem_plot provides its own plotter, cannot combine with plotter="
            raise ValueError(msg)
        if stem_plot:
            plotter = _STEM_PLOTTER_JS

        for i, n in enumerate(names):
            series_opts: dict[str, Any] = {"axis": axis, "group": group_id}
            if label is not None:
                series_opts["label"] = label[i % len(label)]
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
        """Configure the series legend.

        Mirrors R ``dyLegend``.

        Parameters
        ----------
        show : {"auto", "always", "onmouseover", "follow", "never"}, optional
            When to display the legend. ``"auto"`` shows ``"always"``
            when more than one series is plotted, ``"onmouseover"``
            for a single series. ``"follow"`` shows the legend as an
            overlay that follows the mouse. By default ``"auto"``.
        width : int, optional
            Width in pixels of the legend div. By default 250.
        show_zero_values : bool, optional
            Show zero-value labels in the legend. By default True.
        labels_div : str | None, optional
            ID of an external div to display data labels in, rather
            than on the graph. By default None.
        labels_separate_lines : bool, optional
            Put a line break between series labels. Often used with
            *labels_div*. By default False.
        hide_on_mouse_out : bool, optional
            Hide the legend when the mouse leaves the chart area.
            Also affects :meth:`highlight` hiding.
            By default True.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).legend(show="always")

        Floating legend that follows the mouse:

        >>> chart = Dygraph(df).legend(show="follow", width=200)

        See Also
        --------
        highlight : Mouse-over highlighting behaviour.
        """
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
        series_background_color: str | None = None,
        series_opts: dict[str, Any] | None = None,
        hide_on_mouse_out: bool = True,
    ) -> Dygraph:
        """Configure series mouse-over highlighting.

        Mirrors R ``dyHighlight``. Highlighting is always enabled;
        this method customises its appearance.

        Parameters
        ----------
        circle_size : int, optional
            Size in pixels of the dot drawn over highlighted points.
            By default 3.
        series_background_alpha : float, optional
            Fade the background while highlighting a series.
            1.0 = fully visible background (disable fading),
            0.0 = hidden background (show highlighted series only).
            By default 0.5.
        series_background_color : str | None, optional
            Background color used when fading non-highlighted series.
            By default None.
        series_opts : dict[str, Any] | None, optional
            Options applied to the series closest to the mouse
            pointer (e.g. ``{"strokeWidth": 3}``). See
            :meth:`series` for valid keys. By default None.
        hide_on_mouse_out : bool, optional
            Hide highlighting effects when the mouse leaves the
            chart area. Also affects :meth:`legend` hiding.
            By default True.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).highlight(
        ...     circle_size=5,
        ...     series_background_alpha=0.3,
        ...     series_opts={"strokeWidth": 3},
        ... )

        See Also
        --------
        legend : Legend display options.
        """
        opts: dict[str, Any] = {
            "highlightCircleSize": circle_size,
            "highlightSeriesBackgroundAlpha": series_background_alpha,
            "hideOverlayOnMouseOut": hide_on_mouse_out,
        }
        if series_background_color is not None:
            opts["highlightSeriesBackgroundColor"] = series_background_color
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
        tick_color: str | None = None,
        tick_width: int | None = None,
        attach_at_bottom: bool = False,
        icon: str | None = None,
        click_handler: str | None = None,
        mouse_over_handler: str | None = None,
        mouse_out_handler: str | None = None,
        dbl_click_handler: str | None = None,
        series: str | None = None,
    ) -> Dygraph:
        """Add a text annotation at a data point.

        Mirrors R ``dyAnnotation``. Annotations are bound to a
        specific series; if not specified, the last series is used.

        Parameters
        ----------
        x : Any
            Position on the x-axis (numeric or date/time value).
        text : str
            Short text to overlay on the chart at *x*.
        tooltip : str | None, optional
            Additional text displayed on mouse hover.
            By default None.
        width : int | None, optional
            Width in pixels of the annotation flag.
            By default None.
        height : int | None, optional
            Height in pixels of the annotation flag.
            By default None.
        css_class : str | None, optional
            CSS class for styling the annotation. By default None.
        tick_height : int | None, optional
            Height in pixels of the tick connecting the point to
            its flag or icon. By default None.
        tick_color : str | None, optional
            Color of the tick mark. By default None.
        tick_width : int | None, optional
            Width in pixels of the tick mark. By default None.
        attach_at_bottom : bool, optional
            If True, attach the annotation to the x-axis rather
            than to the actual data point. By default False.
        icon : str | None, optional
            URL of an icon to display instead of text.
            By default None.
        click_handler : str | None, optional
            JavaScript function called when the annotation is
            clicked. By default None.
        mouse_over_handler : str | None, optional
            JavaScript function called when the mouse hovers over
            the annotation. By default None.
        mouse_out_handler : str | None, optional
            JavaScript function called when the mouse exits the
            annotation. By default None.
        dbl_click_handler : str | None, optional
            JavaScript function called on double-click.
            By default None.
        series : str | None, optional
            Series to attach the annotation to. By default the last
            series in the data.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).annotation(
        ...     "2024-01-15", "A", tooltip="Anomaly detected"
        ... )

        Annotation on a specific series with custom styling:

        >>> chart = Dygraph(df).annotation(
        ...     "2024-02-01", "B",
        ...     series="temp",
        ...     tick_height=10,
        ...     attach_at_bottom=True,
        ... )

        See Also
        --------
        callbacks : Set annotation event handlers globally.
        """
        if self._format == "date":
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
        if tick_color is not None:
            ann["tickColor"] = tick_color
        if tick_width is not None:
            ann["tickWidth"] = tick_width
        if icon is not None:
            ann["icon"] = icon
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
        """Add a background shading region.

        Mirrors R ``dyShading``.

        Parameters
        ----------
        from_ : Any
            Start position (date/time or numeric).
        to : Any
            End position (date/time or numeric).
        color : str, optional
            Shading color (CSS string, e.g. ``"#AABBCC"`` or
            ``"yellow"``). By default ``"#EFEFEF"`` (light gray).
        axis : {"x", "y"}, optional
            Axis to apply shading along. By default ``"x"``.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).shading("2024-01-15", "2024-02-15")

        Colored shading with custom color:

        >>> chart = Dygraph(df).shading(
        ...     "2024-01-15", "2024-02-15", color="rgba(200,200,255,0.3)"
        ... )

        See Also
        --------
        event : Add a vertical event line.
        """
        if axis == "x" and self._format == "date":
            import pandas as pd

            from_ = pd.Timestamp(from_).strftime("%Y-%m-%dT%H:%M:%S.000Z")
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
        """Add a vertical event line.

        Mirrors R ``dyEvent``.

        Parameters
        ----------
        x : Any
            Position on the x-axis (numeric or date/time).
        label : str | None, optional
            Label displayed next to the event line.
            By default None.
        label_loc : {"top", "bottom"}, optional
            Vertical position of the label. By default ``"top"``.
        color : str, optional
            Color of the event line (CSS string).
            By default ``"black"``.
        stroke_pattern : str | list[int], optional
            A predefined pattern (``"dotted"``, ``"dashed"``,
            ``"dotdash"``, ``"solid"``) or a custom array of
            draw/space lengths. By default ``"dashed"``.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).event("2024-02-14", "Valentine's Day")

        Styled event line:

        >>> chart = Dygraph(df).event(
        ...     "2024-03-01", "Spring", color="#f76e8a", stroke_pattern="dotted"
        ... )

        See Also
        --------
        limit : Add a horizontal limit line.
        shading : Add a shaded region.
        """
        if self._format == "date":
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
        """Add a horizontal limit line.

        Mirrors R ``dyLimit``.

        Parameters
        ----------
        value : float
            Y-axis position of the limit line.
        label : str | None, optional
            Label displayed next to the line. By default None.
        label_loc : {"left", "right"}, optional
            Horizontal position of the label.
            By default ``"left"``.
        color : str, optional
            Color of the limit line (CSS string).
            By default ``"black"``.
        stroke_pattern : str | list[int], optional
            A predefined pattern (``"dotted"``, ``"dashed"``,
            ``"dotdash"``, ``"solid"``) or a custom array of
            draw/space lengths. By default ``"dashed"``.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> chart = Dygraph(df).limit(30.0, "Max")

        Right-aligned label with dotted line:

        >>> chart = Dygraph(df).limit(
        ...     25.0, "Threshold", label_loc="right", stroke_pattern="dotted"
        ... )

        See Also
        --------
        event : Add a vertical event line.
        """
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
        """Add an interactive range selector to the chart.

        Mirrors R ``dyRangeSelector``. Adds a mini-plot below the
        main chart that allows users to pan and zoom to various
        date/value ranges.

        Parameters
        ----------
        date_window : tuple[Any, Any] | None, optional
            Initially zoom in on a section of the graph, given as
            ``(earliest, latest)``. By default None (full range).
        height : int, optional
            Height in pixels of the range selector widget.
            By default 40.
        fill_color : str, optional
            Fill color for the range selector mini plot (CSS string).
            Use ``""`` to turn off fill. By default ``"#A7B1C4"``.
        stroke_color : str, optional
            Stroke color for the range selector mini plot (CSS
            string). Use ``""`` to turn off stroke.
            By default ``"#808FAB"``.
        keep_mouse_zoom : bool, optional
            Keep mouse zoom enabled when a range selector is active.
            By default True.
        retain_date_window : bool, optional
            Keep the current zoom level when updating with new data.
            By default False.

        Examples
        --------
        >>> chart = Dygraph(df).range_selector()

        With initial zoom window:

        >>> chart = Dygraph(df).range_selector(
        ...     date_window=("2024-01-10", "2024-01-20"), height=30
        ... )

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        opts: dict[str, Any] = {
            "showRangeSelector": True,
            "rangeSelectorHeight": height,
            "rangeSelectorPlotFillColor": fill_color,
            "rangeSelectorPlotStrokeColor": stroke_color,
        }
        if date_window is not None:
            if self._format == "date":
                import pandas as pd

                try:
                    opts["dateWindow"] = [
                        pd.Timestamp(d).strftime("%Y-%m-%dT%H:%M:%S.000Z")
                        for d in date_window
                    ]
                except Exception as exc:
                    msg = (
                        f"Cannot convert date_window values to timestamps: "
                        f"{date_window!r} — {exc}"
                    )
                    raise ValueError(msg) from exc
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
        """Add a rolling average period text box.

        Mirrors R ``dyRoller``. Displays a text box at the bottom
        left of the plot. Y-values are averaged over the specified
        number of time-scale units (e.g. days, months, years).

        Parameters
        ----------
        show : bool, optional
            Whether to show the roller text box. By default True.
        roll_period : int, optional
            Number of time-scale units to average values over.
            By default 1.

        Examples
        --------
        >>> chart = Dygraph(df).roller(roll_period=7)

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
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
        """Set JavaScript callbacks for dygraph events.

        Mirrors R ``dyCallbacks``. See the `dygraph options reference
        <https://dygraphs.com/options.html>`_ for callback signatures.

        Parameters
        ----------
        click : str | None, optional
            Called when the canvas is clicked. By default None.
        draw : str | None, optional
            Called every time the dygraph is drawn (initial draw,
            after zooming, and while panning). By default None.
        highlight : str | None, optional
            Called every time a new point is highlighted.
            By default None.
        point_click : str | None, optional
            Called when a data point is clicked. By default None.
        underlay : str | None, optional
            Called before the chart is drawn (useful for drawing
            on the canvas behind the chart). By default None.
        unhighlight : str | None, optional
            Called when the user stops highlighting any point
            by mousing out. By default None.
        zoom : str | None, optional
            Called when the zoom window changes. By default None.
        draw_highlight_point : str | None, optional
            Custom drawing for a highlighted point. Should draw
            within ``pointSize`` pixels from ``(cx, cy)``.
            By default None.
        draw_point : str | None, optional
            Custom drawing when ``drawPoints`` is enabled. Should
            draw within ``pointSize`` pixels from ``(cx, cy)``.
            By default None.
        annotation_click : str | None, optional
            Called when an annotation is clicked. Can also be set
            per-annotation. By default None.
        annotation_mouse_over : str | None, optional
            Called when the mouse hovers over an annotation.
            By default None.
        annotation_mouse_out : str | None, optional
            Called when the mouse exits an annotation.
            By default None.
        annotation_dbl_click : str | None, optional
            Called when an annotation is double-clicked.
            By default None.

        Returns
        -------
        Dygraph
            Self, for chaining.

        Examples
        --------
        >>> from dygraphs import JS
        >>> chart = Dygraph(df).callbacks(
        ...     click="function(e, x, pts) { console.log(x); }",
        ...     zoom="function(minDate, maxDate) { console.log(minDate, maxDate); }",
        ... )

        See Also
        --------
        annotation : Per-annotation event handlers.
        """
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
        """Apply a custom CSS file to the chart.

        Mirrors R ``dyCSS``. Styles are injected into the page and
        affect all dygraphs on the same page. See the `CSS
        documentation <https://dygraphs.com/css.html>`_ for
        available styles.

        Parameters
        ----------
        path : str | Path
            Path to a CSS file.

        Examples
        --------
        >>> chart = Dygraph(df).css("custom-dygraph.css")

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        self._css = Path(path).read_text()
        return self

    # ---- plotters (Plotters) -----------------------------------------

    def bar_chart(self) -> Dygraph:
        """Apply a bar chart plotter.

        Mirrors R ``dyBarChart``. Automatically selects a
        multi-column plotter when more than one data series exists.

        Examples
        --------
        >>> chart = Dygraph(df).bar_chart()

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        n_series = len(self._data) - 1
        if n_series > 1:
            js = _read_plotter("multicolumn")
            self._attrs["plotter"] = JS("Dygraph.Plotters.MultiColumn")
        else:
            js = _read_plotter("barchart")
            self._attrs["plotter"] = JS("Dygraph.Plotters.BarChart")
        self._extra_js.append(js)
        return self

    def stacked_bar_chart(self) -> Dygraph:
        """Apply a stacked bar chart plotter.

        Mirrors R ``dyStackedBarChart``.

        Examples
        --------
        >>> chart = Dygraph(df).stacked_bar_chart()

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("stackedbarchart")
        self._attrs["plotter"] = JS("Dygraph.Plotters.StackedBarChart")
        self._extra_js.append(js)
        return self

    def multi_column(self) -> Dygraph:
        """Apply a multi-column (grouped) bar chart plotter.

        Mirrors R ``dyMultiColumn``.

        Examples
        --------
        >>> chart = Dygraph(df).multi_column()

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("multicolumn")
        self._attrs["plotter"] = JS("Dygraph.Plotters.MultiColumn")
        self._extra_js.append(js)
        return self

    def bar_series(self, name: str, **kwargs: Any) -> Dygraph:
        """Apply a bar plotter to a single series.

        Mirrors R ``dyBarSeries``.

        Parameters
        ----------
        name : str
            Series name (must match a column label).
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`series`.

        Examples
        --------
        >>> chart = Dygraph(df).bar_series("rain")

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("barseries")
        self._extra_js.append(js)
        return self.series(name, plotter="barSeriesPlotter", **kwargs)

    def stem_series(self, name: str, **kwargs: Any) -> Dygraph:
        """Apply a stem plotter to a single series.

        Mirrors R ``dyStemSeries``.

        Parameters
        ----------
        name : str
            Series name (must match a column label).
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`series`.

        Examples
        --------
        >>> chart = Dygraph(df).stem_series("rain")

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("stemplot")
        self._extra_js.append(js)
        return self.series(name, plotter="stemPlotter", **kwargs)

    def shadow(self, name: str, **kwargs: Any) -> Dygraph:
        """Apply a fill-only (shadow) plotter to a single series.

        Mirrors R ``dyShadow``.

        Parameters
        ----------
        name : str
            Series name (must match a column label).
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`series`.

        Examples
        --------
        >>> chart = Dygraph(df).shadow("temp")

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("fillplotter")
        self._extra_js.append(js)
        return self.series(name, plotter="filledlineplotter", **kwargs)

    def filled_line(self, name: str, **kwargs: Any) -> Dygraph:
        """Apply a filled-line plotter to a single series.

        Mirrors R ``dyFilledLine``.

        Parameters
        ----------
        name : str
            Series name (must match a column label).
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`series`.

        Examples
        --------
        >>> chart = Dygraph(df).filled_line("temp")

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("filledline")
        self._extra_js.append(js)
        return self.series(name, plotter="filledlineplotter", **kwargs)

    def error_fill(self, name: str, **kwargs: Any) -> Dygraph:
        """Apply an error-bar fill plotter to a single series.

        Mirrors R ``dyErrorFill``.

        Parameters
        ----------
        name : str
            Series name (must match a column label).
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`series`.

        Examples
        --------
        >>> chart = Dygraph(data).error_fill("value")

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("errorplotter")
        self._extra_js.append(js)
        return self.series(name, plotter="errorplotter", **kwargs)

    def candlestick(self, *, compress: bool = False) -> Dygraph:
        """Apply a candlestick plotter for OHLC data.

        Mirrors R ``dyCandlestick``.

        Parameters
        ----------
        compress : bool, optional
            If True, auto-compress OHLC data at different zoom levels
            (yearly/quarterly/monthly/weekly/daily).
            By default False.

        Examples
        --------
        >>> chart = Dygraph(ohlc_df).candlestick()

        With auto-compression at different zoom levels:

        >>> chart = Dygraph(ohlc_df).candlestick(compress=True)

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("candlestick")
        self._attrs["plotter"] = JS("Dygraph.Plotters.CandlestickPlotter")
        self._extra_js.append(js)
        if compress:
            compress_js = _read_plugin("compress")
            self._extra_js.append(compress_js)
            self._attrs["dataHandler"] = JS("Dygraph.DataHandlers.CompressHandler")
        return self

    def multi_column_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Apply a multi-column plotter to a subset of series.

        Mirrors R ``dyMultiColumnGroup``.

        Parameters
        ----------
        names : list[str]
            Series names to include in the group.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`group`.

        Examples
        --------
        >>> chart = Dygraph(df).multi_column_group(["temp", "rain"])

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("multicolumngroup")
        self._extra_js.append(js)
        return self.group(names, plotter="multiColumnGroupPlotter", **kwargs)

    def candlestick_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Apply a candlestick plotter to a subset of series.

        Mirrors R ``dyCandlestickGroup``.

        Parameters
        ----------
        names : list[str]
            Series names to include in the group.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`group`.

        Examples
        --------
        >>> chart = Dygraph(df).candlestick_group(["open", "high", "low", "close"])

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("candlestickgroup")
        self._extra_js.append(js)
        return self.group(names, plotter="candlestickgroupPlotter", **kwargs)

    def stacked_bar_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Apply a stacked bar plotter to a subset of series.

        Mirrors R ``dyStackedBarGroup``.

        Parameters
        ----------
        names : list[str]
            Series names to include in the group.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`group`.

        Examples
        --------
        >>> chart = Dygraph(df).stacked_bar_group(["solar", "wind", "hydro"])

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("stackedbargroup")
        self._extra_js.append(js)
        return self.group(names, plotter="stackedBarPlotter", **kwargs)

    def stacked_line_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Apply a stacked line plotter to a subset of series.

        Mirrors R ``dyStackedLineGroup``.

        Parameters
        ----------
        names : list[str]
            Series names to include in the group.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`group`.

        Examples
        --------
        >>> chart = Dygraph(df).stacked_line_group(["solar", "wind", "hydro"])

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("stackedlinegroup")
        self._extra_js.append(js)
        return self.group(names, plotter="linePlotter", **kwargs)

    def stacked_ribbon_group(self, names: list[str], **kwargs: Any) -> Dygraph:
        """Apply a stacked ribbon plotter to a subset of series.

        Mirrors R ``dyStackedRibbonGroup``.

        Parameters
        ----------
        names : list[str]
            Series names to include in the group.
        **kwargs
            Additional keyword arguments forwarded to
            :meth:`group`.

        Examples
        --------
        >>> chart = Dygraph(df).stacked_ribbon_group(["solar", "wind", "hydro"])

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        js = _read_plotter("stackedribbongroup")
        self._extra_js.append(js)
        return self.group(names, plotter="linePlotter", **kwargs)

    # ---- plugins (dyUnzoom, dyCrosshair, dyRibbon, dyRebase) ---------

    def unzoom(self) -> Dygraph:
        """Enable the Unzoom button plugin.

        Mirrors R ``dyUnzoom``. Adds an "Unzoom" button to the chart
        when it is in a zoomed state (more discoverable than the
        default double-click gesture).

        Examples
        --------
        >>> chart = Dygraph(df).range_selector().unzoom()

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        self._plugins.append({"name": "Unzoom", "options": None})
        self._extra_js.append(_read_plugin("unzoom"))
        return self

    def crosshair(
        self,
        direction: Literal["both", "horizontal", "vertical"] = "both",
    ) -> Dygraph:
        """Enable the Crosshair plugin.

        Mirrors R ``dyCrosshair``. Draws a crosshair line over the
        point closest to the mouse when the user hovers over the
        chart.

        Parameters
        ----------
        direction : {"both", "horizontal", "vertical"}, optional
            Which crosshair lines to draw. By default ``"both"``.

        Examples
        --------
        >>> chart = Dygraph(df).crosshair(direction="vertical")

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
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
        """Enable the Ribbon plugin.

        Mirrors R ``dyRibbon``. Adds a horizontal band of colours
        running through the chart, useful for visualising categorical
        variables that change over time along the x-axis.

        Parameters
        ----------
        data : list[float] | None, optional
            Numeric values in the range 0--1 mapping to palette
            indices. By default None.
        palette : list[str] | None, optional
            Color palette for the ribbon bands.
            By default None.
        parser : str | None, optional
            JavaScript function ``(data, dygraph)`` returning an
            array of numeric values. Used if *data* is not provided.
            By default None.
        top : float, optional
            Vertical position (0--1) of the top edge of the ribbon,
            relative to chart height. By default 1.0.
        bottom : float, optional
            Vertical position (0--1) of the bottom edge of the
            ribbon, relative to chart height. By default 0.0.

        Examples
        --------
        >>> chart = Dygraph(df).ribbon(
        ...     data=[0, 1, 0, 1, 0],
        ...     palette=["green", "red"],
        ... )

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
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
        """Enable the Rebase (straw-broom) plugin.

        Mirrors R ``dyRebase``. Rebases all series so that they
        start from a common value, making it easier to compare
        relative changes.

        Parameters
        ----------
        value : float, optional
            Base value for rebasing (e.g. 100 for percentage
            comparison). By default 100.
        percent : bool, optional
            If True, rebase to percentage changes instead of an
            absolute value. By default False.

        Examples
        --------
        >>> chart = Dygraph(stocks_df).rebase(value=100)

        Rebase to percentage changes:

        >>> chart = Dygraph(stocks_df).rebase(percent=True)

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        base: Any = "percent" if percent else value
        self._plugins.append({"name": "Rebase", "options": base})
        self._extra_js.append(_read_plugin("rebase"))
        return self

    # ---- generic plugin/plotter/handler (R: dyPlugin, dyPlotter, dyDataHandler)

    def plugin(
        self,
        name: str,
        *,
        js: str | None = None,
        options: Any = None,
    ) -> Dygraph:
        """Register a custom dygraphs plugin.

        Mirrors R ``dyPlugin``.

        Parameters
        ----------
        name : str
            Plugin constructor name (e.g. ``"MyPlugin"``), must be
            accessible as ``Dygraph.Plugins[name]``.
        js : str | None, optional
            Raw JavaScript source that defines the plugin. Injected
            into the page before the chart is instantiated.
            By default None.
        options : Any, optional
            Plugin options passed to the constructor.
            By default None.

        Examples
        --------
        >>> js_code = Path("my-plugin.js").read_text()
        >>> chart = Dygraph(df).plugin("MyPlugin", js=js_code, options={"foo": 1})

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        self._plugins.append({"name": name, "options": options})
        if js is not None:
            self._extra_js.append(js)
        return self

    def custom_plotter(self, js: str) -> Dygraph:
        """Set a custom plotter from raw JavaScript.

        Mirrors R ``dyPlotter``.

        Parameters
        ----------
        js : str
            JavaScript source defining a plotter function. Can be
            an inline function expression or a named reference loaded
            via a ``<script>`` tag.

        Examples
        --------
        >>> chart = Dygraph(df).custom_plotter(
        ...     "function(e) { /* custom drawing */ }"
        ... )

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        self._attrs["plotter"] = JS(js)
        return self

    def data_handler(self, js: str) -> Dygraph:
        """Set a custom data handler from raw JavaScript.

        Mirrors R ``dyDataHandler``.

        Parameters
        ----------
        js : str
            JavaScript source defining a data handler.

        Examples
        --------
        >>> chart = Dygraph(df).data_handler(
        ...     "function(rawData, index, setName) { /* ... */ }"
        ... )

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        self._attrs["dataHandler"] = JS(js)
        return self

    # ---- series_data (R: dySeriesData) -----------------------------------

    def series_data(self, name: str, values: list[Any]) -> Dygraph:
        """Add auxiliary data for a series.

        Mirrors R ``dySeriesData``. Appends an extra column of data
        that can be referenced by custom formatters or plotters.

        Parameters
        ----------
        name : str
            Column label for the auxiliary data.
        values : list[Any]
            Data values (must be same length as existing columns).

        Examples
        --------
        >>> chart = Dygraph(df).series_data("smoothed", [10, 15, 20])

        Returns
        -------
        Dygraph
            Self, for chaining.
        """
        if self._data and len(values) != len(self._data[0]):
            msg = (
                f"values length ({len(values)}) must match existing data "
                f"length ({len(self._data[0])})"
            )
            raise ValueError(msg)
        self._attrs["labels"].append(name)
        self._data.append(list(values))
        return self

    # ---- serialisation -----------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise the full dygraph config to a plain dict.

        This is the JSON payload that gets sent to the browser, equivalent
        to the ``x`` list in R's ``htmlwidgets::createWidget``.

        Examples
        --------
        >>> config = Dygraph(df).options(fill_graph=True).to_dict()
        >>> config["attrs"]["fillGraph"]
        True
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
        # Timezone / scale (R: x$fixedtz, x$tzone, x$scale)
        if self._tzone:
            x["fixedtz"] = True
            x["tzone"] = self._tzone
        if self._scale:
            x["scale"] = self._scale
        if self._point_shapes:
            # R sends a plain string for global shapes, object for per-series.
            if list(self._point_shapes.keys()) == ["__global__"]:
                x["pointShape"] = self._point_shapes["__global__"]
            else:
                # Drop __global__ if present alongside per-series shapes
                x["pointShape"] = {
                    k: v for k, v in self._point_shapes.items() if k != "__global__"
                }
        if self._css:
            x["css"] = self._css
        if self._extra_js:
            x["extraJs"] = list(dict.fromkeys(self._extra_js))
        return x

    def to_json(self, **kwargs: Any) -> str:
        """Serialise to JSON, handling ``JS`` objects as raw strings.

        Examples
        --------
        >>> json_str = Dygraph(df).to_json(indent=2)
        """

        def _default(obj: Any) -> Any:
            if isinstance(obj, JS):
                # Mark for post-processing
                return f"__JS__:{obj.code}:__JS__"
            msg = f"Object of type {type(obj)} is not JSON serializable"
            raise TypeError(msg)

        raw = json.dumps(self.to_dict(), default=_default, **kwargs)
        return unwrap_js_markers(raw)

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

        Examples
        --------
        >>> from dash import Dash
        >>> app = Dash(__name__)
        >>> component = Dygraph(df).to_dash(app=app)

        Returns
        -------
        dash.html.Div
            Component ready to place in a Dash layout.
        """
        from dygraphs.dash.component import dygraph_to_dash

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

        Requires ``dygraphs[shiny]``.

        Parameters
        ----------
        element_id
            Unique DOM id for the chart container.
        height, width
            CSS dimensions.

        Examples
        --------
        >>> ui = Dygraph(df).to_shiny("my-chart")
        """
        from dygraphs.shiny.component import dygraph_ui

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

        Examples
        --------
        >>> html_str = Dygraph(df, title="Weather").to_html()
        >>> Path("chart.html").write_text(html_str)
        """
        height_css = f"{height}px" if isinstance(height, int) else height
        page_title = title or self._attrs.get("title", "dygraphs chart")
        config_json = self.to_json()

        # Force inline mode when plotters/plugins are used — they depend on
        # internal APIs (DygraphCanvasRenderer, Dygraph.Plotters) that the CDN
        # minified build doesn't expose.  R also bundles its own copy.
        use_cdn = cdn and not self._extra_js and not self._point_shapes
        if use_cdn:
            js_include = (
                f'<link rel="stylesheet" href="{DYGRAPH_CSS_CDN}">\n'
                f'<script src="{DYGRAPH_JS_CDN}"></script>'
            )
        else:
            dygraph_js = (ASSETS_DIR / "dygraph-combined.js").read_text()
            dygraph_css = (ASSETS_DIR / "dygraph.css").read_text()
            js_include = f"<style>{dygraph_css}</style>\n<script>{dygraph_js}</script>"

        extra_js_blocks = ""
        # Compatibility shim: CDN build may not expose Dygraph.Interaction or
        # Dygraph.Plotters namespaces that our bundled version and R both have.
        extra_js_blocks += (
            "<script>"
            "if(!Dygraph.Interaction)Dygraph.Interaction={};"
            "if(!Dygraph.Interaction.defaultModel)Dygraph.Interaction.defaultModel=Dygraph.defaultInteractionModel;"
            "if(!Dygraph.Interaction.nonInteractiveModel_)Dygraph.Interaction.nonInteractiveModel_=Dygraph.nonInteractiveModel_;"
            "if(!Dygraph.Plotters)Dygraph.Plotters={};"
            "</script>\n"
        )
        # Bundle moment.js + moment-timezone for date format charts
        # (R bundles these too — needed for timezone-aware formatting)
        if self._format == "date":
            moment_js = (ASSETS_DIR / "moment.min.js").read_text()
            moment_tz_js = (ASSETS_DIR / "moment-timezone.min.js").read_text()
            extra_js_blocks += f"<script>{moment_js}</script>\n"
            extra_js_blocks += f"<script>{moment_tz_js}</script>\n"
        # Inject shapes.js if point shapes are used (defines Dygraph.Circles)
        if self._point_shapes:
            shapes_js = (ASSETS_DIR / "shapes.js").read_text()
            extra_js_blocks += f"<script>{shapes_js}</script>\n"
        if self._extra_js:
            for js_code in dict.fromkeys(self._extra_js):
                extra_js_blocks += f"<script>{js_code}</script>\n"

        # The rendering JS below mirrors R's inst/htmlwidgets/dygraphs.js
        # as closely as possible to ensure identical behavior.
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{page_title}</title>
{js_include}
{extra_js_blocks}</head><body>
<div id="chart" style="width:{width}; height:{height_css};"></div>
<script>
(function() {{
    var el = document.getElementById('chart');
    var config = {config_json};

    // --- Transpose column-oriented data to row-oriented (R: HTMLWidgets.transposeArray2D) ---
    var data = config.data;
    var nRows = data[0].length, nCols = data.length, rows = [];
    for (var i = 0; i < nRows; i++) {{
        var row = [];
        for (var j = 0; j < nCols; j++) {{
            var val = data[j][i];
            if (j === 0 && config.format === 'date' && typeof val === 'string')
                val = new Date(val);
            row.push(val);
        }}
        rows.push(row);
    }}

    var opts = config.attrs;

    // --- normalizeDateValue (R: dygraphs.js lines 753-760) ---
    // For date-only scales (not hourly/minute/seconds) without fixedtz,
    // add timezone offset so dates display correctly in local time.
    function normalizeDateValue(scale, value, fixedtz) {{
        var date = new Date(value);
        if (scale !== 'minute' && scale !== 'hourly' && scale !== 'seconds' && !fixedtz) {{
            var localAsUTC = date.getTime() + (date.getTimezoneOffset() * 60000);
            date = new Date(localAsUTC);
        }}
        return date;
    }}

    // --- Date format setup (R: dygraphs.js lines 71-97) ---
    if (config.format === 'date') {{
        var scale = config.scale || 'daily';
        var fixedtz = config.fixedtz || false;
        var tzone = config.tzone || 'UTC';

        // Install timezone-aware formatters when fixedtz (R: lines 74-81)
        if (fixedtz && typeof moment !== 'undefined') {{
            if (!opts.axes) opts.axes = {{}};
            if (!opts.axes.x) opts.axes.x = {{}};
            if (opts.axes.x.axisLabelFormatter === undefined) {{
                opts.axes.x.axisLabelFormatter = (function(tz) {{
                    return function(date, granularity) {{
                        var m = moment(date).tz(tz);
                        if (granularity >= Dygraph.DECADAL) return m.format('YYYY');
                        if (granularity >= Dygraph.MONTHLY) return m.format('MMM YYYY');
                        var frac = m.hour()*3600 + m.minute()*60 + m.second() + m.millisecond();
                        if (frac === 0 || granularity >= Dygraph.DAILY) return m.format('DD MMM');
                        return m.second() ? m.format('HH:mm:ss') : m.format('HH:mm');
                    }};
                }})(tzone);
            }}
            if (opts.axes.x.valueFormatter === undefined) {{
                opts.axes.x.valueFormatter = (function(sc, tz) {{
                    return function(millis) {{
                        var m = moment(millis).tz(tz);
                        var za = ' (' + m.zoneAbbr() + ')';
                        if (sc === 'yearly') return m.format('YYYY') + za;
                        if (sc === 'monthly') return m.format('MMM, YYYY') + za;
                        if (sc === 'daily' || sc === 'weekly') return m.format('MMM DD, YYYY') + za;
                        return m.format('dddd, MMMM DD, YYYY HH:mm:ss') + za;
                    }};
                }})(scale, tzone);
            }}
            if (opts.axes.x.ticker === undefined) {{
                opts.axes.x.ticker = (function(tz) {{
                    return function(t, e, a, i, r) {{
                        var gran = Dygraph.pickDateTickGranularity(t, e, a, i);
                        if (gran < 0) return [];
                        var n = i('axisLabelFormatter');
                        var y = [];
                        var spacing = Dygraph.TICK_PLACEMENT[gran].spacing;
                        var d = moment(t).tz(tz);
                        d.millisecond(0);
                        var v = d.valueOf();
                        var m = moment(v).tz(tz);
                        for (; v <= e; v += spacing, m = moment(v).tz(tz)) {{
                            y.push({{v: v, label: n(m, gran, i, r)}});
                        }}
                        return y;
                    }};
                }})(tzone);
            }}
        }}

        // Default value formatter for non-fixedtz (R: lines 84-85, 427-447)
        if (!fixedtz) {{
            if (!opts.axes) opts.axes = {{}};
            if (!opts.axes.x) opts.axes.x = {{}};
            if (opts.axes.x.valueFormatter === undefined) {{
                var monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                opts.axes.x.valueFormatter = (function(sc) {{
                    return function(millis) {{
                        var d = new Date(millis);
                        if (sc === 'yearly') return '' + d.getFullYear();
                        if (sc === 'monthly') return monthNames[d.getMonth()] + ', ' + d.getFullYear();
                        if (sc === 'daily' || sc === 'weekly')
                            return monthNames[d.getMonth()] + ' ' + d.getDate() + ', ' + d.getFullYear();
                        return d.toLocaleString();
                    }};
                }})(scale);
            }}
        }}

        // Normalize data dates (R: lines 88-90)
        for (var k = 0; k < rows.length; k++) {{
            rows[k][0] = normalizeDateValue(scale, rows[k][0], fixedtz);
        }}

        // Normalize dateWindow (R: lines 91-96)
        if (opts.dateWindow) {{
            opts.dateWindow = opts.dateWindow.map(function(v) {{
                return normalizeDateValue(scale, v, fixedtz).getTime();
            }});
        }}
    }}

    opts.file = rows;

    // --- Resolve "auto" legend (R: dygraphs.js lines 64-69) ---
    if (opts.legend === 'auto') {{
        opts.legend = (data.length <= 2) ? 'onmouseover' : 'always';
    }}

    // --- disableZoom → nonInteractiveModel (R: dygraphs.js lines 53-55) ---
    if (opts.disableZoom) {{
        opts.interactionModel = Dygraph.Interaction.nonInteractiveModel_;
    }}

    // --- mobileDisableYTouch (R: dygraphs.js lines 112-122) ---
    if (opts.mobileDisableYTouch !== false && /Mobi|Android/i.test(navigator.userAgent)) {{
        if (!opts.interactionModel) {{
            opts.interactionModel = Dygraph.Interaction.defaultModel;
        }}
        var _origTouchstart = opts.interactionModel.touchstart;
        opts.interactionModel.touchstart = function(event, g, context) {{
            context.touchDirections = {{x: true, y: false}};
            if (_origTouchstart) _origTouchstart(event, g, context);
        }};
    }}

    // --- Shadings → underlayCallback (R: addShadingCallback, lines 519-565) ---
    if (config.shadings && config.shadings.length > 0) {{
        var prevUnderlayCallback = opts.underlayCallback;
        opts.underlayCallback = function(canvas, area, g) {{
            if (prevUnderlayCallback) prevUnderlayCallback(canvas, area, g);
            for (var i = 0; i < config.shadings.length; i++) {{
                var sh = config.shadings[i];
                canvas.save();
                canvas.fillStyle = sh.color;
                if (sh.axis === 'x') {{
                    var x1 = config.format === 'date' ? normalizeDateValue(config.scale, sh.from, config.fixedtz).getTime() : sh.from;
                    var x2 = config.format === 'date' ? normalizeDateValue(config.scale, sh.to, config.fixedtz).getTime() : sh.to;
                    var left = g.toDomXCoord(x1);
                    var right = g.toDomXCoord(x2);
                    canvas.fillRect(left, area.y, right - left, area.h);
                }} else if (sh.axis === 'y') {{
                    var bottom = g.toDomYCoord(sh.from);
                    var top = g.toDomYCoord(sh.to);
                    canvas.fillRect(area.x, bottom, area.w, top - bottom);
                }}
                canvas.restore();
            }}
        }};
    }}

    // --- Events/limits → underlayCallback chain (R: addEventCallback, lines 567-654) ---
    if (config.events && config.events.length > 0) {{
        var prevUnderlayCallback2 = opts.underlayCallback;
        opts.underlayCallback = function(canvas, area, g) {{
            if (prevUnderlayCallback2) prevUnderlayCallback2(canvas, area, g);
            for (var i = 0; i < config.events.length; i++) {{
                var ev = config.events[i];
                canvas.save();
                canvas.strokeStyle = ev.color || 'black';
                if (ev.axis === 'x') {{
                    var xPos = config.format === 'date'
                        ? g.toDomXCoord(normalizeDateValue(config.scale, ev.pos, config.fixedtz).getTime())
                        : g.toDomXCoord(ev.pos);
                    canvas.setLineDash(ev.strokePattern || [10, 5]);
                    canvas.beginPath();
                    canvas.moveTo(xPos, area.y);
                    canvas.lineTo(xPos, area.y + area.h);
                    canvas.stroke();
                }} else if (ev.axis === 'y') {{
                    var yPos = g.toDomYCoord(ev.pos);
                    canvas.setLineDash(ev.strokePattern || [10, 5]);
                    canvas.beginPath();
                    canvas.moveTo(area.x, yPos);
                    canvas.lineTo(area.x + area.w, yPos);
                    canvas.stroke();
                }}
                canvas.restore();
                // Draw label (R: rotated for x-axis, horizontal for y-axis)
                if (ev.label) {{
                    canvas.save();
                    canvas.fillStyle = ev.color || 'black';
                    canvas.font = '12px sans-serif';
                    var size = canvas.measureText(ev.label);
                    if (ev.axis === 'x') {{
                        // R rotates x-event labels 90 degrees (lines 636-639)
                        var tx = xPos - 4;
                        var ty = ev.labelLoc === 'bottom'
                            ? area.y + area.h - 10
                            : area.y + size.width + 10;
                        canvas.translate(tx, ty);
                        canvas.rotate(3 * Math.PI / 2);
                        canvas.translate(-tx, -ty);
                        canvas.fillText(ev.label, tx, ty);
                    }} else {{
                        var lx = ev.labelLoc === 'right'
                            ? area.x + area.w - size.width - 10
                            : area.x + 10;
                        canvas.fillText(ev.label, lx, yPos - 4);
                    }}
                    canvas.restore();
                }}
            }}
        }};
    }}

    // --- Zoom callback: track userDateWindow (R: addZoomCallback, lines 449-481) ---
    if (config.group) {{
        var prevZoomCallback = opts.zoomCallback;
        opts.zoomCallback = function(minDate, maxDate, yRanges) {{
            if (prevZoomCallback) prevZoomCallback(minDate, maxDate, yRanges);
            // Track whether zoom was user-initiated or shows full range
            var xAxisRange = this.xAxisRange();
            var xAxisExtremes = this.xAxisExtremes();
            if (xAxisRange[0] !== xAxisExtremes[0] || xAxisRange[1] !== xAxisExtremes[1]) {{
                this.userDateWindow = [minDate, maxDate];
            }} else {{
                this.userDateWindow = null;
            }}
            // Sync userDateWindow across group
            var group = window.__dyGroups[config.group] || [];
            for (var j = 0; j < group.length; j++) {{
                group[j].instance.userDateWindow = this.userDateWindow;
            }}
        }};
    }}

    // --- Group sync: drawCallback (R: addGroupDrawCallback, lines 483-516) ---
    if (config.group) {{
        if (!window.__dyGroups) window.__dyGroups = {{}};
        window.__dyGroups[config.group] = window.__dyGroups[config.group] || [];
        var blockRedraw = false;
        var prevDrawCallback = opts.drawCallback;
        opts.drawCallback = function(me, initial) {{
            if (prevDrawCallback) prevDrawCallback(me, initial);
            if (blockRedraw || initial) return;
            blockRedraw = true;
            var range = me.xAxisRange();
            var group = window.__dyGroups[config.group];
            for (var j = 0; j < group.length; j++) {{
                if (group[j].instance === me) continue;
                var peerRange = group[j].instance.xAxisRange();
                if (peerRange[0] !== range[0] || peerRange[1] !== range[1]) {{
                    group[j].instance.updateOptions({{dateWindow: range}});
                }}
            }}
            blockRedraw = false;
        }};
        // Highlight sync
        opts.highlightCallback = function(event, x, points, row) {{
            if (el._suppressHighlight) return;
            var group = window.__dyGroups[config.group];
            for (var j = 0; j < group.length; j++) {{
                if (group[j].el === el) continue;
                group[j].el._suppressHighlight = true;
                group[j].instance.setSelection(row);
                group[j].el._suppressHighlight = false;
            }}
        }};
        opts.unhighlightCallback = function() {{
            if (el._suppressHighlight) return;
            var group = window.__dyGroups[config.group];
            for (var j = 0; j < group.length; j++) {{
                if (group[j].el === el) continue;
                group[j].el._suppressHighlight = true;
                group[j].instance.clearSelection();
                group[j].el._suppressHighlight = false;
            }}
        }};
    }}

    // --- Plugins (R: dygraphs.js lines 125-138) ---
    if (config.plugins && config.plugins.length > 0) {{
        opts.plugins = [];
        for (var p = 0; p < config.plugins.length; p++) {{
            var pl = config.plugins[p];
            if (Dygraph.Plugins && Dygraph.Plugins[pl.name]) {{
                opts.plugins.push(new Dygraph.Plugins[pl.name](pl.options));
            }}
        }}
    }}

    // --- Point shapes (R: dygraphs.js lines 150-163) ---
    if (config.pointShape) {{
        var shapes = config.pointShape;
        if (typeof shapes === 'string') {{
            opts.drawPointCallback = Dygraph.Circles[shapes.toUpperCase()];
            opts.drawHighlightPointCallback = Dygraph.Circles[shapes.toUpperCase()];
        }} else {{
            if (!opts.series) opts.series = {{}};
            for (var sn in shapes) {{
                if (!shapes.hasOwnProperty(sn)) continue;
                if (!opts.series[sn]) opts.series[sn] = {{}};
                opts.series[sn].drawPointCallback = Dygraph.Circles[shapes[sn].toUpperCase()];
                opts.series[sn].drawHighlightPointCallback = Dygraph.Circles[shapes[sn].toUpperCase()];
            }}
        }}
    }}

    // --- CSS injection (R: dygraphs.js lines 200-208) ---
    if (config.css) {{
        var style = document.createElement('style');
        style.type = 'text/css';
        if (style.styleSheet) style.styleSheet.cssText = config.css;
        else style.appendChild(document.createTextNode(config.css));
        document.getElementsByTagName('head')[0].appendChild(style);
    }}

    // --- Create dygraph ---
    var dygraph = new Dygraph(el, opts.file, opts);

    // --- Register in group ---
    if (config.group) {{
        window.__dyGroups[config.group].push({{el: el, instance: dygraph}});
    }}

    // --- Annotations via ready() (R: dygraphs.js lines 244-253) ---
    if (config.annotations && config.annotations.length > 0) {{
        dygraph.ready(function() {{
            config.annotations.map(function(a) {{
                if (config.format === 'date')
                    a.x = normalizeDateValue(config.scale, a.x, config.fixedtz).getTime();
            }});
            dygraph.setAnnotations(config.annotations);
        }});
    }}

    // --- Resize handler (R: dygraphs.js lines 774-777) ---
    window.addEventListener('resize', function() {{ dygraph.resize(); }});
}})();
</script></body></html>"""

    # ---- update (modify config) --------------------------------------

    def update(self, **kwargs: Any) -> Dygraph:
        """Apply declarative params or builder-style overrides to this chart.

        Accepts the same keyword arguments as the constructor's declarative
        params (``options``, ``axes``, ``series``, ``legend``, etc.).

        Examples
        --------
        >>> chart = Dygraph(df)
        >>> chart.update(legend={"show": "follow"}, options={"fill_graph": True})

        Returns self for chaining.
        """
        self._apply_declarative(**kwargs)
        return self

    # ---- copy --------------------------------------------------------

    def copy(self) -> Dygraph:
        """Return a deep copy of this Dygraph.

        Useful for forking a base config into variants.

        Examples
        --------
        >>> base = Dygraph(df).options(fill_graph=True)
        >>> variant = base.copy().series("temp", color="red")
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

        Examples
        --------
        >>> chart = Dygraph.from_csv("data.csv", title="My Data")
        """
        csv_text = Path(path).read_text()
        return cls(csv_text, **kwargs)
