import dash
import pandas as pd
import snbplt
from dash import html
from dash_capture import capture_element

from dygraphs import Dygraph, Legend, Options, RangeSelector
from dygraphs.dash import DygraphChart, DyModebarButton, dygraph_strategy

START_DATE = pd.Timestamp("2023-01-01")
forecast_start = pd.Timestamp("2024-01-01")
forecast_end = pd.Timestamp("2025-01-01")
round_decimals = 2

df_to_plot = pd.DataFrame(
    {"actual": [1.0, 1.2, 1.1, 1.3], "forecast": [None, None, 1.15, 1.35]},
    index=pd.date_range("2023-01-01", periods=4, freq="QS"),
)

chart = (
    Dygraph(
        df_to_plot,
        group="forecast-revision-lineplots",
        legend=Legend(show="follow", labels_separate_lines=True),
        options=Options(
            digits_after_decimal=round_decimals,
            labels_utc=True,
            legend_follow_offset_x=100,
            legend_follow_offset_y=50,
            axis_line_color="#FFFFFF",
            axis_label_font_size=12,
            right_gap=3,
        ),
        range_selector=RangeSelector(
            date_window=(START_DATE, df_to_plot.index[-1]), height=30
        ),
    )
    .shading(from_=forecast_start, to=forecast_end, color=snbplt.Farben.gray10)
    .axis("y", axis_label_width=30)
)

chart_component = DygraphChart(chart, id="my-chart", height="400px")


def renderer(
    _target,
    _snapshot_img,
    width: int = 1200,
    height: int = 400,
    capture_width: int = 1200,
    capture_height: int = 400,
):
    _target.write(_snapshot_img())


def resolve(width: int = 1200, height: int = 400, **_):
    return {"capture_width": width, "capture_height": height}


app = dash.Dash(__name__)
app.layout = html.Div(
    [
        chart_component,
        capture_element(
            "my-chart-container",
            renderer=renderer,
            capture_resolver=resolve,
            trigger=DyModebarButton(graph_id="my-chart", tooltip="Save"),
            strategy=dygraph_strategy(strip_margin=True),
            filename="forecast.png",
        ),
    ]
)

if __name__ == "__main__":
    app.run(debug=True)
