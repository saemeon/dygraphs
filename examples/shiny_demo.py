"""Shiny for Python demo showcasing pydygraphs.

Run with::

    uv run shiny run examples/shiny_demo.py

Then open http://127.0.0.1:8000 in your browser.

Requires: ``pip install pydygraphs[shiny]``
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from shiny import App, Inputs, Outputs, Session, reactive, ui

from pydygraphs import Dygraph
from pydygraphs.shiny import dygraph_ui, render_dygraph

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

app_ui = ui.page_fluid(
    ui.h1("pydygraphs + Shiny for Python"),
    ui.p("Reactive dygraphs chart with Shiny slider control."),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_slider("trend", "Trend:", min=-2, max=2, value=0, step=0.5),
            ui.input_slider("points", "Data points:", min=30, max=180, value=90, step=10),
            ui.input_checkbox("fill", "Fill graph", value=True),
            ui.input_checkbox("draw_points", "Draw points", value=False),
        ),
        dygraph_ui("chart1", height="350px"),
        dygraph_ui("chart2", height="250px"),
    ),
)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------


def server(input: Inputs, output: Outputs, session: Session):
    @reactive.effect
    async def update_chart1():
        np.random.seed(42)
        n = input.points()
        trend = input.trend()
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        df = pd.DataFrame(
            {
                "Temperature": (15 + np.cumsum(trend + np.random.randn(n) * 0.5)).round(2),
                "Humidity": (50 + np.cumsum(trend * 0.5 + np.random.randn(n) * 0.3)).round(2),
            },
            index=dates,
        )

        dg = (
            Dygraph(df, title="Temperature & Humidity")
            .options(
                fill_graph=input.fill(),
                draw_points=input.draw_points(),
                stroke_width=2,
                colors=["#00d4aa", "#f4a261"],
                animated_zooms=True,
            )
            .axis("y", label="Value")
            .legend(show="always")
            .range_selector(height=25)
            .annotation(
                dates[n // 2].isoformat(),
                "M",
                tooltip="Midpoint",
                series="Temperature",
            )
            .shading(
                dates[n // 4].isoformat(),
                dates[n // 3].isoformat(),
                color="rgba(200,200,255,0.3)",
            )
        )

        await render_dygraph(session, "chart1", dg)

    @reactive.effect
    async def update_chart2():
        np.random.seed(7)
        n = input.points()
        trend = input.trend()
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        df = pd.DataFrame(
            {
                "Pressure": (1013 + np.cumsum(trend * 0.1 + np.random.randn(n) * 0.2)).round(1),
            },
            index=dates,
        )

        dg = (
            Dygraph(df, title="Atmospheric Pressure")
            .options(
                fill_graph=False,
                stroke_width=2,
                colors=["#7eb8f7"],
            )
            .axis("y", label="hPa")
            .legend(show="always")
            .range_selector(height=25)
            .limit(1013.0, "Sea level", color="#e74c3c", stroke_pattern="dotted")
        )

        await render_dygraph(session, "chart2", dg)


app = App(app_ui, server)
