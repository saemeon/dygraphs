"""Plotters chapter — bar charts, series-level, group-level, candlestick, error bars."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dygraphs import Dygraph

from ._common import _DATES, _RNG, ChartList, Section, _html, _ts


def section_bar_chart_plotters() -> Section:
    cards: ChartList = []

    bar_df = _ts(["Alpha", "Beta", "Gamma"])

    cards.append(
        (
            "Bar chart (auto multi-column)",
            _html(Dygraph(bar_df, title="Bar Chart (multi-series auto)").bar_chart()),
        )
    )

    cards.append(
        (
            "Stacked bar chart",
            _html(
                Dygraph(bar_df, title="Stacked Bar Chart")
                .stacked_bar_chart()
                .options(colors=["#e74c3c", "#3498db", "#2ecc71"])
            ),
        )
    )

    cards.append(
        (
            "Multi-column (explicit)",
            _html(Dygraph(bar_df, title="Multi-Column").multi_column()),
        )
    )

    cards.append(
        (
            "Single-series bar chart",
            _html(
                Dygraph(
                    pd.DataFrame(
                        {"Sales": _RNG.integers(10, 50, 20)}, index=_DATES[:20]
                    ),
                    title="Single-Series Bar",
                ).bar_chart()
            ),
        )
    )

    return ("8. Bar Chart Plotters", cards)


def section_series_level_plotters() -> Section:
    cards: ChartList = []

    df_two = _ts(["Line", "Special"])

    cards.append(
        (
            "bar_series (one series as bars)",
            _html(
                Dygraph(df_two, title="bar_series on 'Special'").bar_series("Special")
            ),
        )
    )

    cards.append(
        (
            "stem_series",
            _html(
                Dygraph(df_two, title="stem_series on 'Special'").stem_series("Special")
            ),
        )
    )

    cards.append(
        (
            "shadow (fill only, no line)",
            _html(Dygraph(df_two, title="shadow on 'Special'").shadow("Special")),
        )
    )

    cards.append(
        (
            "filled_line",
            _html(
                Dygraph(df_two, title="filled_line on 'Special'").filled_line("Special")
            ),
        )
    )

    cards.append(
        (
            "error_fill",
            _html(
                Dygraph(df_two, title="error_fill on 'Special'").error_fill("Special")
            ),
        )
    )

    return ("9. Series-Level Plotters", cards)


def section_group_level_plotters() -> Section:
    cards: ChartList = []

    df_grp = _ts(["X", "Y", "Z"])

    cards.append(
        (
            "multi_column_group",
            _html(
                Dygraph(
                    df_grp, title="multi_column_group(['X','Y'])"
                ).multi_column_group(["X", "Y"])
            ),
        )
    )

    cards.append(
        (
            "stacked_bar_group",
            _html(
                Dygraph(df_grp, title="stacked_bar_group(['X','Y'])").stacked_bar_group(
                    ["X", "Y"]
                )
            ),
        )
    )

    cards.append(
        (
            "stacked_line_group",
            _html(
                Dygraph(
                    df_grp, title="stacked_line_group(['X','Y'])"
                ).stacked_line_group(["X", "Y"])
            ),
        )
    )

    cards.append(
        (
            "stacked_ribbon_group",
            _html(
                Dygraph(
                    df_grp, title="stacked_ribbon_group(['X','Y'])"
                ).stacked_ribbon_group(["X", "Y"])
            ),
        )
    )

    return ("10. Group-Level Plotters", cards)


def section_candlestick() -> Section:
    cards: ChartList = []

    ohlc = pd.DataFrame(
        {
            "Open": (100 + _RNG.standard_normal(60).cumsum()).round(2),
            "High": (102 + _RNG.standard_normal(60).cumsum()).round(2),
            "Low": (98 + _RNG.standard_normal(60).cumsum()).round(2),
            "Close": (100 + _RNG.standard_normal(60).cumsum()).round(2),
        },
        index=pd.date_range("2024-01-01", periods=60, freq="D"),
    )

    cards.append(
        (
            "Candlestick",
            _html(Dygraph(ohlc, title="Candlestick Chart").candlestick()),
        )
    )

    cards.append(
        (
            "Candlestick with compress",
            _html(
                Dygraph(ohlc, title="Candlestick + Compress Plugin").candlestick(
                    compress=True
                )
            ),
        )
    )

    cards.append(
        (
            "candlestick_group",
            _html(
                Dygraph(
                    ohlc, title="candlestick_group(['Open','High','Low','Close'])"
                ).candlestick_group(["Open", "High", "Low", "Close"])
            ),
        )
    )

    return ("11. Candlestick Charts", cards)


def section_error_bars() -> Section:
    cards: ChartList = []

    y_vals = 20 + _RNG.standard_normal(40).cumsum()
    eb_df = pd.DataFrame(
        {
            "low": (y_vals - np.abs(_RNG.standard_normal(40))).round(2),
            "mid": y_vals.round(2),
            "high": (y_vals + np.abs(_RNG.standard_normal(40))).round(2),
        },
        index=_DATES[:40],
    )

    cards.append(
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

    cards.append(
        (
            "Error bars (2 columns: value, error)",
            _html(
                Dygraph(eb_df2, title="Error Bars via columns=")
                .series(columns=["value", "error"], color="#3498db")
                .legend(show="always")
            ),
        )
    )

    return ("12. Error Bars", cards)


ALL_SECTIONS = [
    section_bar_chart_plotters,
    section_series_level_plotters,
    section_group_level_plotters,
    section_candlestick,
    section_error_bars,
]
