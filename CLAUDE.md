# dygraphs

Python wrapper for the dygraphs JavaScript charting library. Core port of R dygraphs with framework adapters for Dash and Shiny.

## Package layout

- **Import name:** `dygraphs`
- **Source:** `src/dygraphs/`
- **Tests:** `tests/dygraphs/`, `tests/dash/`, `tests/integration/`
- **Examples:** `examples/`
- **Docs:** MkDocs with Material theme + mkdocstrings

## Development

```bash
uv sync --group dev          # install all deps
uv run pytest tests/         # run tests (203 tests)
uv run ruff check --fix      # lint
uv run ruff format           # format
uv run mkdocs serve          # preview docs
```

- Integration tests (`tests/integration/`) require Chrome/Selenium, skipped on CI
- Part of the `brand-toolkit` uv workspace (parent `pyproject.toml`)

## Dependencies

- **No hard dependencies** — the core works with plain lists/dicts
- `pandas` is optional (`dygraphs[pandas]`) — needed for DataFrame/Series/CSV input
- `dash` is optional (`dygraphs[dash]`) — needed for Dash adapter
- `shiny` is optional (`dygraphs[shiny]`) — needed for Shiny adapter

## Key design decisions

- **Port of R dygraphs API.** Method names mirror R pipe functions: `dy_series()`, `dy_annotation()`, `dy_shading()`, `dy_event()`, etc.
- **Builder pattern.** `Dygraph(data).dy_series(...).dy_options(...)` — chainable methods.
- **Framework-agnostic core.** `Dygraph` produces HTML/JS. Adapters for Dash and Shiny are separate subpackages.
- **Lazy imports for optional deps.** pandas, numpy, dash, shiny are imported inside functions, not at module level.

## Bundled assets

- `src/dygraphs/assets/` contains the dygraphs JavaScript library, plugins, and `dash_render.js` (the Dash clientside renderer)
- `dygraphs-js/` and `dygraphs-r/` are reference copies of the upstream JS library and R package (not part of the Python package)
- `PyDyGraphs/` is legacy code from an earlier implementation (untracked, not part of this package)

## Dash adapter architecture

The Dash integration (`src/dygraphs/dash/`) follows the R dygraphs / htmlwidgets model:

- **`dash_render.js`** — the clientside renderer, extracted to a real `.js` file (lintable, syntax-highlightable). Defines `window.dygraphsDash.render(setup, config, optsOverride)`. Read once at Python import time, inlined into each chart's clientside callback with an IIFE guard so only the first chart initialises the renderer.
- **Always destroy + recreate** — on every data update, the existing dygraph instance is destroyed and a new one is created from scratch (same as R's `renderValue`). This eliminates the "did I forget to invalidate X" class of bugs from the old in-place `updateOptions` path. Zoom can optionally be preserved via `retain_date_window=True` (default `False`, matching R).
- **`dcc.Store` + clientside callback** — the standard Dash pattern for wrapping a third-party JS library. Two stores: `{cid}-store` (canonical config) and `{cid}-opts` (runtime overrides).
- **`MULTI_CANVAS_CAPTURE_JS`** — shared JS constant in `capture.py` for DPR-aware multi-canvas PNG capture. Used by both the modebar camera button and the `dash-capture` wizard strategy (`dygraph_strategy()`).

## Test conventions for the Dash adapter

**Static checks > Selenium for regression coverage.** The Dash adapter
has been bitten multiple times by bugs that are easy to detect with
Python-side string assertions on the generated JS but expensive to
detect with a real browser (DPR math, IIFE wrapping, slice off-by-one,
shared-source drift). Selenium tests for these properties take ~55s
each and add a Chrome dependency; the equivalent static checks run in
under a millisecond and catch the same regressions.

The convention, mirroring how `dash-capture` tests itself:

- **`tests/dash/test_render_js_correctness.py`** holds *static* property
  assertions on `dash_render.js`, the strategy capture JS, and the
  Python-side shim builder. One assertion per bug class. Sub-second
  total runtime. **This is the safety net for the Dash refactor.**
- **`tests/integration/`** holds the *minimum* browser-driven tests
  needed for end-to-end sanity ("does the chart actually render"). One
  pass through Selenium per session, not per test. Gated under the
  Chrome opt-in.
- New refactors of the renderer should add a static assertion to
  `test_render_js_correctness.py` for any property they want to lock
  in, *not* a new Selenium test.

## Open TODOs (Dash adapter)

### Done
- [x] Extract renderer JS from Python f-string to `src/dygraphs/assets/dash_render.js` (~480 lines, lintable)
- [x] Switch to always-recreate update model (R-style); preserve zoom only when `retain_date_window=True`
- [x] Add `retain_date_window` Python option, default `False` to match R
- [x] Fix `__JS__:` marker slice off-by-one in both `dash_render.js` and `shiny/component.py`
- [x] Fix DPR cropping in multi-canvas capture (DPR-aware output canvas + 9-arg `drawImage`)
- [x] Fix IIFE-vs-statement bug in `dygraph_strategy()` preprocess/capture JS
- [x] Unify modebar and wizard capture paths via shared `MULTI_CANVAS_CAPTURE_JS`
- [x] Add `tests/dash/test_render_js_correctness.py` — Python-side static checks (17 assertions, 0.5s)
- [x] **Tried and reverted:** moving the renderer asset into `html.Script(_DASH_RENDER_JS)` in the layout (Phase 1.5). React doesn't execute `<script>` tags rendered through its vDOM, so the asset never initialised. Reverted to inlining in the per-chart callback body with the IIFE guard.

### Next up — small, well-defined PRs
1. **Drop hidden `dcc.Graph` sink** *(Phase 3)* — replace `Output(hidden_graph_id, "figure")` with `Output(store_id, "data", allow_duplicate=True)` + `prevent_initial_call='initial_duplicate'`. Bump `dash>=2.9.0` in `pyproject.toml`. Delete the hidden Graph component. Removes one ghost component from every chart's DOM. ~30 min.
2. **Outputs helper module** *(Phase 4)* — new file `src/dygraphs/dash/outputs.py` exporting `data(component_id)` and `opts(component_id)` that produce the right `Output` objects. Re-export from `dygraphs.dash`. Update README example. ~30 min.
3. **Centralise `processJsMarkers`** — move the recursive `__JS__:` eval walk to a single pre-pass at the top of `render()` in `dash_render.js`. Currently it's called twice (once on `opts`, once after merging the override). Easier to lint and reason about. ~15 min.
4. **Document the always-recreate model in `docs/`** — add a "Updating data from Dash callbacks" section to `docs/index.md` explaining: write to `Output(f"{cid}-store", "data")`, the chart destroys + recreates on every update, set `retain_date_window=True` if you need zoom preserved. Include the `outputs` helper from item 2 once it lands.

### Decisions deferred (revisit when there's a reason)
- **Flask blueprint serving the asset** — would let us replace `html.Script(content)` with `<script src="/dygraphs/dash_render.js">`, matching R/htmlwidgets exactly. Only worth doing once a page has many charts and the duplicated callback bodies become a payload concern.
- **Real React component (`dash-dygraph` package)** — npm/webpack toolchain, separate distribution, version-compat matrix. Worth doing if dygraphs-for-Dash adoption justifies the build pipeline. Not until then.
- **Collapse `chart-store` + `chart-opts` into one** — keeps the option for users to toggle a single setting without retransmitting data. Different from R, not strictly worse. Don't touch unless the split causes a concrete problem.
- **Selenium capture tests** — DPR/edge-probe browser tests. The static checks in `test_render_js_correctness.py` cover the same regressions; adding browser tests would be belt-and-suspenders.
- **Group sync stress tests** — multi-chart zoom propagation works in the demo. No automated coverage. Add when a regression actually happens.

### Rationale
The R dygraphs package (in `dygraphs-r/`) uses htmlwidgets, which provides: a real `.js` asset loaded once per page via `<script src>`, a single `renderValue(x)` entrypoint per chart, always-destroy-then-recreate on updates, and stateful closures for the live dygraph instance. The Dash adapter now matches this model as closely as Dash's architecture allows: store + clientside callback instead of htmlwidgets, IIFE-guarded inline instead of manifest-declared `<script src>`, and DOM-attached `_dygraphInstance` instead of a closure (because the clientside callback can't capture state across invocations the way an htmlwidgets factory can).

---

## Code style

### Imports

Order: `__future__` -> stdlib -> third-party -> local. Alphabetical within groups. Managed by ruff/isort.

```python
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

import numpy as np
from dygraphs.utils import helper_func
```

Use `TYPE_CHECKING` blocks for heavy optional deps and circular imports:

```python
if TYPE_CHECKING:
    import pandas as pd
```

### Type hints

- Use `|` union syntax (PEP 604): `str | None`, not `Optional[str]`
- Use `from __future__ import annotations` for forward references
- Use `TypeAlias` for complex types
- Annotate all public function signatures
- Return type annotations on all public functions

### Docstrings — NumPy convention

Class-level docstrings preferred over `__init__`. Sections: Parameters, Returns, Raises, Examples, See Also, Notes.

```python
def dy_series(
    self,
    name: str,
    *,
    color: str | None = None,
    stroke_width: float | None = None,
) -> Dygraph:
    """Configure display options for a named series.

    Parameters
    ----------
    name : str
        Series name (must match a column label).
    color : str | None, optional
        CSS color string. By default None.
    stroke_width : float | None, optional
        Line width in pixels. By default None.

    Returns
    -------
    Dygraph
        Self, for chaining.
    """
```

### Naming

| What | Convention | Example |
|------|-----------|---------|
| Functions, variables | `snake_case` | `dy_series`, `stroke_width` |
| Classes | `CapitalCase` | `Dygraph`, `DashDygraph` |
| Constants | `UPPER_CASE` | `POINT_SHAPES` |
| Private/internal | `_leading_underscore` | `_normalise_data`, `_format` |

### Line length

88 characters. Enforced by ruff.

### Testing

- Class-based grouping for related tests
- One assertion per test (mostly)
- No `__init__.py` in test dirs
- No docstrings required on test methods
- Parametrize for multi-value tests

### Toolchain

| Tool | Purpose | Command |
|------|---------|---------|
| uv | Package manager | `uv sync`, `uv run pytest` |
| ruff | Linting + formatting | `ruff check --fix`, `ruff format` |
| ty | Type checking | `uv run ty check` |
| prek | Pre-commit hooks | `prek run` |
| pytest | Testing | `uv run pytest` |
| setuptools-scm | Versioning from git tags | automatic |
| MkDocs | Documentation | `uv run mkdocs serve` |
