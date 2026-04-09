"""API chapter — formatting, interaction, stacking, declarative, copy, plotters, CSS, grid, to_html."""

from __future__ import annotations

import tempfile
from pathlib import Path

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

from ._common import _DATES, _RNG, ChartList, Section, _html, _ts


def section_number_formatting() -> Section:
    cards: ChartList = []

    big_df = pd.DataFrame(
        {"Revenue": _RNG.integers(1_000_000, 9_000_000, 30)},
        index=_DATES[:30],
    )

    cards.append(
        (
            "Labels KMB (K/M/B suffixes)",
            _html(
                Dygraph(big_df, title="Labels KMB").options(
                    labels_kmb=True, colors=["#27ae60"]
                )
            ),
        )
    )

    cards.append(
        (
            "Digits after decimal + sig figs",
            _html(
                Dygraph(_ts(["Precise"]), title="4 digits after decimal").options(
                    digits_after_decimal=4, colors=["#2980b9"]
                )
            ),
        )
    )

    return ("16. Number Formatting", cards)


def section_interaction_options() -> Section:
    cards: ChartList = []

    cards.append(
        (
            "Disable zoom",
            _html(
                Dygraph(_ts(["Static"]), title="Zoom Disabled").options(
                    disable_zoom=True, colors=["#c0392b"]
                )
            ),
        )
    )

    cards.append(
        (
            "Animated zooms",
            _html(
                Dygraph(_ts(["Smooth"]), title="Animated Zooms").options(
                    animated_zooms=True, colors=["#8e44ad"]
                )
            ),
        )
    )

    cards.append(
        (
            "Visibility (hide second series)",
            _html(
                Dygraph(_ts(["Visible", "Hidden"]), title="Visibility: [True, False]")
                .options(visibility=[True, False])
                .legend(show="always")
            ),
        )
    )

    return ("17. Interaction Options", cards)


def section_stacked_graph() -> Section:
    cards: ChartList = []

    cards.append(
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

    return ("18. Stacked Graph", cards)


def section_declarative_api() -> Section:
    cards: ChartList = []

    cards.append(
        (
            "Full declarative construction",
            _html(
                Dygraph(
                    _ts(["Voltage", "Current"]),
                    title="Declarative API",
                    options=Options(
                        fill_graph=True, stroke_width=2, animated_zooms=True
                    ),
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
                    annotations=[
                        Annotation(x="2024-01-20", text="!", series="Voltage")
                    ],
                )
            ),
        )
    )

    return ("19. Declarative API", cards)


def section_copy_update_fork() -> Section:
    cards: ChartList = []

    base_chart = Dygraph(_ts(["Base"]), title="Base chart").options(
        stroke_width=2, colors=["#2c3e50"]
    )

    variant_a = base_chart.copy().options(fill_graph=True, colors=["#e74c3c"])
    variant_a._attrs["title"] = "Fork A (fill + red)"

    variant_b = base_chart.copy().options(step_plot=True, colors=["#3498db"])
    variant_b._attrs["title"] = "Fork B (step + blue)"

    cards.append(("Copy → fork A", _html(variant_a)))
    cards.append(("Copy → fork B", _html(variant_b)))

    cards.append(
        (
            "update() method",
            _html(
                Dygraph(_ts(["Updated"]), title="Before update").update(
                    options={"fill_graph": True}, legend=Legend(show="always")
                )
            ),
        )
    )

    return ("20. Copy, Update & Fork", cards)


def section_custom_plotter() -> Section:
    cards: ChartList = []

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

    cards.append(
        (
            "Custom plotter (circles only)",
            _html(
                Dygraph(
                    pd.DataFrame(
                        {"y": _RNG.standard_normal(30).cumsum().round(1)},
                        index=_DATES[:30],
                    ),
                    title="Custom Plotter",
                ).custom_plotter(custom_js)
            ),
        )
    )

    return ("21. Custom Plotter", cards)


def section_auxiliary_series_data() -> Section:
    cards: ChartList = []

    cards.append(
        (
            "series_data (extra column)",
            _html(
                Dygraph(_ts(["Original"]), title="series_data: adds 'Extra' column")
                .series_data("Extra", (_RNG.standard_normal(90) * 10).round(1).tolist())
                .legend(show="always")
            ),
        )
    )

    return ("22. Auxiliary Series Data", cards)


def section_custom_css() -> Section:
    cards: ChartList = []

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

    cards.append(
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

    return ("23. Custom CSS", cards)


def section_grid_options() -> Section:
    cards: ChartList = []

    cards.append(
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

    cards.append(
        (
            "No grid",
            _html(
                Dygraph(_ts(["Clean"]), title="No Grid").options(
                    draw_grid=False, colors=["#16a085"]
                )
            ),
        )
    )

    return ("24. Grid Options", cards)


def section_to_html_options() -> Section:
    cards: ChartList = []

    cards.append(
        (
            "Inline JS (cdn=False)",
            Dygraph(_ts(["Inline"]), title="Inline JS (no CDN)").to_html(
                cdn=False, height="280px"
            ),
        )
    )

    cards.append(
        (
            "Custom dimensions",
            Dygraph(_ts(["Small"]), title="Custom Dimensions").to_html(
                height=200, width="60%"
            ),
        )
    )

    return ("25. to_html Options", cards)


ALL_SECTIONS = [
    section_number_formatting,
    section_interaction_options,
    section_stacked_graph,
    section_declarative_api,
    section_copy_update_fork,
    section_custom_plotter,
    section_auxiliary_series_data,
    section_custom_css,
    section_grid_options,
    section_to_html_options,
]
