"""Store-id conventions for dygraphs Dash charts.

Each chart created with :class:`DygraphChart` (or
:func:`dygraph_to_dash` / :meth:`Dygraph.to_dash`) is an
``html.Div`` wrapping three siblings:

- ``dcc.Store(id={id})`` — canonical config (data + attrs). Target with
  ``Output(chart, "data")`` (the wrapper's identity) or the equivalent
  ``Output("my-chart", "data")``.
- ``dcc.Store(id={id}-opts)`` — runtime overrides. Target with
  ``Output(chart.opts, "data")`` or ``Output("my-chart-opts", "data")``.
- ``html.Div(id={id}-container)`` — the DOM container the dygraphs JS
  renders into.

The wrapper uses ``dash_wrap.ComponentWrapper`` — no helpers needed on
the callback side, and no magic beyond what dash-wrap documents
(``_set_random_id`` + ``__class__`` spoof).
"""
