"""
Error bands from 3 columns
==========================

Pass a list of three column names to ``.series()`` to turn them
into a single custom-bar series (low / mid / high). This is the
Python equivalent of R's idiom ::

    dySeries(c("lwr", "fit", "upr"))

The three source columns are collapsed into one series carrying a
``[low, mid, high]`` triple per row, and dygraphs renders the
shaded band automatically.
"""

import numpy as np
import pandas as pd

from dygraphs import Dygraph

# %%
# Forecast data with a 95% prediction interval. Not real data —
# just shaped like what a time-series forecaster would produce.
rng = np.random.default_rng(2024)
dates = pd.date_range("2024-01-01", periods=60, freq="D")
trend = np.linspace(10, 25, 60)
noise = rng.standard_normal(60) * 1.5
fit = trend + noise
sigma = np.linspace(1.0, 4.0, 60)

df = pd.DataFrame(
    {
        "lwr": (fit - 1.96 * sigma).round(2),
        "fit": fit.round(2),
        "upr": (fit + 1.96 * sigma).round(2),
    },
    index=dates,
)

# %%
# ``.series([names])`` is the R-style shortcut. The three columns
# are collapsed, ``customBars=True`` is set automatically, and
# dygraphs renders the shaded band under the central line.

chart = (
    Dygraph(df, title="60-day forecast with 95% interval")
    .series(["lwr", "fit", "upr"], label="forecast")
    .options(colors=["#7eb8f7"], stroke_width=2)
    .legend(show="always")
)
