# pydygraphs

Python wrapper for the [dygraphs](https://dygraphs.com) JavaScript charting library.

**Core port of the R [dygraphs](https://rstudio.github.io/dygraphs/) package** — all 44 exported R functions ported to a Pythonic builder API. The R package (by RStudio/JJ Allaire) is the most mature dygraphs wrapper in any language; pydygraphs faithfully ports its API design, data model, and test coverage to Python.

Framework-agnostic core with adapters for [Plotly Dash](https://dash.plotly.com/) and [Shiny for Python](https://shiny.posit.co/py/).

## Features

- **Two API styles**: builder chaining (`Dygraph(df).options(...).series(...)`) and declarative (`Dygraph(df, options=Options(...), series=[Series(...)])`) — both produce identical output
- **Full R port**: options, axes, series, legend, highlight, annotations, shadings, events, limits, range selector, roller, callbacks
- **Advanced plotters**: bar chart, stacked bar, candlestick, multi-column, stem, filled line, error fill + group variants
- **Plugins**: unzoom, crosshair, ribbon, rebase
- **Error bars**: symmetric, custom (low/mid/high), fractions with Wilson intervals
- **Zoom sync** across multiple charts (line + stacked bar)
- **Stacked bar chart** with interactive canvas range selector
- **Modebar overlay** (Plotly-style) with PNG download and reset zoom buttons
- **Standalone HTML export** via `.to_html()` — no server needed
- **dash-capture compatible** via `dygraph_strategy()`
- **Framework-agnostic**: core builder has zero Dash/Shiny imports
- **Flexible data input**: DataFrame, Series, dict, list, numpy array, CSV string, CSV file
- **Type-safe**: full type hints, `py.typed`, passes `ty` and `ruff`

## Installation

```bash
pip install pydygraphs            # core only
pip install pydygraphs[dash]      # + Plotly Dash adapter
pip install pydygraphs[shiny]     # + Shiny for Python adapter
```

## Quick Start

### Builder API (chaining)

```python
import pandas as pd
from pydygraphs import Dygraph

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
from pydygraphs import Dygraph, Options, Series, Axis, Legend, RangeSelector

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
app.layout = html.Div([chart.to_dash(app=app)])
```

### Render in Shiny

```python
from pydygraphs.shiny import dygraph_ui, render_dygraph

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
from pydygraphs import Dygraph, make_error_bar_data

data = make_error_bar_data(x=[1,2,3], y=[10,20,30], error=[1,2,3])
chart = Dygraph(data, options={"error_bars": True})
```

## Syncing Multiple Charts

```python
from pydygraphs import sync_dygraphs, stacked_bar

chart_a = Dygraph(df1).range_selector().to_dash(app, component_id="a")
chart_b = Dygraph(df2).range_selector().to_dash(app, component_id="b")
chart_c = stacked_bar(app, "c", csv_data, title="Stacked Bar")

sync = sync_dygraphs(app, ["a", "b", "c"])
app.layout = html.Div([sync, chart_a, chart_b, chart_c])
```

## Dynamic Updates (Dash)

Charts expose `dcc.Store` components:

```python
Output("{id}-store", "data")    # update chart data
Output("{id}-opts", "data")     # update options at runtime
Input("{id}-xrange", "data")    # read current date window
```

## Capture (dash-capture)

```python
from pydygraphs import dygraph_strategy
from dash_capture import capture_element

capture_element(app, "btn", "chart-container", "img-store",
                strategy=dygraph_strategy(hide_range_selector=True))
```

## API Reference

### Builder Methods

| Method | R Equivalent | Description |
|--------|-------------|-------------|
| `Dygraph(data, ...)` | `dygraph()` | Create chart |
| `.options(...)` | `dyOptions()` | Global options |
| `.axis(name, ...)` | `dyAxis()` | Per-axis config |
| `.series(name, ...)` | `dySeries()` | Per-series config |
| `.group(names, ...)` | `dyGroup()` | Group config |
| `.legend(...)` | `dyLegend()` | Legend options |
| `.highlight(...)` | `dyHighlight()` | Highlight behavior |
| `.annotation(x, text)` | `dyAnnotation()` | Data annotations |
| `.shading(from_, to)` | `dyShading()` | Background regions |
| `.event(x, label)` | `dyEvent()` | Vertical event lines |
| `.limit(value, label)` | `dyLimit()` | Horizontal limit lines |
| `.range_selector(...)` | `dyRangeSelector()` | Range selector |
| `.roller(...)` | `dyRoller()` | Rolling average |
| `.callbacks(...)` | `dyCallbacks()` | JS callbacks |
| `.css(path)` | `dyCSS()` | Custom CSS |
| `.update(...)` | — | Modify config |
| `.copy()` | — | Deep copy |
| `.to_dash(app)` | — | Dash component |
| `.to_shiny(id)` | — | Shiny component |
| `.to_html()` | — | Standalone HTML |
| `.to_dict()` | — | Plain dict |
| `.to_json()` | — | JSON string |
| `Dygraph.from_csv(path)` | — | Load from CSV file |

### Declarative Dataclasses

`Options`, `Axis`, `Series`, `Legend`, `Highlight`, `Annotation`, `Shading`, `Event`, `Limit`, `RangeSelector`, `Roller`, `Callbacks`

All accept the same parameters as their builder counterparts. Pass as dataclass or dict.

### Plotters

`.bar_chart()`, `.stacked_bar_chart()`, `.multi_column()`, `.candlestick()`, `.bar_series(name)`, `.stem_series(name)`, `.shadow(name)`, `.filled_line(name)`, `.error_fill(name)` + group variants

Also via constructor: `Dygraph(df, plotter="bar_chart")`

### Plugins

`.unzoom()`, `.crosshair(direction)`, `.ribbon(data, palette)`, `.rebase(value, percent)`

## Development

```bash
uv sync --group dev
uv run ruff check src/ tests/
uv run ty check
uv run prek run --all-files
uv run pytest tests/pydygraphs/    # core tests
uv run pytest tests/dash/          # Dash adapter tests
uv run pytest tests/integration/   # Chrome integration tests
```

## License

MIT
