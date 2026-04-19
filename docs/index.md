# dygraphs

Python wrapper for the [dygraphs](https://dygraphs.com) JavaScript charting library.

**Core port of the R [dygraphs](https://rstudio.github.io/dygraphs/) package** — all 37 exported R `dy*` functions plus the `dygraph()` constructor are ported to a Pythonic builder API. The R package (by RStudio/JJ Allaire) is the most mature dygraphs wrapper in any language; this package faithfully ports its API design, data model, and test coverage to Python. See the *R Function Mapping* table below.

Framework-agnostic core with adapters for [Plotly Dash](https://dash.plotly.com/) and [Shiny for Python](https://shiny.posit.co/py/).

## Features

- **Two API styles**: builder chaining (`Dygraph(df).options(...).series(...)`) and declarative (`Dygraph(df, options=Options(...), series=[Series(...)])`) — both produce identical output
- **Full R port + full JS coverage**: options, axes, series, legend, highlight, annotations, shadings, events, limits, range selector, roller, callbacks — every documented and undocumented dygraph option is exposed
- **Advanced plotters**: bar chart, stacked bar, candlestick, multi-column, stem, filled line, error fill + group variants
- **Plugins**: unzoom, crosshair, ribbon, rebase
- **Error bars**: symmetric, custom (low/mid/high), fractions with Wilson intervals
- **Zoom sync** across multiple charts with debounced range-selector panning
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
from pathlib import Path

html_string = chart.to_html()
Path("chart.html").write_text(html_string)
```

### Jupyter / IPython

A `Dygraph` is its own display object — making it the last expression
in a cell auto-renders it inline via `_repr_html_`, the same UX as
`dygraph()` in RStudio's viewer:

```python
chart  # auto-displays
```

For loops or non-last-expression contexts, use the explicit helper:

```python
chart.show()  # uses IPython.display.HTML
```

## Data Input

| Format | Example |
|--------|---------|
| pandas DataFrame | `pd.DataFrame({"y": [1,2,3]}, index=pd.date_range(...))` |
| pandas Series | `pd.Series([1,2,3], name="y")` |
| dict of lists | `{"x": [1,2,3], "y": [10,20,30]}` |
| list of rows | `[[1, 10], [2, 20], [3, 30]]` |
| numpy array | `np.array([[1, 10], [2, 20]])` |
| CSV string | `"Date,A,B\n2024-01-01,1,2\n..."` |
| CSV file | `Dygraph.from_csv("data.csv")` |

DatetimeIndex is auto-detected and formatted for the x-axis.

## Builder Methods

All configuration uses method chaining, mirroring the R package's pipe operator:

```python
chart = (
    Dygraph(df, title="My Chart")
    .options(fill_graph=True, stroke_width=2)
    .axis("y", label="Temperature", value_range=(0, 40))
    .axis("y2", label="Humidity", independent_ticks=True)
    .series("temp", color="red", axis="y")
    .series("humidity", color="blue", axis="y2")
    .legend(show="always")
    .highlight(circle_size=5, series_opts={"strokeWidth": 3})
    .annotation("2024-03-15", "A", tooltip="Spring")
    .shading("2024-01-15", "2024-02-15", color="rgba(200,200,255,0.3)")
    .event("2024-02-14", "Valentine's", color="#f76e8a")
    .limit(30.0, "Threshold", stroke_pattern="dotted")
    .range_selector(height=30)
    .roller(roll_period=7)
    .crosshair(direction="vertical")
    .unzoom()
    .to_dash()
)
```

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
| `.css(css)` | `dyCSS()` | Custom CSS — file path or raw CSS string |
| `.dependency(name, ...)` | `dyDependency()` | Attach external JS / CSS files |

### Plotters

`.bar_chart()`, `.stacked_bar_chart()`, `.multi_column()`, `.candlestick()`, `.bar_series(name)`, `.stem_series(name)`, `.shadow(name)`, `.filled_line(name)`, `.error_fill(name)` + group variants

Also via constructor: `Dygraph(df, plotter="bar_chart")`

### Plugins

`.unzoom()`, `.crosshair(direction)`, `.ribbon(data, palette)`, `.rebase(value, percent)`

## Error Bars

```python
from dygraphs import Dygraph, make_error_bar_data

data = make_error_bar_data(x=[1, 2, 3], y=[10, 20, 30], error=[1, 2, 3])
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

## Updating data from Dash callbacks

dygraphs charts in Dash follow the **R `htmlwidgets` model**: every config
update destroys the existing dygraph instance and creates a new one from
scratch. There is exactly one update path, so there's no class of "did I
forget to invalidate X?" bugs to chase.

Each chart created with `DyGraph` (or `dygraph_to_dash` / `Dygraph.to_dash`)
is backed by two `dcc.Store` components:

| Store id          | What lives there       | When to write              |
|-------------------|------------------------|----------------------------|
| `{id}`            | Canonical config       | Pushing fresh data + attrs |
| `{id}-opts`       | Runtime opts override  | Toggling display options   |

The data store shares the chart's `id`, so you can target it directly
with standard Dash `Output` — no helpers needed:

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

### Preserving zoom across updates

Because every config update is a full destroy+recreate, the user's current
zoom range is **discarded** by default — same as R's `dygraph(...)` with
`retainDateWindow = FALSE`. To carry the zoom forward across updates, set
`retain_date_window=True` on the chart options:

```python
chart = (
    Dygraph(df, title="Live data")
    .options(retain_date_window=True)
    .range_selector(height=30)
    .to_dash(component_id="my-chart")
)
```

The renderer reads the previous instance's `xAxisRange()` before
destroying it and writes it back into the new instance's `dateWindow`.

### Group sync still works

Charts that share a `group=` name continue to sync zoom, pan, and highlight
across updates — the JS group registry is keyed by chart id, not by dygraph
instance, so a destroy+recreate transparently re-registers under the same id.

## Modebar

Plotly-style overlay buttons appear on hover:

- **Camera icon**: Download chart as PNG (hides range selector)
- **Home icon**: Reset zoom to full range

Disable with `modebar=False` in `.to_dash()`.

## dash-capture Integration

```python
from dygraphs import dygraph_strategy
from dash_capture import capture_element

capture_element(
    app, "btn", "chart-container", "img-store",
    strategy=dygraph_strategy(hide_range_selector=True),
)
```

## Utility Methods

```python
chart.update(legend={"show": "follow"})  # modify config after construction
forked = chart.copy()                     # deep copy for variants
config = chart.to_dict()                  # plain dict (framework-agnostic)
json_str = chart.to_json()                # JSON with JS functions
```

## R Function Mapping

Every R `dy*()` function has a Python equivalent:

| R Function | Python Builder | Python Declarative |
|------------|---------------|-------------------|
| `dygraph()` | `Dygraph(data)` | `Dygraph(data)` |
| `dyOptions()` | `.options()` | `Options(...)` |
| `dyAxis()` | `.axis()` | `Axis(...)` |
| `dySeries()` | `.series()` | `Series(...)` |
| `dyGroup()` | `.group()` | — |
| `dyLegend()` | `.legend()` | `Legend(...)` |
| `dyHighlight()` | `.highlight()` | `Highlight(...)` |
| `dyAnnotation()` | `.annotation()` | `Annotation(...)` |
| `dyShading()` | `.shading()` | `Shading(...)` |
| `dyEvent()` | `.event()` | `Event(...)` |
| `dyLimit()` | `.limit()` | `Limit(...)` |
| `dyRangeSelector()` | `.range_selector()` | `RangeSelector(...)` |
| `dyRoller()` | `.roller()` | `Roller(...)` |
| `dyCallbacks()` | `.callbacks()` | `Callbacks(...)` |
| `dyCSS()` | `.css()` | — |
| `dyBarChart()` | `.bar_chart()` | — |
| `dyStackedBarChart()` | `.stacked_bar_chart()` | — |
| `dyMultiColumn()` | `.multi_column()` | — |
| `dyCandlestick()` | `.candlestick()` | — |
| `dyBarSeries()` | `.bar_series()` | — |
| `dyStemSeries()` | `.stem_series()` | — |
| `dyShadow()` | `.shadow()` | — |
| `dyFilledLine()` | `.filled_line()` | — |
| `dyErrorFill()` | `.error_fill()` | — |
| `dyMultiColumnGroup()` | `.multi_column_group()` | — |
| `dyCandlestickGroup()` | `.candlestick_group()` | — |
| `dyStackedBarGroup()` | `.stacked_bar_group()` | — |
| `dyStackedLineGroup()` | `.stacked_line_group()` | — |
| `dyStackedRibbonGroup()` | `.stacked_ribbon_group()` | — |
| `dyUnzoom()` | `.unzoom()` | — |
| `dyCrosshair()` | `.crosshair()` | — |
| `dyRibbon()` | `.ribbon()` | — |
| `dyRebase()` | `.rebase()` | — |
| `dyPlotter()` | `.custom_plotter()` | — |
| `dyDataHandler()` | `.data_handler()` | — |
| `dySeriesData()` | `.series_data()` | — |
| `dyPlugin()` | `.plugin()` | — |
| `dyDependency()` | `.dependency()` | — |

See the [API Reference](api.md) for full parameter documentation generated from docstrings.
