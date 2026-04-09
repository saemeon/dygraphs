"""Overlays chapter — annotations, events, shadings, limits, range selector."""

from __future__ import annotations

from dygraphs import Dygraph

from ._common import _RNG, ChartList, Section, _html, _ts


def section_annotations_events() -> Section:
    cards: ChartList = []

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
        .limit(
            25.0, "Upper", color="#e74c3c", stroke_pattern="dashed", label_loc="right"
        )
        .limit(15.0, "Lower", color="#3498db", stroke_pattern="dotted")
        .legend(show="always")
    )
    cards.append(("All overlay types combined", _html(dg_overlay)))

    cards.append(
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

    return ("6. Annotations, Events, Shadings & Limits", cards)


def section_range_selector_roller() -> Section:
    cards: ChartList = []

    cards.append(
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

    cards.append(
        (
            "Rolling average (7-day)",
            _html(
                Dygraph(_ts(["Noisy"]), title="Roller: 7-day rolling average")
                .roller(roll_period=7)
                .options(colors=["#e67e22"])
            ),
        )
    )

    return ("7. Range Selector & Roller", cards)


ALL_SECTIONS = [
    section_annotations_events,
    section_range_selector_roller,
]
