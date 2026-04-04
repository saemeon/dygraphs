# dash-dygraphs

Python/Dash wrapper for the [dygraphs](https://dygraphs.com) JavaScript charting library.

Ported from the R [dygraphs](https://rstudio.github.io/dygraphs/) package with a Pythonic builder API for use in [Plotly Dash](https://dash.plotly.com/) applications.

## Features

- **Builder API** with method chaining (mirrors R's pipe pattern)
- **Full R port**: options, axes, series, legend, highlight, annotations, shadings, events, limits, range selector, roller, callbacks
- **Advanced plotters**: bar chart, stacked bar, candlestick, multi-column, stem, filled line, error fill + group variants
- **Plugins**: unzoom, crosshair, ribbon, rebase
- **Zoom sync** across multiple charts (line + stacked bar)
- **Stacked bar chart** with interactive canvas range selector
- **Modebar overlay** (Plotly-style) with PNG download and reset zoom buttons
- **dash-capture compatible** via `dygraph_strategy()`
- **Type-safe**: full type hints, `py.typed`, passes `ty` and `ruff`

## Installation

```bash
pip install dash-dygraphs
```

## Quick Start

```python
import pandas as pd
from dash import Dash, html
from dash_dygraphs import Dygraph

app = Dash(__name__)

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
    .to_dash(app=app)
)

app.layout = html.Div([chart])

if __name__ == "__main__":
    app.run(debug=True)
```

## Syncing Multiple Charts

```python
from dash_dygraphs import Dygraph, sync_dygraphs, stacked_bar

chart_a = Dygraph(df1, title="Chart A").range_selector().to_dash(app, component_id="a")
chart_b = Dygraph(df2, title="Chart B").range_selector().to_dash(app, component_id="b")
chart_c = stacked_bar(app, "c", csv_data, title="Stacked Bar")

sync = sync_dygraphs(app, ["a", "b", "c"])

app.layout = html.Div([sync, chart_a, chart_b, chart_c])
```

## Capture (dash-capture integration)

```python
from dash_dygraphs import dygraph_strategy
from dash_capture import capture_element

capture_element(
    app, "btn", "my-chart-container", "img-store",
    strategy=dygraph_strategy(hide_range_selector=True),
)
```

## API Overview

### Dygraph Builder

| Method | R Equivalent | Description |
|--------|-------------|-------------|
| `Dygraph(data, title, xlab, ylab)` | `dygraph()` | Create chart |
| `.options(...)` | `dyOptions()` | Global options |
| `.axis(name, ...)` | `dyAxis()` | Per-axis config |
| `.series(name, ...)` | `dySeries()` | Per-series config |
| `.group(names, ...)` | `dyGroup()` | Group config |
| `.legend(...)` | `dyLegend()` | Legend options |
| `.highlight(...)` | `dyHighlight()` | Highlight behavior |
| `.annotation(x, text, ...)` | `dyAnnotation()` | Data annotations |
| `.shading(from_, to, ...)` | `dyShading()` | Background regions |
| `.event(x, label, ...)` | `dyEvent()` | Vertical event lines |
| `.limit(value, label, ...)` | `dyLimit()` | Horizontal limit lines |
| `.range_selector(...)` | `dyRangeSelector()` | Range selector widget |
| `.roller(...)` | `dyRoller()` | Rolling average control |
| `.callbacks(...)` | `dyCallbacks()` | JS event handlers |
| `.css(path)` | `dyCSS()` | Custom stylesheet |
| `.to_dash(app)` | — | Render to Dash component |

### Plotters

| Method | R Equivalent |
|--------|-------------|
| `.bar_chart()` | `dyBarChart()` |
| `.stacked_bar_chart()` | `dyStackedBarChart()` |
| `.multi_column()` | `dyMultiColumn()` |
| `.candlestick()` | `dyCandlestick()` |
| `.bar_series(name)` | `dyBarSeries()` |
| `.stem_series(name)` | `dyStemSeries()` |
| `.shadow(name)` | `dyShadow()` |
| `.filled_line(name)` | `dyFilledLine()` |
| `.error_fill(name)` | `dyErrorFill()` |

### Plugins

| Method | R Equivalent |
|--------|-------------|
| `.unzoom()` | `dyUnzoom()` |
| `.crosshair(direction)` | `dyCrosshair()` |
| `.ribbon(data, palette)` | `dyRibbon()` |
| `.rebase(value, percent)` | `dyRebase()` |

## Development

```bash
uv sync --group dev
uv run ruff check src/ tests/
uv run ty check
uv run pytest tests/
uv run pytest tests/integration/ -v  # requires Chrome
```

## License

MIT
