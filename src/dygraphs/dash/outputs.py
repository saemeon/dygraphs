"""Store-id conventions for dygraphs Dash charts.

Each chart created with :class:`DyGraph` (or :func:`dygraph_to_dash` /
:meth:`Dygraph.to_dash`) is backed by two ``dcc.Store`` components:

- ``{id}`` — canonical config (data + attrs).  Target with
  ``Output("my-chart", "data")``.
- ``{id}-opts`` — runtime overrides.  Target with
  ``Output("my-chart-opts", "data")``.

Both use standard Dash ``Output`` / ``Input`` — no helpers needed.
"""
