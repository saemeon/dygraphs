# dygraphs

Python port of the R **dygraphs** package, wrapping the dygraphs JavaScript
charting library. Framework adapters for Dash and Shiny.

## Project goal — R feature parity

The north star is **feature-complete parity with the R dygraphs package**, with
a Python API that stays as close to R's as Python idioms allow. Concretely:

- **Function-level parity.** Every exported `dy*` function in R has a
  corresponding method on the Python `Dygraph` class. See *R ↔ Python API
  mapping* below.
- **Behavior parity.** The JSON config emitted by Python should structurally
  match what R's `dygraph()` produces for equivalent inputs. The gold standard
  is `tests/integration/test_r_parity.py`, which shells out to `Rscript` and
  diffs the two outputs.
- **Naming convention.** R uses `camelCase` and a mandatory `dy` prefix
  (`dyOptions`, `dySeries`, …); Python uses `snake_case` and **drops the `dy`
  prefix** because the methods already live on a `Dygraph` instance. So
  `dygraph %>% dyOptions(stackedGraph = TRUE)` becomes
  `Dygraph(...).options(stacked_graph=True)`. The mapping is mechanical and
  documented in the table below.
- **Constructor parameter renames.** Audited against R's `dygraph()` —
  there is exactly **one** rename: R's `main` → Python's `title`. Every
  other parameter (`data`, `xlab`, `ylab`, `periodicity`, `group`, `width`,
  `height`) keeps its R name verbatim. R's `elementId` has no Python
  equivalent because the Dash/Shiny adapters manage component IDs
  themselves. Last audited against `dygraphs-r/R/dygraph.R`.

Anything that diverges from R is either (a) a Pythonic naming change covered
by the mapping, or (b) deliberately documented as a Python-only addition (the
declarative API, the Dash/Shiny adapters, `to_dict`/`to_json`/`to_html`).

## Package layout

- **Import name:** `dygraphs`
- **Source:** `src/dygraphs/`
  - `dygraph.py` — the `Dygraph` builder class (~3.5k lines, intentionally
    monolithic to mirror the R API 1:1; do not split without a parity reason)
  - `declarative.py` — dataclasses (`Options`, `Axis`, `Series`, `Legend`, …)
    that mirror every builder method, so users can pass `Dygraph(df,
    options=Options(...), series=[Series(...)])` instead of chaining. Pure
    Python sugar — no R analogue.
  - `dash/`, `shiny/` — framework adapters (see below)
  - `assets/` — bundled JS/CSS, plus `dash_render.js`
- **Tests:** `tests/dygraphs/`, `tests/dash/`, `tests/integration/`
- **Examples:** `examples/`
- **Docs:** MkDocs with Material theme + mkdocstrings

## Development

```bash
uv sync --group dev          # install all deps
uv run pytest tests/         # run tests (~520 collected)
uv run ruff check --fix      # lint
uv run ruff format           # format
uv run mkdocs serve          # preview docs
```

- Integration tests under `tests/integration/` are gated:
  - `test_chrome_smoke.py`, `test_browser_render.py`, etc. require
    Chrome/Selenium and are skipped without it
  - `test_r_parity.py` requires `Rscript` + the R `dygraphs` package and is
    skipped without them — but **this is the canonical parity test**, so run
    it locally before any change that touches the JSON output of `Dygraph`
- Part of the `brand-toolkit` uv workspace (parent `pyproject.toml`)

## Dependencies

- **No hard dependencies** — the core works with plain lists/dicts
- `pandas` is optional (`dygraphs[pandas]`) — needed for DataFrame/Series/CSV input
- `dash` is optional (`dygraphs[dash]`) — needed for Dash adapter
- `shiny` is optional (`dygraphs[shiny]`) — needed for Shiny adapter

## Key design decisions

- **Port of the R dygraphs API.** Every exported R `dy*` function maps to a
  Python method with the `dy` prefix removed and the name `snake_case`d:
  `dyOptions` → `.options()`, `dySeries` → `.series()`, `dyRangeSelector` →
  `.range_selector()`. See *R ↔ Python API mapping* below.
- **Builder pattern.** `Dygraph(data).series(...).options(...)` — chainable
  methods, equivalent to R's `dygraph(data) %>% dySeries(...) %>% dyOptions(...)`.
- **Declarative alternative.** `Dygraph(data, options=Options(...),
  series=[Series(...)])` is sugar over the builder, using the dataclasses in
  `declarative.py`. Users can mix and match.
- **Framework-agnostic core.** `Dygraph` produces HTML/JS. Adapters for Dash
  and Shiny are separate subpackages with no impact on the core.
- **Lazy imports for optional deps.** pandas, numpy, dash, shiny are imported
  inside functions, not at module level.

## Bundled assets and reference clones

- `src/dygraphs/assets/` — vendored runtime: the dygraphs JavaScript library,
  plugins, `dygraph.css`, `moment.min.js`, and `dash_render.js` (the Dash
  clientside renderer). Shipped with the wheel.
- `dygraphs-r/` and `dygraphs-js/` — **vendored reference copies** of the
  upstream R package (`rstudio/dygraphs`) and JS library (`danvk/dygraphs`),
  checked into the repo for parity work. Source of truth when porting
  features and resolving parity questions. Excluded from the wheel via
  `tool.setuptools.packages.find` (`where = ["src"]`), so they never ship
  to end users — they just come along when you clone the repo for
  development.
- `PyDyGraphs/` — legacy code from an earlier implementation; gitignored, not
  part of this package.

## R ↔ Python API mapping

Audited against `dygraphs-r/NAMESPACE` (37 exported `dy*` functions plus the
`dygraph` constructor). Mapping rule: drop `dy`, snake_case the rest. The
table groups by source file in `dygraphs-r/R/`.

| R function | Python method | R source | Status |
|---|---|---|---|
| `dygraph(data, ...)` | `Dygraph(data, ...)` | `dygraph.R` | ✅ (see *Constructor parity*) |
| `dyOptions` | `.options()` | `options.R` | ✅ |
| `dyAxis` | `.axis()` | `axis.R` | ✅ |
| `dySeries` | `.series()` | `series.R` | ✅ |
| `dyGroup` | `.group()` | `group.R` | ✅ |
| `dyLegend` | `.legend()` | `legend.R` | ✅ |
| `dyHighlight` | `.highlight()` | `highlight.R` | ✅ |
| `dyAnnotation` | `.annotation()` | `annotation.R` | ✅ |
| `dyShading` | `.shading()` | `shading.R` | ✅ |
| `dyEvent` | `.event()` | `event.R` | ✅ |
| `dyLimit` | `.limit()` | `event.R` | ✅ |
| `dyRangeSelector` | `.range_selector()` | `range-selector.R` | ✅ |
| `dyRoller` | `.roller()` | `roller.R` | ✅ |
| `dyCallbacks` | `.callbacks()` | `callbacks.R` | ✅ |
| `dyCSS` | `.css()` | `css.R` | ✅ |
| `dyBarChart` | `.bar_chart()` | `candlestick.R` | ✅ |
| `dyStackedBarChart` | `.stacked_bar_chart()` | `candlestick.R` | ✅ |
| `dyMultiColumn` | `.multi_column()` | `candlestick.R` | ✅ |
| `dyBarSeries` | `.bar_series()` | `candlestick.R` | ✅ |
| `dyStemSeries` | `.stem_series()` | `candlestick.R` | ✅ |
| `dyShadow` | `.shadow()` | `candlestick.R` | ✅ |
| `dyFilledLine` | `.filled_line()` | `candlestick.R` | ✅ |
| `dyErrorFill` | `.error_fill()` | `candlestick.R` | ✅ |
| `dyCandlestick` | `.candlestick()` | `candlestick.R` | ✅ |
| `dyMultiColumnGroup` | `.multi_column_group()` | `candlestick.R` | ✅ |
| `dyCandlestickGroup` | `.candlestick_group()` | `candlestick.R` | ✅ |
| `dyStackedBarGroup` | `.stacked_bar_group()` | `candlestick.R` | ✅ |
| `dyStackedLineGroup` | `.stacked_line_group()` | `candlestick.R` | ✅ |
| `dyStackedRibbonGroup` | `.stacked_ribbon_group()` | `candlestick.R` | ✅ |
| `dyUnzoom` | `.unzoom()` | `plugins.R` | ✅ |
| `dyCrosshair` | `.crosshair()` | `plugins.R` | ✅ |
| `dyRibbon` | `.ribbon()` | `plugins.R` | ✅ |
| `dyRebase` | `.rebase()` | `rebase.R` | ✅ |
| `dyPlugin` | `.plugin()` | `plugins.R` | ✅ |
| `dyPlotter` | `.custom_plotter()` | `plotters.R` | ✅ (named `custom_plotter` to avoid clash with the constructor's `plotter=` kwarg) |
| `dyDataHandler` | `.data_handler()` | `plotters.R` | ✅ |
| `dySeriesData` | `.series_data()` | `series.R` | ✅ |
| `dyDependency` | `.dependency()` | `dependency.R` | ✅ |

**Function-level parity: 37 / 37 (100%).** Every exported R `dy*` function
has a Python equivalent. `.dependency()` takes the pieces of R's
`htmltools::htmlDependency` directly (`name`, `version`, `src`, `script`,
`stylesheet`), reads referenced files eagerly, and inlines them as
`<script>` / `<style>` tags in `to_html()` output.

### Constructor parity

R's `dygraph(data, main, xlab, ylab, periodicity, group, elementId, width,
height)` vs Python's `Dygraph(data, title, xlab, ylab, periodicity, group,
width, height, ...)`:

- ✅ `data`, `xlab`, `ylab`, `periodicity`, `group`, `width`, `height` —
  direct mapping.
- ✅ `main` → `title` (Python rename; documented).
- ✅ `periodicity` accepts `"yearly"`, `"quarterly"`, `"monthly"`,
  `"weekly"`, `"daily"`, `"hourly"`, `"minute"`, `"seconds"`,
  `"milliseconds"` (matches `xts::periodicity$scale`). Defaults to
  `None` = auto-detect from the pandas index. Only meaningful for
  date-formatted data; passing it with numeric data raises `ValueError`.
- N/A `elementId` — R's htmlwidgets needs an explicit DOM id; Python adapters
  manage their own component IDs (`cid` for Dash, output id for Shiny).

### Behavior parity (per-parameter)

The function-level table only proves the methods *exist*. Per-parameter
behavior (does `.options(stacked_graph=True)` produce the same JSON as
`dyOptions(stackedGraph = TRUE)`?) is enforced by
`tests/integration/test_r_parity.py`, which shells out to `Rscript` and diffs
the JSON output. **Run that file before any change to `dygraph.py` that
touches the emitted config.** If it's red, parity has regressed.

The previous parameter-level audit lives in
`tests/dygraphs/test_coverage_gaps.py` (point shape serialisation, axis
options branches, group options, annotation fields, range selector edges, CSS
emission, `to_html` variants, JSON edge cases, ribbon plugin options).

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

## Open TODOs

**Lifecycle policy.** When a "Next up" item ships, move it to "Done". When
"Done" items predate the most recent release, delete them — the git history is
the long-term record. Don't let either subsection grow unbounded.

### Primary track — R parity

These are the only items that move us toward the stated north star.

#### Done (recent)
- [x] **Port `dyDependency`.** `.dependency(name, version, src=None,
  script=None, stylesheet=None)` takes the pieces of R's
  `htmltools::htmlDependency` directly, reads the referenced files eagerly,
  and inlines them as `<script>` / `<style>` tags before the main chart
  script in `to_html()` output. Pushes function-level parity to 37/37.
- [x] **`periodicity=` constructor override.** Closes the last constructor
  parity gap. Accepts the nine string values emitted by
  `xts::periodicity$scale` (`"yearly"`, `"quarterly"`, `"monthly"`,
  `"weekly"`, `"daily"`, `"hourly"`, `"minute"`, `"seconds"`,
  `"milliseconds"`); `None` = auto-detect (default). Validated against
  `_VALID_PERIODICITIES`; raises on numeric data.
- [x] **Audit `test_r_parity.py` coverage.** Cross-referenced the file
  against the 37-row mapping table. Was covering 18 of 37 methods at the
  start of the audit; added 14 new test cases across 5 new classes to
  cover the previously-untested high-value methods: `periodicity=`
  override, `dyDependency`, `dyCSS`, the four chart-level plotters
  (`dyBarChart`, `dyStackedBarChart`, `dyMultiColumn`, `dyCandlestick`),
  and the five series-level plotters (`dyBarSeries`, `dyStemSeries`,
  `dyShadow`, `dyFilledLine`, `dyErrorFill`). Remaining gaps are tracked
  below.
- [x] **Verify constructor parameter renames are documented.** Audited
  Python `Dygraph.__init__` against R `dygraph()`. Only one rename:
  `main` → `title`. Documented in the "Naming convention" subsection.

#### Next up
1. **Cover the remaining R parity gaps in `test_r_parity.py`.** Methods
   still without an R-vs-Python comparison test:
   - `dyMultiColumnGroup`, `dyCandlestickGroup`, `dyStackedBarGroup`,
     `dyStackedLineGroup`, `dyStackedRibbonGroup` — all use the same
     "apply group plotter" pattern; one parametrized test class would
     cover them.
   - `dyPlugin` (the bare wrapper, not via Crosshair/Ribbon/Rebase),
     `dyPlotter` (custom plotter, not via the chart-level family),
     `dyDataHandler`, `dySeriesData` — single-method one-offs.
   None are parity-blocking, but coverage is the only way to catch
   per-parameter regressions before users do.

#### Known structural divergences (not bugs, just things to remember)
- **Plotter storage.** R stores the plotter NAME string in `x$plotter`
  (e.g. `"BarChart"`); Python stores a `JS("Dygraph.Plotters.X")`
  namespace lookup so the JS resolves it at render time. Both reach the
  same runtime function, but the JSON shapes differ. The R parity
  comparisons in `TestPlotterFamily` and `TestSeriesPlotterFamily` are
  intentionally structural ("plotter is set"), not byte-for-byte.
- **`shadow` and `filled_line` share the same plotter name in Python**
  (`filledlineplotter`). R uses two distinct JS files (`fillplotter.js`
  vs `filledline.js`). Smoke-checked during the parity audit; flagging
  here in case it's actually a Python bug rather than a deliberate
  consolidation. Worth a short investigation when someone has time.

### Tertiary track — Pythonic UX polish

Small Python-side improvements that don't move the parity needle but
make the package feel less rough to a Python user. Surfaced by an end-
to-end UX review against R's `dygraphs` workflow.

#### Done (recent)
- [x] **R-style error-band positional list.** `.series(["lwr","fit","upr"])`
  is now sugar for `.series(columns=["lwr","fit","upr"])`, mirroring R's
  `dySeries(c("lwr","fit","upr"))`. Strings are explicitly excluded so
  `.series("name")` still works. Caught a real R-parity gap masquerading
  as a function-level tick.
- [x] **Jupyter auto-display.** `_repr_html_` returns `to_html()` so
  charts render inline when they're the last expression in a notebook
  cell — same UX as `dygraph(...)` in RStudio's viewer. Plus an explicit
  `.show()` for non-last-expression cases that uses `IPython.display.HTML`
  when available and prints a hint otherwise.
- [x] **`.css()` accepts raw CSS strings.** Previously it required a
  file path; passing raw CSS crashed with `FileNotFoundError`. Now
  detects raw strings via the presence of `{` (any string with no
  braces is treated as a path, matching R). `Path` objects always read
  from disk.
- [x] **Split `examples/gallery.py` into a 5-chapter package.** The
  monolithic 1329-line script became `examples/gallery_pkg/` with one
  module per theme: `basics` (data input, styling, point shapes, axes,
  legend), `overlays` (annotations / events / shadings, range
  selector + roller), `plotters` (bar / series / group / candlestick /
  error bars), `plugins` (plugins, series groups, callbacks), and
  `api` (everything else: formatting, interaction, stacked,
  declarative, copy/update, custom plotter, series data, css, grid,
  to_html). Each chapter exposes `ALL_SECTIONS`, a list of zero-arg
  functions returning `(title, charts)` tuples; the package
  `__init__.py` walks them in order. Output is **byte-identical** to
  the old gallery (verified at 13.4 MB).

#### Next up
1. **Document the `.group()` vs `group=` collision.** `Dygraph(df,
   group="sync-name")` is the *sync-group* kwarg (mirrors R's
   `dygraph(group=)`); `.group([...])` is the `dyGroup` port for
   styling a set of series together. Same name, very different
   behaviour. Either alias one of them or add a prominent warning to
   both docstrings.

### Secondary track — Dash adapter cleanup

Smaller infrastructure items in the Dash subpackage. Not parity-blocking, but
worth doing while the renderer is fresh in someone's head.

#### Done (recent)
- [x] Extract renderer JS from Python f-string to
  `src/dygraphs/assets/dash_render.js` (~480 lines, lintable)
- [x] Switch to always-recreate update model (R-style); preserve zoom only when
  `retain_date_window=True`
- [x] Add `retain_date_window` Python option, default `False` to match R
- [x] Fix `__JS__:` marker slice off-by-one in both `dash_render.js` and
  `shiny/component.py`
- [x] Fix DPR cropping in multi-canvas capture (DPR-aware output canvas +
  9-arg `drawImage`)
- [x] Fix IIFE-vs-statement bug in `dygraph_strategy()` preprocess/capture JS
- [x] Unify modebar and wizard capture paths via shared
  `MULTI_CANVAS_CAPTURE_JS`
- [x] Add `tests/dash/test_render_js_correctness.py` — Python-side static
  checks (17 assertions, 0.5s)
- [x] **Tried and reverted:** moving the renderer asset into
  `html.Script(_DASH_RENDER_JS)` in the layout. React doesn't execute
  `<script>` tags rendered through its vDOM, so the asset never initialised.
  Reverted to inlining in the per-chart callback body with the IIFE guard.

#### Next up
1. **Drop hidden `dcc.Graph` sink** — replace `Output(hidden_graph_id,
   "figure")` (still present at `src/dygraphs/dash/component.py:178, 202, 253,
   493, 500`) with `Output(store_id, "data", allow_duplicate=True)` +
   `prevent_initial_call='initial_duplicate'`. Bump `dash>=2.9.0` in
   `pyproject.toml`. Delete the hidden Graph component. Removes one ghost
   component from every chart's DOM. ~30 min.
2. **Outputs helper module** — new file `src/dygraphs/dash/outputs.py`
   exporting `data(component_id)` and `opts(component_id)` that produce the
   right `Output` objects. Re-export from `dygraphs.dash`. Update README
   example. ~30 min.
3. **Centralise `processJsMarkers`** — move the recursive `__JS__:` eval walk
   to a single pre-pass at the top of `render()` in `dash_render.js`.
   Currently it's called twice (once on `opts`, once after merging the
   override). Easier to lint and reason about. ~15 min.
4. **Document the always-recreate model in `docs/`** — add an "Updating data
   from Dash callbacks" section to `docs/index.md` explaining: write to
   `Output(f"{cid}-store", "data")`, the chart destroys + recreates on every
   update, set `retain_date_window=True` if you need zoom preserved. Include
   the `outputs` helper from item 2 once it lands.

#### Decisions deferred (revisit when there's a reason)
- **Flask blueprint serving the asset** — would let us replace
  `html.Script(content)` with `<script src="/dygraphs/dash_render.js">`,
  matching R/htmlwidgets exactly. Only worth doing once a page has many
  charts and the duplicated callback bodies become a payload concern.
- **Real React component (`dash-dygraph` package)** — npm/webpack toolchain,
  separate distribution, version-compat matrix. Worth doing if
  dygraphs-for-Dash adoption justifies the build pipeline. Not until then.
- **Collapse `chart-store` + `chart-opts` into one** — keeps the option for
  users to toggle a single setting without retransmitting data. Different
  from R, not strictly worse. Don't touch unless the split causes a concrete
  problem.
- **Selenium capture tests** — DPR/edge-probe browser tests. The static
  checks in `test_render_js_correctness.py` cover the same regressions;
  adding browser tests would be belt-and-suspenders.
- **Group sync stress tests** — multi-chart zoom propagation works in the
  demo. No automated coverage. Add when a regression actually happens.

#### Rationale (Dash architecture)
The R dygraphs package uses htmlwidgets, which provides: a real `.js` asset
loaded once per page via `<script src>`, a single `renderValue(x)` entrypoint
per chart, always-destroy-then-recreate on updates, and stateful closures for
the live dygraph instance. The Dash adapter now matches this model as closely
as Dash's architecture allows: store + clientside callback instead of
htmlwidgets, IIFE-guarded inline instead of manifest-declared `<script src>`,
and DOM-attached `_dygraphInstance` instead of a closure (because the
clientside callback can't capture state across invocations the way an
htmlwidgets factory can). The Shiny adapter (`src/dygraphs/shiny/`) is
intentionally a much thinner shim — Shiny's `htmlwidgets`-style binding
already does most of the work that Dash forces us to reimplement.

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
def series(
    self,
    name: str,
    *,
    color: str | None = None,
    stroke_width: float | None = None,
) -> Dygraph:
    """Configure display options for a named series.

    Mirrors R's ``dySeries()``.

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
| Functions, variables | `snake_case` | `series`, `stroke_width` |
| Classes | `CapitalCase` | `Dygraph`, `DashDygraph` |
| Constants | `UPPER_CASE` | `POINT_SHAPES` |
| Private/internal | `_leading_underscore` | `_normalise_data`, `_format` |

R-port methods specifically: drop the `dy` prefix and snake_case the rest
(`dyOptions` → `options`, `dyRangeSelector` → `range_selector`). See *R ↔
Python API mapping* above.

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
