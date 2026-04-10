"""
Styling and per-series options
==============================

Chain ``.options()`` and ``.series()`` calls on top of the base
chart to customise colours, stroke widths, fills, and axes. Each
method returns ``self``, mirroring R's ``%>%`` pipe style.

The `R dygraphs package <https://rstudio.github.io/dygraphs/>`_
uses ``dyOptions()`` and ``dySeries()`` for the same purpose; the
Python method names drop the ``dy`` prefix because they already
live on a ``Dygraph`` instance.
"""

import numpy as np
import pandas as pd

from dygraphs import Dygraph

rng = np.random.default_rng(7)
dates = pd.date_range("2024-01-01", periods=120, freq="D")
df = pd.DataFrame(
    {
        "revenue": 100 + np.cumsum(rng.standard_normal(120) * 2),
        "cost": 60 + np.cumsum(rng.standard_normal(120) * 1.3),
    },
    index=dates,
).round(2)

# %%
# Fill the area under each series, bump the stroke width, and pick
# hand-chosen colours. ``.series()`` customises a single named
# series; here we make cost dashed to distinguish it from revenue.

chart = (
    Dygraph(df, title="Revenue vs Cost")
    .options(fill_graph=True, fill_alpha=0.2, stroke_width=2.5)
    .series("revenue", color="#00d4aa")
    .series("cost", color="#f76e8a", stroke_pattern="dashed")
    .legend(show="always")
    .range_selector(height=30)
)
