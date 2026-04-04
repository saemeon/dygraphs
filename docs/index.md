# dash-dygraphs

Python/Dash wrapper for the [dygraphs](https://dygraphs.com) JavaScript charting library.

Ported from the R [dygraphs](https://rstudio.github.io/dygraphs/) package with a Pythonic builder API.

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
    .options(fill_graph=True, draw_points=True)
    .axis("y", label="Value")
    .legend(show="always")
    .range_selector(height=30)
    .to_dash(app=app)
)

app.layout = html.Div([chart])

if __name__ == "__main__":
    app.run(debug=True)
```

## Features

### Builder Pattern

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
    .to_dash(app=app)
)
```

### Zoom Sync

Synchronize zoom and pan across multiple charts:

```python
from dash_dygraphs import sync_dygraphs, stacked_bar

sync = sync_dygraphs(app, ["chart-a", "chart-b", "chart-c"])
app.layout = html.Div([sync, chart_a, chart_b, chart_c])
```

### Stacked Bar Chart

Canvas-based stacked bar chart with interactive range selector:

```python
from dash_dygraphs import stacked_bar

bar = stacked_bar(
    app, "energy",
    initial_data=csv_string,
    colors=["#00d4aa", "#7eb8f7", "#f4a261"],
    height=280,
    title="Energy Contributions",
)
```

### Modebar

Plotly-style overlay buttons appear on hover:

- **Camera icon**: Download chart as PNG (hides range selector)
- **Home icon**: Reset zoom to full range

Disable with `modebar=False` in `.to_dash()`.

### dash-capture Integration

```python
from dash_dygraphs import dygraph_strategy
from dash_capture import capture_element

capture_element(
    app, "btn", "chart-container", "img-store",
    strategy=dygraph_strategy(hide_range_selector=True),
)
```

## Data Input

Accepts multiple formats:

| Type | Example |
|------|---------|
| pandas DataFrame | `pd.DataFrame({"y": [1,2,3]}, index=pd.date_range(...))` |
| pandas Series | `pd.Series([1,2,3], name="y")` |
| dict of lists | `{"x": [1,2,3], "y": [10,20,30]}` |
| list of rows | `[[1, 10], [2, 20], [3, 30]]` |

DatetimeIndex is auto-detected and formatted for the x-axis.
