"""
Annotations, events, and shadings
=================================

Decorate a chart with markers that call out moments in the data:

- :meth:`.annotation` pins a short label to a point on a series
  (mirrors R's ``dyAnnotation``).
- :meth:`.event` draws a full-height vertical line with a label
  near the top (mirrors ``dyEvent``).
- :meth:`.shading` paints a background region between two x-values
  (mirrors ``dyShading``).
- :meth:`.limit` draws a horizontal reference line at a y-value
  (mirrors ``dyLimit``).

All four accept ISO date strings and chain naturally.
"""

import numpy as np
import pandas as pd

from dygraphs import Dygraph

rng = np.random.default_rng(1)
dates = pd.date_range("2024-01-01", periods=120, freq="D")
df = pd.DataFrame(
    {"price": 100 + np.cumsum(rng.standard_normal(120) * 1.2)},
    index=dates,
).round(2)

# %%
# Chain every overlay type together. The `color` and
# `stroke_pattern` kwargs on events / limits / shadings map to the
# same dygraphs JS options R's wrappers do.

chart = (
    Dygraph(df, title="Price history with overlays")
    .options(stroke_width=2, colors=["#2563eb"])
    .annotation("2024-02-14", "Valentine's", tooltip="+5% above MA-20")
    .event("2024-03-15", label="Earnings call", color="#f76e8a")
    .shading("2024-04-01", "2024-04-15", color="rgba(251, 191, 36, 0.18)")
    .limit(100.0, label="Baseline", color="#10b981", stroke_pattern="dashed")
    .range_selector(height=30)
)
