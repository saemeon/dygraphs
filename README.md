# dygraphs

Python wrapper for the [dygraphs](https://dygraphs.com) JavaScript charting library.

**Core port of the R [dygraphs](https://rstudio.github.io/dygraphs/) package** — **all 37** exported R `dy*` functions plus the `dygraph()` constructor are ported to a Pythonic builder API (100% function-level parity). The R package (by RStudio/JJ Allaire) is the most mature dygraphs wrapper in any language; dygraphs faithfully ports its API design, data model, and test coverage to Python.

Framework-agnostic core with adapters for [Plotly Dash](https://dash.plotly.com/) and [Shiny for Python](https://shiny.posit.co/py/).

## Features

- **Two API styles**: builder chaining (`Dygraph(df).options(...).series(...)`) and declarative (`Dygraph(df, options=Options(...), series=[Series(...)])`) — both produce identical output
- **Full R port + full JS coverage**: options, axes, series, legend, highlight, annotations, shadings, events, limits, range selector, roller, callbacks — every documented and undocumented dygraph option is exposed
- **Advanced plotters**: bar chart, stacked bar, candlestick, multi-column, stem, filled line, error fill + group variants
- **Plugins**: unzoom, crosshair, ribbon, rebase, plus `.plugin()` and `.dependency()` for arbitrary external JS/CSS
- **Error bars**: symmetric, custom (low/mid/high), fractions with Wilson intervals — also via R-style `dySeries(c("lwr","fit","upr"))` shortcut: `.series(["lwr","fit","upr"])`
- **Zoom sync** across multiple charts (line + stacked bar) with debounced range-selector panning
- **Stacked bar chart** with interactive canvas range selector
- **Jupyter / IPython auto-display** — `_repr_html_` makes charts render inline as the last expression in a cell, same UX as `dygraph()` in RStudio's viewer
- **Modebar overlay** (Plotly-style) with PNG download and reset zoom buttons
- **Standalone HTML export** via `.to_html()` — no server needed
- **dash-capture compatible** via `dygraph_strategy()`
- **Framework-agnostic**: core builder has zero Dash/Shiny imports
- **Flexible data input**: DataFrame, Series, dict, list, numpy array, CSV string, CSV file
- **Type-safe**: full type hints, `py.typed`, passes `ty` and `ruff`

## Installation

```bash
pip install dygraphs            # core only
pip install dygraphs[dash]      # + Plotly Dash adapter
pip install dygraphs[shiny]     # + Shiny for Python adapter
```

## Quick Start

### Builder API (chaining)

```python
import pandas as pd
from dygraphs import Dygraph

df = pd.DataFrame(
    {"temp": [10, 12, 11, 14, 13], "rain": [5, 3, 7, 2, 6]},
    index=pd.date_range("2024-01-01", periods=5, freq="D"),
)

chart = (
    Dygraph(df, title="Weather")
    .options(fill_graph=True, draw_points=True, colors=["#00d4aa", "#f4a261"])
    .axis("y", label="Value")
    .series("temp", stroke_width=2)
    .legend(show="always")
    .range_selector(height=30)
)
```

### Declarative API

```python
from dygraphs import Dygraph, Options, Series, Axis, Legend, RangeSelector

chart = Dygraph(
    df,
    title="Weather",
    options=Options(fill_graph=True, draw_points=True, colors=["#00d4aa", "#f4a261"]),
    axes=[Axis("y", label="Value")],
    series=[Series("temp", stroke_width=2)],
    legend=Legend(show="always"),
    range_selector=RangeSelector(height=30),
)
```

Dicts work too — mix freely:

```python
chart = Dygraph(
    df,
    title="Weather",
    options={"fill_graph": True},
    series=[Series("temp", color="red"), {"name": "rain", "axis": "y2"}],
)
```

### Render in Dash

```python
from dash import Dash, html
app = Dash(__name__)
app.layout = html.Div([chart.to_dash()])
```

### Render in Shiny

```python
from dygraphs.shiny import dygraph_ui, render_dygraph

# In UI:
dygraph_ui("my-chart")

# In server:
await render_dygraph(session, "my-chart", chart)
```

### Standalone HTML

```python
html_string = chart.to_html()
Path("chart.html").write_text(html_string)
```

### Jupyter / IPython

A `Dygraph` is its own display object. Make it the last expression in
a cell and Jupyter renders it inline:

```python
chart  # auto-displays via _repr_html_
```

For non-last-expression contexts (loops, after side-effecting lines)
use the explicit helper:

```python
chart.show()  # uses IPython.display.HTML
```

## Data Input

| Format | Example |
|--------|---------|
| pandas DataFrame | `pd.DataFrame({"y": [1,2,3]}, index=pd.date_range(...))` |
| pandas Series | `pd.Series([1,2,3], name="y")` |
| dict | `{"x": [1,2,3], "y": [10,20,30]}` |
| list of rows | `[[1, 10], [2, 20], [3, 30]]` |
| numpy array | `np.array([[1, 10], [2, 20]])` |
| CSV string | `"Date,A,B\n2024-01-01,1,2\n..."` |
| CSV file | `Dygraph.from_csv("data.csv")` |

## Utility Methods

```python
chart.update(legend={"show": "follow"})  # modify config after construction
forked = chart.copy()                     # deep copy for variants
config = chart.to_dict()                  # plain dict (framework-agnostic)
json_str = chart.to_json()                # JSON with JS functions
```

## Error Bars

```python
from dygraphs import Dygraph, make_error_bar_data

data = make_error_bar_data(x=[1,2,3], y=[10,20,30], error=[1,2,3])
chart = Dygraph(data, options={"error_bars": True})
```

## Syncing Multiple Charts

Charts with the same `group` name automatically sync zoom, pan, and highlight:

```python
from dygraphs import Dygraph, stacked_bar

chart_a = Dygraph(df1, group="sync").range_selector().to_dash(component_id="a")
chart_b = Dygraph(df2, group="sync").range_selector().to_dash(component_id="b")
chart_c = stacked_bar("c", csv_data, title="Stacked Bar", group="sync")

app.layout = html.Div([chart_a, chart_b, chart_c])
```

The constructor's `group=` kwarg has a chainable equivalent for fluent
builders: `Dygraph(df).sync_group("sync")`. **Not to be confused with**
`.group([names])`, which is the unrelated `dyGroup` port for styling
a list of series together within a *single* chart.

## Periodicity override

By default, dygraphs auto-detects the time scale from a `DatetimeIndex`
(daily, monthly, yearly, etc.). For irregular data or to force a
specific scale, pass `periodicity=`:

```python
# Force monthly even if the index has finer granularity
chart = Dygraph(df, title="Monthly view", periodicity="monthly")
```

Accepted values mirror R's `xts::periodicity$scale`: `"yearly"`,
`"quarterly"`, `"monthly"`, `"weekly"`, `"daily"`, `"hourly"`,
`"minute"`, `"seconds"`, `"milliseconds"`. Default `None` = auto.

## External plugin assets

Use `.dependency()` to attach external JavaScript / CSS files to a
chart — the Python equivalent of R's `dyDependency(htmlDependency(...))`.
Files are read eagerly and inlined as `<script>` / `<style>` tags in
`to_html()` output:

```python
chart = (
    Dygraph(df)
    .dependency(
        "Dygraph.Plugins.MyPlugin",
        version="1.2",
        src="plugins/",
        script="my-plugin.js",
        stylesheet="my-plugin.css",
    )
)
```

## Dynamic Updates (Dash)

Each chart created with `DyGraph` (or `dygraph_to_dash` / `Dygraph.to_dash`)
is backed by two `dcc.Store` components. The data store shares the chart's
`id`, so you can target it directly with standard Dash `Output`:

```python
import dash
from dash import Input, Output
from dygraphs import Dygraph

# Pushing a fresh config (data + attrs) → full destroy+recreate
@dash.callback(Output("my-chart", "data"), Input("refresh", "n_clicks"))
def refresh(_n):
    return Dygraph(new_df).to_dict()

# Pushing runtime overrides → merged on top of the existing config
@dash.callback(Output("my-chart-opts", "data"), Input("toggle", "value"))
def toggle(v):
    return {"strokeWidth": 3 if v else 1}
```

The chart is always destroyed and recreated on every config update (R
`htmlwidgets` model); pass `retain_date_window=True` to `.options()` if you
need the user's zoom preserved across updates.

## Capture (dash-capture)

```python
from dygraphs import dygraph_strategy
from dash_capture import capture_element

capture_element(app, "btn", "chart-container", "img-store",
                strategy=dygraph_strategy(hide_range_selector=True))
```

## API Reference

### Builder Methods

| Method | R Equivalent | Description |
|--------|-------------|-------------|
| `Dygraph(data, ...)` | `dygraph()` | Create chart (also accepts `periodicity=`) |
| `.options(...)` | `dyOptions()` | Global options |
| `.axis(name, ...)` | `dyAxis()` | Per-axis config |
| `.series(name, ...)` | `dySeries()` | Per-series config (accepts `[names]` for error bands) |
| `.group(names, ...)` | `dyGroup()` | Group of series — shared display options |
| `.sync_group(name)` | — | Cross-chart sync alias for `group=` kwarg |
| `.legend(...)` | `dyLegend()` | Legend options |
| `.highlight(...)` | `dyHighlight()` | Highlight behavior |
| `.annotation(x, text)` | `dyAnnotation()` | Data annotations |
| `.shading(from_, to)` | `dyShading()` | Background regions |
| `.event(x, label)` | `dyEvent()` | Vertical event lines |
| `.limit(value, label)` | `dyLimit()` | Horizontal limit lines |
| `.range_selector(...)` | `dyRangeSelector()` | Range selector |
| `.roller(...)` | `dyRoller()` | Rolling average |
| `.callbacks(...)` | `dyCallbacks()` | JS callbacks |
| `.css(css)` | `dyCSS()` | Custom CSS — accepts a file path or raw CSS string |
| `.plugin(name, js, options)` | `dyPlugin()` | Register a custom dygraphs plugin |
| `.dependency(name, ...)` | `dyDependency()` | Attach external JS / CSS files |
| `.custom_plotter(js)` | `dyPlotter()` | Set a custom JS plotter |
| `.data_handler(js)` | `dyDataHandler()` | Set a custom JS data handler |
| `.series_data(name, values)` | `dySeriesData()` | Add an auxiliary data column |
| `.update(...)` | — | Modify config post-construction |
| `.copy()` | — | Deep copy for forking variants |
| `.show()` | — | Render in Jupyter via `IPython.display` |
| `.to_dash()` | — | Dash component |
| `.to_shiny(id)` | — | Shiny component |
| `.to_html()` | — | Standalone HTML page |
| `.to_dict()` | — | Plain dict (framework-agnostic) |
| `.to_json()` | — | JSON string (with JS markers preserved) |
| `Dygraph.from_csv(path)` | — | Load from CSV file |

### Declarative Dataclasses

`Options`, `Axis`, `Series`, `Legend`, `Highlight`, `Annotation`, `Shading`, `Event`, `Limit`, `RangeSelector`, `Roller`, `Callbacks`

All accept the same parameters as their builder counterparts. Pass as dataclass or dict.

### Plotters

`.bar_chart()`, `.stacked_bar_chart()`, `.multi_column()`, `.candlestick()`, `.bar_series(name)`, `.stem_series(name)`, `.shadow(name)`, `.filled_line(name)`, `.error_fill(name)` + group variants

Also via constructor: `Dygraph(df, plotter="bar_chart")`

### Plugins

`.unzoom()`, `.crosshair(direction)`, `.ribbon(data, palette)`, `.rebase(value, percent)`

## Full Options Reference

### `.options(...)` / `Options(...)`

| Parameter | JS Option | Description |
|-----------|-----------|-------------|
| `stacked_graph` | `stackedGraph` | Stack series on top of each other |
| `stacked_graph_nan_fill` | `stackedGraphNaNFill` | NaN handling in stacked graphs (`"all"`, `"inside"`, `"none"`) |
| `fill_graph` | `fillGraph` | Fill area under graph |
| `fill_alpha` | `fillAlpha` | Fill transparency (0–1) |
| `step_plot` | `stepPlot` | Step plot instead of line |
| `stem_plot` | — | Stem plot (custom plotter) |
| `draw_points` | `drawPoints` | Draw dots at data points |
| `point_size` | `pointSize` | Dot size in pixels |
| `point_shape` | — | Dot shape (`"dot"`, `"triangle"`, `"square"`, etc.) |
| `draw_gap_edge_points` | `drawGapEdgePoints` | Draw points at data gaps |
| `connect_separated_points` | `connectSeparatedPoints` | Connect across missing values |
| `stroke_width` | `strokeWidth` | Line width |
| `stroke_pattern` | `strokePattern` | Dash pattern (`"dashed"`, `"dotted"`, or `[on, off]`) |
| `stroke_border_width` | `strokeBorderWidth` | Border around lines |
| `stroke_border_color` | `strokeBorderColor` | Border color |
| `plotter` | `plotter` | Custom JS plotter function |
| `colors` | `colors` | List of series colors |
| `color_value` | `colorValue` | HSV value for auto-colors |
| `color_saturation` | `colorSaturation` | HSV saturation for auto-colors |
| `draw_x_axis` | `axes.x.drawAxis` | Show x axis |
| `draw_y_axis` | `axes.y.drawAxis` | Show y axis |
| `include_zero` | `includeZero` | Y-axis includes zero |
| `draw_axes_at_zero` | `drawAxesAtZero` | Draw axes at zero position |
| `logscale` | `logscale` | Logarithmic scale |
| `axis_tick_size` | `axisTickSize` | Tick mark size |
| `axis_line_color` | `axisLineColor` | Axis line color |
| `axis_line_width` | `axisLineWidth` | Axis line width |
| `axis_label_color` | `axisLabelColor` | Axis label color |
| `axis_label_font_size` | `axisLabelFontSize` | Axis label font size |
| `axis_label_width` | `axisLabelWidth` | Axis label width |
| `draw_grid` | `drawGrid` | Show gridlines |
| `grid_line_color` | `gridLineColor` | Grid color |
| `grid_line_width` | `gridLineWidth` | Grid width |
| `grid_line_pattern` | `gridLinePattern` | Grid dash pattern |
| `title_height` | `titleHeight` | Title area height |
| `right_gap` | `rightGap` | Right margin pixels |
| `x_label_height` | `xLabelHeight` | X-axis label height |
| `y_label_width` | `yLabelWidth` | Y-axis label width |
| `digits_after_decimal` | `digitsAfterDecimal` | Decimal places |
| `max_number_width` | `maxNumberWidth` | Scientific notation threshold |
| `sig_figs` | `sigFigs` | Fixed significant figures |
| `labels_kmb` | `labelsKMB` | k/M/B notation |
| `labels_kmg2` | `labelsKMG2` | Ki/Mi/Gi notation |
| `labels_utc` | `labelsUTC` | UTC dates |
| `pan_edge_fraction` | `panEdgeFraction` | Max pan distance fraction |
| `animated_zooms` | `animatedZooms` | Animate zoom transitions |
| `animate_background_fade` | `animateBackgroundFade` | Highlight background animation |
| `disable_zoom` | `disableZoom` | Disable zooming |
| `retain_date_window` | `retainDateWindow` | Keep zoom on data update |
| `error_bars` | `errorBars` | Enable error bars |
| `custom_bars` | `customBars` | Low/mid/high format |
| `sigma` | `sigma` | Standard deviations |
| `fractions` | `fractions` | Fraction format |
| `wilson_interval` | `wilsonInterval` | Wilson confidence intervals |
| `visibility` | `visibility` | Series visibility list |
| `legend_formatter` | `legendFormatter` | Custom JS legend formatter |
| `legend_follow_offset_x` | `legendFollowOffsetX` | Floating legend X offset |
| `legend_follow_offset_y` | `legendFollowOffsetY` | Floating legend Y offset |
| `range_selector_*` | `rangeSelector*` | Range selector fine styling (7 options) |
| `range_selector_veil_colour` | `rangeSelectorVeilColour` | Range selector veil fill color |
| `resizable` | `resizable` | Add resize handles |
| `pixel_ratio` | `pixelRatio` | Pixel ratio scaling |
| `delimiter` | `delimiter` | CSV field separator |
| `x_value_parser` | `xValueParser` | Custom JS x-value parser |
| `display_annotations` | `displayAnnotations` | Interpret columns as annotations |
| `data_handler` | `dataHandler` | Custom JS data handler |

### `.series(...)` / `Series(...)`

| Parameter | JS Option | Description |
|-----------|-----------|-------------|
| `color` | `color` | Series color |
| `axis` | `axis` | Assign to `"y"` or `"y2"` |
| `step_plot` | `stepPlot` | Step plot for this series |
| `fill_graph` | `fillGraph` | Fill under this series |
| `draw_points` | `drawPoints` | Draw dots for this series |
| `point_size` | `pointSize` | Dot size |
| `point_shape` | — | Dot shape |
| `stroke_width` | `strokeWidth` | Line width |
| `stroke_pattern` | `strokePattern` | Dash pattern |
| `stroke_border_width` | `strokeBorderWidth` | Border width |
| `stroke_border_color` | `strokeBorderColor` | Border color |
| `plotter` | `plotter` | Custom JS plotter |
| `highlight_circle_size` | `highlightCircleSize` | Per-series highlight dot size |
| `show_in_range_selector` | `showInRangeSelector` | Show in range selector mini-plot |

### `.highlight(...)` / `Highlight(...)`

| Parameter | JS Option | Description |
|-----------|-----------|-------------|
| `circle_size` | `highlightCircleSize` | Highlight dot size |
| `series_background_alpha` | `highlightSeriesBackgroundAlpha` | Background fade alpha |
| `series_background_color` | `highlightSeriesBackgroundColor` | Background fade color |
| `series_opts` | `highlightSeriesOpts` | Opts applied to highlighted series |
| `hide_on_mouse_out` | `hideOverlayOnMouseOut` | Hide legend on mouse exit |

### `.annotation(...)` / `Annotation(...)`

| Parameter | JS Property | Description |
|-----------|------------|-------------|
| `x` | `x` | Position on x-axis |
| `text` | `shortText` | Short label text |
| `tooltip` | `text` | Tooltip on hover |
| `width`, `height` | `width`, `height` | Annotation box size |
| `css_class` | `cssClass` | Custom CSS class |
| `tick_height` | `tickHeight` | Tick line height |
| `tick_color` | `tickColor` | Tick line color |
| `tick_width` | `tickWidth` | Tick line width |
| `attach_at_bottom` | `attachAtBottom` | Attach to bottom |
| `icon` | `icon` | Image URL instead of text |
| `click_handler` | `clickHandler` | JS click handler |
| `mouse_over_handler` | `mouseOverHandler` | JS mouseover handler |
| `mouse_out_handler` | `mouseOutHandler` | JS mouseout handler |
| `dbl_click_handler` | `dblClickHandler` | JS double-click handler |

## Development

```bash
uv sync --group dev
uv run ruff check src/ tests/
uv run ty check
uv run prek run --all-files
uv run pytest tests/dygraphs/    # core tests
uv run pytest tests/dash/          # Dash adapter tests
uv run pytest tests/integration/   # Chrome integration tests
```

## License

MIT
