"""Standalone feature gallery — every dygraphs feature in one HTML page.

Run with::

    uv run python examples/gallery.py

Opens the gallery in your default browser.  No Dash or Shiny required.
"""

from __future__ import annotations

import html as html_mod
import tempfile
import webbrowser
from pathlib import Path

import numpy as np
import pandas as pd

from dygraphs import (
    Annotation,
    Axis,
    Dygraph,
    Event,
    Legend,
    Options,
    RangeSelector,
    Series,
    Shading,
)

# =============================================================================
# Data helpers
# =============================================================================

_RNG = np.random.default_rng(42)
_DATES = pd.date_range("2024-01-01", periods=90, freq="D")


def _ts(cols: list[str], base: float = 20.0) -> pd.DataFrame:
    data = {}
    for i, c in enumerate(cols):
        data[c] = (base + i * 5 + np.cumsum(_RNG.standard_normal(90) * 0.6)).round(2)
    return pd.DataFrame(data, index=_DATES)


def _section(title: str, charts: list[tuple[str, str]]) -> str:
    cards = ""
    for subtitle, chart_html in charts:
        # Each chart is a self-contained HTML page — render in an iframe
        # so all <head> scripts (CDN, plotters, shapes.js) are preserved.
        escaped = chart_html.replace("&", "&amp;").replace('"', "&quot;")
        cards += f"""
        <div class="card">
            <h3>{html_mod.escape(subtitle)}</h3>
            <iframe srcdoc="{escaped}" style="width:100%;height:320px;border:none;"></iframe>
        </div>"""
    return f"""
    <div class="section">
        <h2>{html_mod.escape(title)}</h2>
        {cards}
    </div>"""


# =============================================================================
# Charts — organised by feature category
# =============================================================================

charts: list[tuple[str, list[tuple[str, str]]]] = []
_id = 0


def _html(dg: Dygraph, **kw) -> str:
    global _id
    _id += 1
    return dg.to_html(height="280px", cdn=True, **kw)


# ---------------------------------------------------------------------------
# 1. Data input formats
# ---------------------------------------------------------------------------

section_charts: list[tuple[str, str]] = []

# DataFrame with DatetimeIndex
section_charts.append(
    (
        "DataFrame with DatetimeIndex",
        _html(Dygraph(_ts(["temp", "humidity"]), title="Time-series DataFrame")),
    )
)

# Dict input (numeric x-axis)
section_charts.append(
    (
        "Dict input (numeric x-axis)",
        _html(
            Dygraph(
                {
                    "x": list(range(20)),
                    "sin": [round(np.sin(i / 3), 2) for i in range(20)],
                    "cos": [round(np.cos(i / 3), 2) for i in range(20)],
                },
                title="Numeric Dict",
            )
        ),
    )
)

# List-of-lists
section_charts.append(
    (
        "List of lists",
        _html(
            Dygraph(
                [[i, i**2, i**3] for i in range(10)],
                title="List of Lists (x, x^2, x^3)",
            )
        ),
    )
)

# CSV string
csv_str = "Date,Revenue,Cost\n2024-01-01,100,80\n2024-01-02,110,85\n2024-01-03,105,82\n2024-01-04,120,90\n2024-01-05,115,88"
section_charts.append(
    (
        "CSV string",
        _html(Dygraph(csv_str, title="CSV String Input")),
    )
)

# Numpy array
arr = np.column_stack(
    [
        np.arange(50),
        _RNG.standard_normal(50).cumsum(),
        _RNG.standard_normal(50).cumsum(),
    ]
)
section_charts.append(
    (
        "Numpy 2D array",
        _html(Dygraph(arr, title="Numpy Array Input")),
    )
)

charts.append(("1. Data Input Formats", section_charts))

# ---------------------------------------------------------------------------
# 2. Line styling
# ---------------------------------------------------------------------------

section_charts = []

df = _ts(["A", "B", "C"])

section_charts.append(
    (
        "Stroke widths & colors",
        _html(
            Dygraph(df, title="Stroke Widths")
            .series("A", stroke_width=1, color="red")
            .series("B", stroke_width=3, color="blue")
            .series("C", stroke_width=5, color="green")
        ),
    )
)

section_charts.append(
    (
        "Stroke patterns",
        _html(
            Dygraph(df, title="Stroke Patterns")
            .series("A", stroke_pattern="solid", color="#e74c3c")
            .series("B", stroke_pattern="dashed", color="#3498db")
            .series("C", stroke_pattern="dotted", color="#2ecc71")
        ),
    )
)

section_charts.append(
    (
        "Fill graph with alpha",
        _html(
            Dygraph(df, title="Fill Graph").options(
                fill_graph=True,
                fill_alpha=0.25,
                colors=["#e74c3c", "#3498db", "#2ecc71"],
            )
        ),
    )
)

section_charts.append(
    (
        "Step plot",
        _html(
            Dygraph(
                pd.DataFrame({"status": _RNG.integers(0, 3, 50)}, index=_DATES[:50]),
                title="Step Plot",
            ).options(
                step_plot=True, fill_graph=True, fill_alpha=0.3, colors=["#9b59b6"]
            )
        ),
    )
)

section_charts.append(
    (
        "Stem plot",
        _html(
            Dygraph(
                pd.DataFrame(
                    {"impulse": (_RNG.standard_normal(30) * 5).round(1)},
                    index=_DATES[:30],
                ),
                title="Stem Plot",
            ).options(stem_plot=True, colors=["#e67e22"])
        ),
    )
)

section_charts.append(
    (
        "Connect separated points",
        _html(
            Dygraph(
                pd.DataFrame(
                    {"y": [1, None, None, 4, 5, None, 7, 8, 9, 10]},
                    index=pd.date_range("2024-01-01", periods=10, freq="D"),
                ),
                title="Connect Separated Points",
            ).options(
                connect_separated_points=True, draw_points=True, colors=["#2ecc71"]
            )
        ),
    )
)

charts.append(("2. Line Styling", section_charts))

# ---------------------------------------------------------------------------
# 3. Point shapes
# ---------------------------------------------------------------------------

section_charts = []

shapes_df = pd.DataFrame(
    {
        name: _RNG.standard_normal(20).cumsum().round(1)
        for name in [
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
        ]
    },
    index=pd.date_range("2024-01-01", periods=20, freq="D"),
)

dg = Dygraph(shapes_df, title="All 10 Point Shapes").options(
    draw_points=True, point_size=4, stroke_width=1
)
for name in shapes_df.columns:
    dg = dg.series(name, point_shape=name)

section_charts.append(("All 10 shapes (per-series)", _html(dg)))

section_charts.append(
    (
        "Global point shape",
        _html(
            Dygraph(_ts(["A", "B"]), title="Global Star Shape").options(
                draw_points=True, point_size=3, point_shape="star"
            )
        ),
    )
)

charts.append(("3. Point Shapes", section_charts))

# ---------------------------------------------------------------------------
# 4. Axes
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Secondary y-axis (y2)",
        _html(
            Dygraph(_ts(["Pressure", "Wind"]), title="Dual Axis")
            .axis("y", label="Pressure (hPa)")
            .axis("y2", label="Wind (km/h)", independent_ticks=True)
            .series("Pressure", axis="y", color="#3498db")
            .series("Wind", axis="y2", color="#e74c3c", stroke_pattern="dashed")
        ),
    )
)

section_charts.append(
    (
        "Logscale y-axis",
        _html(
            Dygraph(
                pd.DataFrame(
                    {"exp": [2**i for i in range(15)]},
                    index=pd.date_range("2024-01-01", periods=15, freq="D"),
                ),
                title="Logscale Y",
            )
            .axis("y", logscale=True)
            .options(colors=["#8e44ad"])
        ),
    )
)

section_charts.append(
    (
        "Include zero & draw axes at zero",
        _html(
            Dygraph(
                pd.DataFrame(
                    {"y": _RNG.standard_normal(30).cumsum().round(1)}, index=_DATES[:30]
                ),
                title="Include Zero + Axes at Zero",
            ).options(include_zero=True, draw_axes_at_zero=True, colors=["#16a085"])
        ),
    )
)

section_charts.append(
    (
        "Axis styling",
        _html(
            Dygraph(_ts(["Value"]), title="Axis Styling")
            .axis("x", axis_line_color="red", axis_line_width=2, pixels_per_label=80)
            .axis(
                "y",
                axis_label_color="blue",
                axis_label_font_size=12,
                grid_line_color="#ddd",
                grid_line_width=0.5,
            )
        ),
    )
)

section_charts.append(
    (
        "Hide axes",
        _html(
            Dygraph(_ts(["Signal"]), title="Hidden Axes").options(
                draw_x_axis=False,
                draw_y_axis=False,
                draw_grid=False,
                colors=["#e74c3c"],
            )
        ),
    )
)

charts.append(("4. Axes & Scales", section_charts))

# ---------------------------------------------------------------------------
# 5. Legend & Highlight
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Legend always",
        _html(Dygraph(_ts(["A", "B"]), title="Legend: always").legend(show="always")),
    )
)

section_charts.append(
    (
        "Legend follow",
        _html(
            Dygraph(_ts(["A", "B"]), title="Legend: follow (tracks cursor)").legend(
                show="follow"
            )
        ),
    )
)

section_charts.append(
    (
        "Legend never",
        _html(Dygraph(_ts(["A"]), title="Legend: never (hidden)").legend(show="never")),
    )
)

section_charts.append(
    (
        "Highlight options",
        _html(
            Dygraph(_ts(["X", "Y"]), title="Highlight: large circle, dim background")
            .highlight(
                circle_size=8,
                series_background_alpha=0.1,
                series_opts={"strokeWidth": 3},
            )
            .legend(show="always")
        ),
    )
)

charts.append(("5. Legend & Highlight", section_charts))

# ---------------------------------------------------------------------------
# 6. Annotations, Events, Shadings, Limits
# ---------------------------------------------------------------------------

section_charts = []

dg_overlay = (
    Dygraph(_ts(["Value"]), title="Annotations + Events + Shadings + Limits")
    .annotation("2024-01-15", "A", tooltip="First annotation", series="Value")
    .annotation(
        "2024-02-01",
        "B",
        tooltip="Second annotation",
        series="Value",
        css_class="custom-ann",
        tick_height=15,
        attach_at_bottom=True,
    )
    .event("2024-01-20", "Deploy", label_loc="top", color="#3498db")
    .event(
        "2024-02-15",
        "Outage",
        label_loc="bottom",
        color="#e74c3c",
        stroke_pattern="dotted",
    )
    .shading("2024-01-05", "2024-01-12", color="rgba(46,204,113,0.2)")
    .shading("2024-03-01", "2024-03-10", color="rgba(231,76,60,0.2)")
    .limit(25.0, "Upper", color="#e74c3c", stroke_pattern="dashed", label_loc="right")
    .limit(15.0, "Lower", color="#3498db", stroke_pattern="dotted")
    .legend(show="always")
)
section_charts.append(("All overlay types combined", _html(dg_overlay)))

section_charts.append(
    (
        "Y-axis shading",
        _html(
            Dygraph(
                {
                    "x": list(range(20)),
                    "y": [int(_RNG.integers(0, 100)) for _ in range(20)],
                },
                title="Y-Axis Shading",
            )
            .shading(20, 40, color="rgba(52,152,219,0.2)", axis="y")
            .shading(60, 80, color="rgba(231,76,60,0.2)", axis="y")
        ),
    )
)

charts.append(("6. Annotations, Events, Shadings & Limits", section_charts))

# ---------------------------------------------------------------------------
# 7. Range selector & Roller
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Range selector with date window",
        _html(
            Dygraph(
                _ts(["Value"]), title="Range Selector + Date Window"
            ).range_selector(
                date_window=("2024-02-01", "2024-03-01"),
                height=30,
                fill_color="#A7B1C4",
                stroke_color="#808FAB",
            )
        ),
    )
)

section_charts.append(
    (
        "Rolling average (7-day)",
        _html(
            Dygraph(_ts(["Noisy"]), title="Roller: 7-day rolling average")
            .roller(roll_period=7)
            .options(colors=["#e67e22"])
        ),
    )
)

charts.append(("7. Range Selector & Roller", section_charts))

# ---------------------------------------------------------------------------
# 8. Plotters — Bar charts
# ---------------------------------------------------------------------------

section_charts = []

bar_df = _ts(["Alpha", "Beta", "Gamma"])

section_charts.append(
    (
        "Bar chart (auto multi-column)",
        _html(Dygraph(bar_df, title="Bar Chart (multi-series auto)").bar_chart()),
    )
)

section_charts.append(
    (
        "Stacked bar chart",
        _html(
            Dygraph(bar_df, title="Stacked Bar Chart")
            .stacked_bar_chart()
            .options(colors=["#e74c3c", "#3498db", "#2ecc71"])
        ),
    )
)

section_charts.append(
    (
        "Multi-column (explicit)",
        _html(Dygraph(bar_df, title="Multi-Column").multi_column()),
    )
)

section_charts.append(
    (
        "Single-series bar chart",
        _html(
            Dygraph(
                pd.DataFrame({"Sales": _RNG.integers(10, 50, 20)}, index=_DATES[:20]),
                title="Single-Series Bar",
            ).bar_chart()
        ),
    )
)

charts.append(("8. Bar Chart Plotters", section_charts))

# ---------------------------------------------------------------------------
# 9. Plotters — Series-level
# ---------------------------------------------------------------------------

section_charts = []

df_two = _ts(["Line", "Special"])

section_charts.append(
    (
        "bar_series (one series as bars)",
        _html(Dygraph(df_two, title="bar_series on 'Special'").bar_series("Special")),
    )
)

section_charts.append(
    (
        "stem_series",
        _html(Dygraph(df_two, title="stem_series on 'Special'").stem_series("Special")),
    )
)

section_charts.append(
    (
        "shadow (fill only, no line)",
        _html(Dygraph(df_two, title="shadow on 'Special'").shadow("Special")),
    )
)

section_charts.append(
    (
        "filled_line",
        _html(Dygraph(df_two, title="filled_line on 'Special'").filled_line("Special")),
    )
)

section_charts.append(
    (
        "error_fill",
        _html(Dygraph(df_two, title="error_fill on 'Special'").error_fill("Special")),
    )
)

charts.append(("9. Series-Level Plotters", section_charts))

# ---------------------------------------------------------------------------
# 10. Plotters — Group-level
# ---------------------------------------------------------------------------

section_charts = []

df_grp = _ts(["X", "Y", "Z"])

section_charts.append(
    (
        "multi_column_group",
        _html(
            Dygraph(df_grp, title="multi_column_group(['X','Y'])").multi_column_group(
                ["X", "Y"]
            )
        ),
    )
)

section_charts.append(
    (
        "stacked_bar_group",
        _html(
            Dygraph(df_grp, title="stacked_bar_group(['X','Y'])").stacked_bar_group(
                ["X", "Y"]
            )
        ),
    )
)

section_charts.append(
    (
        "stacked_line_group",
        _html(
            Dygraph(df_grp, title="stacked_line_group(['X','Y'])").stacked_line_group(
                ["X", "Y"]
            )
        ),
    )
)

section_charts.append(
    (
        "stacked_ribbon_group",
        _html(
            Dygraph(
                df_grp, title="stacked_ribbon_group(['X','Y'])"
            ).stacked_ribbon_group(["X", "Y"])
        ),
    )
)

charts.append(("10. Group-Level Plotters", section_charts))

# ---------------------------------------------------------------------------
# 11. Candlestick
# ---------------------------------------------------------------------------

section_charts = []

ohlc = pd.DataFrame(
    {
        "Open": (100 + _RNG.standard_normal(60).cumsum()).round(2),
        "High": (102 + _RNG.standard_normal(60).cumsum()).round(2),
        "Low": (98 + _RNG.standard_normal(60).cumsum()).round(2),
        "Close": (100 + _RNG.standard_normal(60).cumsum()).round(2),
    },
    index=pd.date_range("2024-01-01", periods=60, freq="D"),
)

section_charts.append(
    (
        "Candlestick",
        _html(Dygraph(ohlc, title="Candlestick Chart").candlestick()),
    )
)

section_charts.append(
    (
        "Candlestick with compress",
        _html(
            Dygraph(ohlc, title="Candlestick + Compress Plugin").candlestick(
                compress=True
            )
        ),
    )
)

section_charts.append(
    (
        "candlestick_group",
        _html(
            Dygraph(
                ohlc, title="candlestick_group(['Open','High','Low','Close'])"
            ).candlestick_group(["Open", "High", "Low", "Close"])
        ),
    )
)

charts.append(("11. Candlestick Charts", section_charts))

# ---------------------------------------------------------------------------
# 12. Error bars
# ---------------------------------------------------------------------------

section_charts = []

y_vals = 20 + _RNG.standard_normal(40).cumsum()
eb_df = pd.DataFrame(
    {
        "low": (y_vals - np.abs(_RNG.standard_normal(40))).round(2),
        "mid": y_vals.round(2),
        "high": (y_vals + np.abs(_RNG.standard_normal(40))).round(2),
    },
    index=_DATES[:40],
)

section_charts.append(
    (
        "Custom bars (3 columns: low, mid, high)",
        _html(
            Dygraph(eb_df, title="Custom Bars via columns=")
            .series(columns=["low", "mid", "high"], color="#e74c3c")
            .legend(show="always")
        ),
    )
)

eb_df2 = pd.DataFrame(
    {
        "value": y_vals.round(2),
        "error": np.abs(_RNG.standard_normal(40)).round(2),
    },
    index=_DATES[:40],
)

section_charts.append(
    (
        "Error bars (2 columns: value, error)",
        _html(
            Dygraph(eb_df2, title="Error Bars via columns=")
            .series(columns=["value", "error"], color="#3498db")
            .legend(show="always")
        ),
    )
)

charts.append(("12. Error Bars", section_charts))

# ---------------------------------------------------------------------------
# 13. Plugins
# ---------------------------------------------------------------------------

section_charts = []

base = _ts(["Signal"])

section_charts.append(
    (
        "Unzoom button (zoom in, then click button)",
        _html(
            Dygraph(base, title="Unzoom Plugin").unzoom().options(colors=["#2ecc71"])
        ),
    )
)

section_charts.append(
    (
        "Crosshair (vertical)",
        _html(
            Dygraph(base, title="Crosshair: vertical")
            .crosshair(direction="vertical")
            .options(colors=["#3498db"])
        ),
    )
)

section_charts.append(
    (
        "Crosshair (both)",
        _html(
            Dygraph(base, title="Crosshair: both")
            .crosshair(direction="both")
            .options(colors=["#e67e22"])
        ),
    )
)

section_charts.append(
    (
        "Ribbon (background state bands)",
        _html(
            Dygraph(base, title="Ribbon Plugin")
            .ribbon(
                data=[0, 1, 0, 1, 0] * 18,
                palette=["rgba(200,255,200,0.3)", "rgba(255,200,200,0.3)"],
            )
            .options(colors=["#8e44ad"])
        ),
    )
)

df_rebase = _ts(["Stock A", "Stock B"], base=50)
df_rebase["Stock A"] += 50
df_rebase["Stock B"] += 200

section_charts.append(
    (
        "Rebase (normalised to 100)",
        _html(
            Dygraph(df_rebase, title="Rebase Plugin (value=100)")
            .rebase(value=100)
            .legend(show="always")
            .options(colors=["#2ecc71", "#e74c3c"])
        ),
    )
)

section_charts.append(
    (
        "Rebase percent",
        _html(
            Dygraph(df_rebase, title="Rebase Plugin (percent)")
            .rebase(percent=True)
            .legend(show="always")
            .options(colors=["#3498db", "#f39c12"])
        ),
    )
)

charts.append(("13. Plugins", section_charts))

# ---------------------------------------------------------------------------
# 14. Series groups
# ---------------------------------------------------------------------------

section_charts = []

df_g = _ts(["Sensor A", "Sensor B", "Sensor C", "Baseline"])

section_charts.append(
    (
        "Group with shared styling",
        _html(
            Dygraph(df_g, title="Series Group (shared style)")
            .group(
                ["Sensor A", "Sensor B", "Sensor C"],
                color=["#e74c3c", "#3498db", "#2ecc71"],
                fill_graph=True,
                draw_points=True,
                point_size=2,
                point_shape=["triangle", "square", "diamond"],
            )
            .series("Baseline", stroke_pattern="dashed", color="#999")
            .legend(show="always")
        ),
    )
)

section_charts.append(
    (
        "Group with stroke options",
        _html(
            Dygraph(df_g, title="Group Stroke Options")
            .group(
                ["Sensor A", "Sensor B", "Sensor C"],
                stroke_width=3,
                stroke_pattern="dotdash",
            )
            .legend(show="always")
        ),
    )
)

charts.append(("14. Series Groups", section_charts))

# ---------------------------------------------------------------------------
# 15. Callbacks
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Click callback (check browser console)",
        _html(
            Dygraph(_ts(["Value"]), title="Click Callback (see console)")
            .callbacks(click="function(e, x, pts){ console.log('Clicked:', x, pts); }")
            .options(colors=["#16a085"])
        ),
    )
)

section_charts.append(
    (
        "Zoom callback",
        _html(
            Dygraph(_ts(["Value"]), title="Zoom Callback (see console)")
            .callbacks(
                zoom="function(minDate, maxDate, yRanges){ console.log('Zoomed:', minDate, maxDate); }"
            )
            .options(colors=["#8e44ad"])
        ),
    )
)

charts.append(("15. Callbacks", section_charts))

# ---------------------------------------------------------------------------
# 16. Number formatting
# ---------------------------------------------------------------------------

section_charts = []

big_df = pd.DataFrame(
    {"Revenue": _RNG.integers(1_000_000, 9_000_000, 30)},
    index=_DATES[:30],
)

section_charts.append(
    (
        "Labels KMB (K/M/B suffixes)",
        _html(
            Dygraph(big_df, title="Labels KMB").options(
                labels_kmb=True, colors=["#27ae60"]
            )
        ),
    )
)

section_charts.append(
    (
        "Digits after decimal + sig figs",
        _html(
            Dygraph(_ts(["Precise"]), title="4 digits after decimal").options(
                digits_after_decimal=4, colors=["#2980b9"]
            )
        ),
    )
)

charts.append(("16. Number Formatting", section_charts))

# ---------------------------------------------------------------------------
# 17. Interaction options
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Disable zoom",
        _html(
            Dygraph(_ts(["Static"]), title="Zoom Disabled").options(
                disable_zoom=True, colors=["#c0392b"]
            )
        ),
    )
)

section_charts.append(
    (
        "Animated zooms",
        _html(
            Dygraph(_ts(["Smooth"]), title="Animated Zooms").options(
                animated_zooms=True, colors=["#8e44ad"]
            )
        ),
    )
)

section_charts.append(
    (
        "Visibility (hide second series)",
        _html(
            Dygraph(_ts(["Visible", "Hidden"]), title="Visibility: [True, False]")
            .options(visibility=[True, False])
            .legend(show="always")
        ),
    )
)

charts.append(("17. Interaction Options", section_charts))

# ---------------------------------------------------------------------------
# 18. Stacked graph
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Stacked graph",
        _html(
            Dygraph(
                _ts(["Layer 1", "Layer 2", "Layer 3"]), title="Stacked Graph"
            ).options(
                stacked_graph=True,
                fill_alpha=0.5,
                colors=["#e74c3c", "#3498db", "#2ecc71"],
            )
        ),
    )
)

charts.append(("18. Stacked Graph", section_charts))

# ---------------------------------------------------------------------------
# 19. Declarative API
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Full declarative construction",
        _html(
            Dygraph(
                _ts(["Voltage", "Current"]),
                title="Declarative API",
                options=Options(fill_graph=True, stroke_width=2, animated_zooms=True),
                axes=[Axis("y", label="Value", value_range=(0, 50))],
                series=[
                    Series("Voltage", color="#e74c3c", stroke_width=2.5),
                    Series("Current", color="#3498db", fill_graph=False),
                ],
                legend=Legend(show="always"),
                range_selector=RangeSelector(height=25),
                shadings=[
                    Shading(
                        from_="2024-02-01",
                        to="2024-03-01",
                        color="rgba(255,200,200,0.3)",
                    )
                ],
                events=[Event(x="2024-02-14", label="Maintenance", color="#888")],
                annotations=[Annotation(x="2024-01-20", text="!", series="Voltage")],
            )
        ),
    )
)

charts.append(("19. Declarative API", section_charts))

# ---------------------------------------------------------------------------
# 20. Copy, update & fork
# ---------------------------------------------------------------------------

section_charts = []

base_chart = Dygraph(_ts(["Base"]), title="Base chart").options(
    stroke_width=2, colors=["#2c3e50"]
)

variant_a = base_chart.copy().options(fill_graph=True, colors=["#e74c3c"])
variant_a._attrs["title"] = "Fork A (fill + red)"

variant_b = base_chart.copy().options(step_plot=True, colors=["#3498db"])
variant_b._attrs["title"] = "Fork B (step + blue)"

section_charts.append(("Copy → fork A", _html(variant_a)))
section_charts.append(("Copy → fork B", _html(variant_b)))

section_charts.append(
    (
        "update() method",
        _html(
            Dygraph(_ts(["Updated"]), title="Before update").update(
                options={"fill_graph": True}, legend=Legend(show="always")
            )
        ),
    )
)

charts.append(("20. Copy, Update & Fork", section_charts))

# ---------------------------------------------------------------------------
# 21. Custom plotter
# ---------------------------------------------------------------------------

section_charts = []

custom_js = """
function(e) {
  var ctx = e.drawingContext;
  var points = e.points;
  ctx.fillStyle = e.color;
  for (var i = 0; i < points.length; i++) {
    var p = points[i];
    ctx.beginPath();
    ctx.arc(p.canvasx, p.canvasy, 4, 0, 2*Math.PI);
    ctx.fill();
  }
}"""

section_charts.append(
    (
        "Custom plotter (circles only)",
        _html(
            Dygraph(
                pd.DataFrame(
                    {"y": _RNG.standard_normal(30).cumsum().round(1)}, index=_DATES[:30]
                ),
                title="Custom Plotter",
            ).custom_plotter(custom_js)
        ),
    )
)

charts.append(("21. Custom Plotter", section_charts))

# ---------------------------------------------------------------------------
# 22. series_data (auxiliary columns)
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "series_data (extra column)",
        _html(
            Dygraph(_ts(["Original"]), title="series_data: adds 'Extra' column")
            .series_data("Extra", (_RNG.standard_normal(90) * 10).round(1).tolist())
            .legend(show="always")
        ),
    )
)

charts.append(("22. Auxiliary Series Data", section_charts))

# ---------------------------------------------------------------------------
# 23. Inline CSS
# ---------------------------------------------------------------------------

section_charts = []

# Create a temporary CSS file
_css_content = """\
.dygraph-legend {
    background: rgba(0,0,0,0.8) !important;
    color: #fff !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    font-size: 12px !important;
}
.dygraph-ylabel {
    color: #e74c3c !important;
}
"""
_css_path = Path(tempfile.mktemp(suffix=".css"))
_css_path.write_text(_css_content)

section_charts.append(
    (
        "Custom CSS (dark legend, colored ylabel)",
        _html(
            Dygraph(_ts(["Styled"]), title="Custom CSS")
            .css(_css_path)
            .legend(show="always")
            .axis("y", label="Custom Label")
            .options(colors=["#e74c3c"])
        ),
    )
)

_css_path.unlink(missing_ok=True)

charts.append(("23. Custom CSS", section_charts))

# ---------------------------------------------------------------------------
# 24. Grid options
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Grid styling",
        _html(
            Dygraph(_ts(["Value"]), title="Grid Styling").options(
                grid_line_color="rgba(0,0,0,0.1)",
                grid_line_width=1.5,
                grid_line_pattern=[5, 5],
                axis_tick_size=6,
                colors=["#2980b9"],
            )
        ),
    )
)

section_charts.append(
    (
        "No grid",
        _html(
            Dygraph(_ts(["Clean"]), title="No Grid").options(
                draw_grid=False, colors=["#16a085"]
            )
        ),
    )
)

charts.append(("24. Grid Options", section_charts))

# ---------------------------------------------------------------------------
# 25. to_html options
# ---------------------------------------------------------------------------

section_charts = []

section_charts.append(
    (
        "Inline JS (cdn=False)",
        Dygraph(_ts(["Inline"]), title="Inline JS (no CDN)").to_html(
            cdn=False, height="280px"
        ),
    )
)

section_charts.append(
    (
        "Custom dimensions",
        Dygraph(_ts(["Small"]), title="Custom Dimensions").to_html(
            height=200, width="60%"
        ),
    )
)

charts.append(("25. to_html Options", section_charts))


# =============================================================================
# Assemble HTML page
# =============================================================================


def build_page() -> str:
    sections_html = ""
    for section_title, section_items in charts:
        sections_html += _section(section_title, section_items)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>dygraphs Python — Feature Gallery</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 24px;
    background: #fafafa;
    color: #222;
  }}
  h1 {{
    text-align: center;
    margin-bottom: 8px;
  }}
  .subtitle {{
    text-align: center;
    color: #666;
    margin-bottom: 40px;
  }}
  .section {{
    margin-bottom: 48px;
  }}
  .section h2 {{
    border-bottom: 2px solid #ddd;
    padding-bottom: 8px;
    color: #333;
  }}
  .card {{
    background: #fff;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }}
  .card h3 {{
    margin: 0 0 8px 0;
    font-size: 14px;
    color: #888;
    font-weight: 500;
  }}
  .toc {{
    background: #fff;
    border-radius: 8px;
    padding: 16px 24px;
    margin-bottom: 32px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  }}
  .toc ul {{
    columns: 2;
    list-style: none;
    padding: 0;
    margin: 8px 0 0 0;
  }}
  .toc li {{
    padding: 2px 0;
  }}
  .toc a {{
    color: #2980b9;
    text-decoration: none;
  }}
  .toc a:hover {{
    text-decoration: underline;
  }}
</style>
</head>
<body>
<h1>dygraphs Python &mdash; Feature Gallery</h1>
<p class="subtitle">
  Every feature demonstrated in standalone HTML. {len(charts)} sections,
  {sum(len(s) for _, s in charts)} charts.
</p>
{sections_html}
<p style="text-align:center;color:#999;margin-top:48px;">
  Generated by <code>examples/gallery.py</code>
</p>
</body>
</html>"""


if __name__ == "__main__":
    page = build_page()
    out = Path(tempfile.mktemp(suffix=".html", prefix="dygraphs_gallery_"))
    out.write_text(page)
    print(f"Gallery written to {out}")
    print(f"  {len(charts)} sections, {sum(len(s) for _, s in charts)} charts")
    webbrowser.open(f"file://{out}")
