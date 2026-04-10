"""
Basic line chart
================

The minimal recipe. Pass a pandas DataFrame with a ``DatetimeIndex``
to :class:`~dygraphs.Dygraph` and you get an interactive
time-series chart with sensible defaults: zoom via click-drag, pan
via shift-drag, hover legend, and automatic colours.

Everything else is configuration on top of this starting point.
"""

import numpy as np
import pandas as pd

from dygraphs import Dygraph

# %%
# Build some synthetic weather data — three 90-day series with a
# random walk each, so the chart has something interesting to show.
rng = np.random.default_rng(42)
dates = pd.date_range("2024-01-01", periods=90, freq="D")
df = pd.DataFrame(
    {
        "temperature": 20 + np.cumsum(rng.standard_normal(90) * 0.6),
        "humidity": 60 + np.cumsum(rng.standard_normal(90) * 0.4),
        "pressure": 1013 + np.cumsum(rng.standard_normal(90) * 0.3),
    },
    index=dates,
).round(2)

# %%
# One line — builder pattern, no options required.

chart = Dygraph(df, title="Weather station — 90 days")
