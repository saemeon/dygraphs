"""Basics chapter — data input, styling, point shapes, axes, legend."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dygraphs import Dygraph

from ._common import _DATES, _RNG, ChartList, Section, _html, _ts


def section_data_input() -> Section:
    cards: ChartList = []

    # DataFrame with DatetimeIndex
    cards.append(
        (
            "DataFrame with DatetimeIndex",
            _html(Dygraph(_ts(["temp", "humidity"]), title="Time-series DataFrame")),
        )
    )

    # Dict input (numeric x-axis)
    cards.append(
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
    cards.append(
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
    cards.append(
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
    cards.append(
        (
            "Numpy 2D array",
            _html(Dygraph(arr, title="Numpy Array Input")),
        )
    )

    return ("1. Data Input Formats", cards)


def section_line_styling() -> Section:
    cards: ChartList = []

    df = _ts(["A", "B", "C"])

    cards.append(
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

    cards.append(
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

    cards.append(
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

    cards.append(
        (
            "Step plot",
            _html(
                Dygraph(
                    pd.DataFrame(
                        {"status": _RNG.integers(0, 3, 50)}, index=_DATES[:50]
                    ),
                    title="Step Plot",
                ).options(
                    step_plot=True,
                    fill_graph=True,
                    fill_alpha=0.3,
                    colors=["#9b59b6"],
                )
            ),
        )
    )

    cards.append(
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

    cards.append(
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
                    connect_separated_points=True,
                    draw_points=True,
                    colors=["#2ecc71"],
                )
            ),
        )
    )

    return ("2. Line Styling", cards)


def section_point_shapes() -> Section:
    cards: ChartList = []

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

    cards.append(("All 10 shapes (per-series)", _html(dg)))

    cards.append(
        (
            "Global point shape",
            _html(
                Dygraph(_ts(["A", "B"]), title="Global Star Shape").options(
                    draw_points=True, point_size=3, point_shape="star"
                )
            ),
        )
    )

    return ("3. Point Shapes", cards)


def section_axes_scales() -> Section:
    cards: ChartList = []

    cards.append(
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

    cards.append(
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

    cards.append(
        (
            "Include zero & draw axes at zero",
            _html(
                Dygraph(
                    pd.DataFrame(
                        {"y": _RNG.standard_normal(30).cumsum().round(1)},
                        index=_DATES[:30],
                    ),
                    title="Include Zero + Axes at Zero",
                ).options(include_zero=True, draw_axes_at_zero=True, colors=["#16a085"])
            ),
        )
    )

    cards.append(
        (
            "Axis styling",
            _html(
                Dygraph(_ts(["Value"]), title="Axis Styling")
                .axis(
                    "x", axis_line_color="red", axis_line_width=2, pixels_per_label=80
                )
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

    cards.append(
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

    return ("4. Axes & Scales", cards)


def section_legend_highlight() -> Section:
    cards: ChartList = []

    cards.append(
        (
            "Legend always",
            _html(
                Dygraph(_ts(["A", "B"]), title="Legend: always").legend(show="always")
            ),
        )
    )

    cards.append(
        (
            "Legend follow",
            _html(
                Dygraph(_ts(["A", "B"]), title="Legend: follow (tracks cursor)").legend(
                    show="follow"
                )
            ),
        )
    )

    cards.append(
        (
            "Legend never",
            _html(
                Dygraph(_ts(["A"]), title="Legend: never (hidden)").legend(show="never")
            ),
        )
    )

    cards.append(
        (
            "Highlight options",
            _html(
                Dygraph(
                    _ts(["X", "Y"]), title="Highlight: large circle, dim background"
                )
                .highlight(
                    circle_size=8,
                    series_background_alpha=0.1,
                    series_opts={"strokeWidth": 3},
                )
                .legend(show="always")
            ),
        )
    )

    return ("5. Legend & Highlight", cards)


ALL_SECTIONS = [
    section_data_input,
    section_line_styling,
    section_point_shapes,
    section_axes_scales,
    section_legend_highlight,
]
