"""Store-id conventions for dygraphs Dash charts.

Each chart created with :class:`DygraphChart` is an ``html.Div`` wrapping
two siblings:

- ``dcc.Store(id={id})`` — canonical config (data + attrs). Target with
  ``Output(chart, "data")`` (the wrapper's identity) or the equivalent
  ``Output("my-chart", "data")``.
- ``html.Div(id={id}-container)`` — the DOM container the dygraphs JS
  renders into.

One write surface: every change (data, attrs, styling) goes through
the store's ``data`` prop. The wrapper uses
``dash_wrap.ComponentWrapper`` — no helpers needed on the callback side,
and no magic beyond what dash-wrap documents (``_set_random_id`` +
``__class__`` spoof).
"""
