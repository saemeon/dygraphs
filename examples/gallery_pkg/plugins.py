"""Plugins chapter — unzoom, crosshair, ribbon, rebase, series groups, callbacks."""

from __future__ import annotations

from dygraphs import Dygraph

from ._common import ChartList, Section, _html, _ts


def section_plugins() -> Section:
    cards: ChartList = []

    base = _ts(["Signal"])

    cards.append(
        (
            "Unzoom button (zoom in, then click button)",
            _html(
                Dygraph(base, title="Unzoom Plugin")
                .unzoom()
                .options(colors=["#2ecc71"])
            ),
        )
    )

    cards.append(
        (
            "Crosshair (vertical)",
            _html(
                Dygraph(base, title="Crosshair: vertical")
                .crosshair(direction="vertical")
                .options(colors=["#3498db"])
            ),
        )
    )

    cards.append(
        (
            "Crosshair (both)",
            _html(
                Dygraph(base, title="Crosshair: both")
                .crosshair(direction="both")
                .options(colors=["#e67e22"])
            ),
        )
    )

    cards.append(
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

    cards.append(
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

    cards.append(
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

    return ("13. Plugins", cards)


def section_series_groups() -> Section:
    cards: ChartList = []

    df_g = _ts(["Sensor A", "Sensor B", "Sensor C", "Baseline"])

    cards.append(
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

    cards.append(
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

    return ("14. Series Groups", cards)


def section_callbacks() -> Section:
    cards: ChartList = []

    cards.append(
        (
            "Click callback (check browser console)",
            _html(
                Dygraph(_ts(["Value"]), title="Click Callback (see console)")
                .callbacks(
                    click="function(e, x, pts){ console.log('Clicked:', x, pts); }"
                )
                .options(colors=["#16a085"])
            ),
        )
    )

    cards.append(
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

    return ("15. Callbacks", cards)


ALL_SECTIONS = [
    section_plugins,
    section_series_groups,
    section_callbacks,
]
