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

The Dash integration (`src/dygraphs/dash/`) follows the R dygraphs / htmlwidgets model. The goal is **transparency, not magic** — every piece of machinery below is externally documented (in dash-wrap's README or Dash's own docs). Users who want to debug, extend, or audit the component can trace the full chain without surprises.

- **`DygraphChart` class** — the public constructor, `DygraphChart(figure, id=...)`. Inherits from `dash_wrap.ComponentWrapper` with the `dcc.Store` as the inner component. Two siblings live inside the outer `html.Div`:
  - `dcc.Store(id={id})` — carries the serialised config. Its id equals the user-supplied id (the chart's *identity*).
  - `html.Div(id={id}-container)` — the DOM container where dygraphs' JS renders.
  The outer `html.Div` has no id (dash-wrap convention, prevents `DuplicateIdError`). `chart.chart_id` exposes the inner store's id; accessing `chart.id` raises a friendly `AttributeError` pointing at `.chart_id` (while still returning `False` for `hasattr(chart, "id")` so Dash's layout-duplicate walk skips the outer wrapper). Single write channel: every change (data, attrs, styling) flows through `Output(chart, "data")` returning a `dg.to_js()` dict. An earlier two-store design had a second `{id}-opts` sibling for cheap cosmetic updates; removed in favour of R's single-channel model — preserved implementation sketch under "Decisions deferred / opts store" below.
- **`render_core.js`** (shared, framework-agnostic) — the clientside renderer core. Defines `window.dygraphs.render(container, config, options)`. IIFE-guarded, idempotent on repeat inlines. Contains everything that turns a `Dygraph.to_js()` payload into a rendered chart: `processJsMarkers`, `evalExtraJs`, group sync registry, `instantiatePlugins`, `applyPointShapes`, annotation/shading/event overlays, dateWindow ISO→ms normalisation, `Dygraph.Interaction.defaultModel` compat shim, always-destroy+recreate, resize observer. Early-returns on `!config` so `DygraphChart(None, id=...)` is a no-op until real data is pushed. The scaffold-builder option lets frameworks inject their own chart-div wrapper (Dash adds the modebar HTML; Shiny uses the default plain div).
- **`dash_render.js`** (Dash-specific shim) — inlines `render_core.js`, then adds Dash-only concerns: lazy-load `dygraph.css` / `dygraph.min.js` from the CDN, build the modebar-wrapped scaffold, install the PNG capture + reset-zoom button handlers. Dispatches to `window.dygraphs.render(container, config, {scaffoldBuilder})`.
- **Always destroy + recreate** — on every data update, the existing dygraph instance is destroyed and a new one is created from scratch (same as R's `renderValue`). This eliminates the "did I forget to invalidate X" class of bugs from the old in-place `updateOptions` path. Zoom can optionally be preserved via `retain_date_window=True` (default `False`, matching R).
- **Clientside callback** — standard Dash pattern. Dummy output targets the primary store with `allow_duplicate=True`; the JS returns `dash_clientside.no_update`, so the store isn't mutated and there's no feedback loop. Registered once per chart at construction. Requires `dash>=2.9.0`.
- **`MULTI_CANVAS_CAPTURE_JS`** — shared JS constant in `capture.py` for DPR-aware multi-canvas PNG capture. Used by both the modebar camera button and the `dash-capture` wizard strategy (`dygraph_strategy()`).
- **dash-wrap dependency** — provides the `ComponentWrapper` base. Two mechanisms matter: `_set_random_id` returns the inner store's id (so `Output(chart, "data")` resolves), and `__class__` is spoofed so `isinstance(chart, dcc.Store)` is `True`. Everything else is normal Python — the wrapper's a real `html.Div` subclass at the C-type level, which is what Dash uses to serialise the DOM. **`dash-wrap` was extracted to its own PyPI package** (previously vendored in `brand-toolkit/dash-wrap/`); `dygraphs[dash]` declares `dash-wrap>=0.0.1` as a regular dependency.

## Shiny adapter architecture

Parallel to Dash, much thinner. The goal is for Shiny users to feel like they're using standard Shiny — `@render_dygraph` should feel exactly like `@render.plot`, `output_dygraph(id)` like `ui.output_plot(id)`. Rendering delegates to the same `render_core.js` as Dash, so any fix applies to both adapters.

- **`dygraph_ui(element_id, ...)`** — returns a Shiny `TagList` containing the CDN links, the shared `render_core.js` asset (IIFE-guarded; idempotent), the target `<div>`, and a custom-message handler registration keyed by `dygraphs_{element_id}`. The handler is a one-liner: `window.dygraphs.render(el, config)`.
- **`render_dygraph(session, element_id, dg)`** — async server-side function. Serialises `dg` via `.to_js()` (or `None` to clear) and pushes through `session.send_custom_message()`. Planned evolution: add a `@render_dygraph` decorator on top of this, mirroring `@render.plot` — see "Shiny parity plan" below.
- **No `StackedBarChart` / modebar / capture integration yet** — Dash-only, tracked under the parity plan.

## Shiny parity plan (Phases 0–5)

Working toward full Dash-parity for Shiny. Phase 0 is done; Phase 1+ are pending.

**Phase 0 — Shared renderer extraction (DONE).** Everything rendering-related moved from `dash_render.js` into framework-agnostic `render_core.js`; both `dash_render.js` (slim Dash shim) and `shiny/component.py`'s handler now delegate into `window.dygraphs.render`. Eliminates silent drift between adapters: any bug fix applies to both. Shiny users automatically picked up the three recent fixes that were previously Dash-only (dateWindow normalisation, `defaultModel` shim, `evalExtraJs` ordering).

**Phase 1 — Shiny correctness + integration tests (TODO).** Add `tests/shiny/test_render_js_correctness.py` asserting that the Shiny handler goes through `window.dygraphs.render` (i.e. no re-implementation). Add a `shinytest2` / Playwright integration test proving a chart renders and config updates propagate. Confirm `render_dygraph(session, id, None)` clears cleanly.

**Phase 2 — `@render_dygraph` decorator (TODO).** Subclass `shiny.render.renderer.Renderer[Dygraph | None]` so users write:

```python
@render_dygraph
def chart():
    return Dygraph(df)
```

— indistinguishable from `@render.plot`. `None`-return clears the chart. Works with both Shiny Core and Shiny Express. Keep the current `async def render_dygraph(session, id, dg)` as the functional escape hatch. Rename `dygraph_ui` → `output_dygraph` for Plotly-parity naming.

**Phase 3 — feature additions (TODO).** Port `StackedBarChart` to Shiny (same shared-core move: extract the stacked-bar canvas JS into a framework-neutral asset). Port the modebar overlay (hover camera + reset-zoom) into `render_core.js` as an opt-in config, so both adapters get it.

**Phase 4 — docs parity (TODO).** Extend the mental-model diagram in `docs/index.md` to show the Shiny decorator path. Add Shiny recipes, an `examples/shiny_reactive_demo.py` (decorator + reactive input + group sync), promote Shiny in README to a full "Render in Shiny" section.

**Phase 5 — capture (optional).** Mirror `dygraph_strategy()` for the sibling `shinycapture` package.

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
- [x] **Cover the remaining 9 R parity gaps in `test_r_parity.py`.**
  Added five test classes (`TestGroupPlotterFamily` x5,
  `TestDyPluginBare`, `TestDyPlotterCustom`, `TestDyDataHandler`,
  `TestDySeriesData`) bringing explicit R-vs-Python comparison
  coverage from 18 to 27 of 37 methods. Test count 85 → 94. The
  remaining methods are exercised indirectly via wrapper tests
  (e.g. `dyCSS` flows through every chart's serialisation; the
  `dy*Series` family is covered by the per-series plotter tests).
- [x] **Fix `shadow()` / `filled_line()` plotter name collision.**
  Python's `assets/plotters/fillplotter.js` and
  `assets/plotters/filledline.js` both declared
  `function filledlineplotter(e)`. When a chart used both methods,
  whichever JS file was injected last won the global namespace and
  silently changed the other method's behaviour. R doesn't have this
  bug because it inlines the plotter source directly into each
  series's `plotter` field. Renamed the function in `fillplotter.js`
  to `fillplotter` (matching the filename), updated `.shadow()` to
  reference the new name, and added two regression tests in
  `test_plotters.py` (`test_shadow_and_filled_line_use_distinct_plotters`,
  `test_shadow_and_filled_line_inject_both_functions`).

#### Next up
*(no items pending — the Primary track is now complete and the
audit-flagged gaps are closed)*

#### Known structural divergences (not bugs, just things to remember)
- **Plotter storage.** R stores the plotter NAME string in `x$plotter`
  (e.g. `"BarChart"`); Python stores a `JS("Dygraph.Plotters.X")`
  namespace lookup so the JS resolves it at render time. Both reach the
  same runtime function, but the JSON shapes differ. The R parity
  comparisons in `TestPlotterFamily` and `TestSeriesPlotterFamily` are
  intentionally structural ("plotter is set"), not byte-for-byte.
- **Data-handler storage** mirrors the plotter divergence: R's
  `dyDataHandler(name, path)` stores the handler NAME string in
  `dg$x$dataHandler`; Python's `.data_handler(js)` stores the JS
  source as a `JS()` object on `attrs.dataHandler`. Both reach the
  same runtime function via different mechanisms. `TestDyDataHandler`
  is structural for the same reason.
- **`dySeriesData` aux-column storage.** R stores the auxiliary column
  under the R-only `attr(dg$x, "data")` attribute (keyed by name) and
  does **not** push the label into `dg$x$attrs$labels`. Python pushes
  the new name to `attrs.labels` and the values to `data` because
  there's no Python equivalent of R attributes. `TestDySeriesData`
  reads each side via its own aux-data accessor and asserts the
  shared invariant: the new column name is reachable. If we ever want
  per-byte parity here, the Python side would need a separate
  aux-data store and the labels list would have to stay clean — a
  larger refactor than the current shape warrants.

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
- [x] **Disambiguate `.group()` vs `group=`.** Both `Dygraph` features
  are real R ports (`dyGroup` and `dygraph(group=)`) and the names
  can't be changed without breaking parity. Added prominent warning
  blocks to the constructor's `group` parameter description and to
  the `.group()` method's docstring, plus a new `.sync_group(name)`
  builder alias that exposes the constructor kwarg's behaviour
  through autocomplete (Python-only convenience, no R analogue).

#### Next up
*(no items pending — all UX polish items shipped)*

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

#### Done (recent, continued)
- [x] **Drop hidden `dcc.Graph` sink** — replaced with `Output(store_id,
  "data", allow_duplicate=True)` + `prevent_initial_call='initial_duplicate'`.
- [x] **Outputs helper module** — `src/dygraphs/dash/outputs.py` was created,
  then simplified away: the data store now shares the chart's `id` directly,
  so `Output("my-chart", "data")` works without helpers. `data()` and `opts()`
  helpers removed.
- [x] **Document the always-recreate model in `docs/`** — "Updating data from
  Dash callbacks" section added to `docs/index.md`.
- [x] **`DyGraph` component wrapper** — `DyGraph(figure=dg, id="chart")`
  provides `dcc.Graph`-style construction. The data store gets the user-facing
  `id` so `Output("chart", "data")` targets it directly — no helpers needed.
  Wrapper div gets `{id}-wrap`, opts store gets `{id}-opts`. *(Superseded by
  the dash-wrap rebuild below; `DyGraph` was renamed to `DygraphChart` and
  the hand-rolled proxy replaced with `ComponentWrapper` inheritance.)*
- [x] **Rename `DyGraph` → `DygraphChart` + rebuild on `dash-wrap`.**
  The class now inherits from `dash_wrap.ComponentWrapper` with the
  primary `dcc.Store` as the inner component. `Output(chart, "data")`
  resolves to the store via dash-wrap's `_set_random_id` override;
  `isinstance(chart, dcc.Store)` is `True` via the `__class__`
  property. Opts store accessed via `chart.opts` (property returning
  the sibling `dcc.Store`) or by string id `f"{chart.chart_id}-opts"`. The
  outer div has no id (dash-wrap convention; prevents
  `DuplicateIdError`). `register_proxy_defaults(
  dcc.Store, ("data",))` is called once at module import so third
  parties can also `wrap(dcc.Store(...))` cleanly. Naming decision:
  stayed with `DygraphChart` (not `Graph`) because the `dcc.Graph`
  analogy cracks at the callback boundary — users write
  `Output(chart, "data")`, not `"figure"`. Better to name the thing
  for what it is. No backwards-compat alias kept; hard cut. Also:
  `.chart_id` property (not `.id`) exposes the inner store's id — Dash's
  layout validation walks `.id` to detect duplicates, and proxying
  `id` would trip it against the inner store. Users write
  `f"{chart.chart_id}-opts"` or just use `chart.opts`.
- [x] **`figure=None` empty placeholder.** `DygraphChart(None,
  id="my-chart")` produces a valid layout with the store holding
  `data=None`; the clientside renderer has an existing
  `if (!config) return;` guard, so the chart is a no-op until a
  callback pushes real data. Use case: build an app where the first
  config arrives via callback.
- [x] **Centralise `processJsMarkers`.** Called exactly once per
  render on the parsed `opts` dict in `render()`. One easy-to-audit
  eval site. Pinned by
  `test_render_js_correctness.py::TestJsMarkerSinglePass`.
- [x] **Dropped the opts-override store.** Earlier designs had a
  second sibling `dcc.Store(id=f"{id}-opts")` alongside the primary
  store; users could `Output(chart.opts, "data")` with a dict like
  `{"strokeWidth": 3}` that was `Object.assign`'d on top of the base
  config's `attrs` on render — a cheap-cosmetic-updates channel. Removed
  for 1.0 in favour of R's single-write-surface model: every change
  (data, attrs, styling) flows through the primary store. The design
  is preserved in "Decisions deferred / opts store" below in case the
  destroy+recreate cost becomes a real pain point for someone.
- [x] **Migrated all examples/docs from `@app.callback` to `@dash.callback`.**
  Uses `import dash` + `dash.callback(...)` / `dash.Dash(...)` style
  consistently (no explicit imports of `callback` or `Dash`).
- [x] **Dropped `.to_dash()`, `.to_shiny()`, and `dygraph_to_dash()`.**
  `Dygraph` is now strictly framework-agnostic — same convention as
  `plotly.graph_objects.Figure` and R's htmlwidget (R doesn't have
  `dg %>% toShiny()`; it uses `dygraphOutput(id)` + `renderDygraph({...})`
  as separate functions). Single Dash entry point is
  `DygraphChart(figure=dg, id=...)`; Shiny stays on `dygraph_ui(id)` +
  `render_dygraph(session, id, dg)`. `.to_html()` remains because it's a
  self-contained render, not a framework wrapper — analogous to R's
  htmlwidget auto-print / `plotly.Figure.to_html`.
- [x] **Added `Dygraph.to_js()`.** JSON-safe sibling of `to_dict()`:
  substitutes embedded `JS(code)` objects with `"__JS__:code:__JS__"`
  string markers that Dash's prop validator accepts and the clientside
  `processJsMarkers` re-evaluates at render time. Made Dash callback
  returns a one-liner — `return Dygraph(df).to_js()` — no user-side
  `serialise_js()` import. `to_dict()` still exposes the raw config
  for introspection / `to_html()` (which inlines JS directly into a
  `<script>` block). The `to_dict` docstring points at `to_js` so
  users who hit `InvalidCallbackReturnValue` get the fix immediately.
- [x] **Dropped public `to_json()` → private `_to_json()`.** Only used
  internally by `to_html()`; external users never had a reason to
  reach for it (they want `to_dict` / `to_js` / `to_html`). Removed
  from the public surface; renamed to `_to_json` to signal that.
- [x] **Renamed `chart.cid` → `chart.chart_id` + friendly `.id` error.**
  Users coming from `dcc.Graph` habitually reach for `chart.id`, but
  the wrapper has no `.id` attribute (on purpose — Dash's duplicate-
  id walk would trip against the inner store). Now `.id` raises an
  `AttributeError` whose message points at `.chart_id`, while
  `hasattr(chart, "id")` still returns `False` so Dash's layout
  validation keeps working. Renamed the accessor from the terse
  `.cid` to the more self-documenting `.chart_id`.
- [x] **`StackedBarChart` class** (was `stacked_bar()` function).
  Parallels `DygraphChart` shape: `StackedBarChart(id=None, *,
  initial_data=..., colors=..., height=..., title=..., group=...)`.
  Same `.chart_id` accessor, same friendly `.id` error, same
  `dash-wrap`-based identity proxying. Canvas-drawing JS lives in
  `_build_stacked_bar_js` helper alongside `DygraphChart`. Different
  renderer from `DygraphChart` (not backed by dygraphs.js); uses its
  own small canvas-drawing routine.
- [x] **`Dygraph.error_bar_data` / `Dygraph.custom_bar_data` classmethods.**
  Moved from top-level `dygraphs.make_error_bar_data` / `make_custom_bar_data`
  to classmethods on `Dygraph`. Better discoverability via
  autocomplete and reduces top-level namespace noise. Top-level
  functions removed.
- [x] **Dropped top-level lazy re-exports** from `dygraphs/__init__.py`.
  `stacked_bar`, `dygraph_strategy`, `DygraphChart`, etc. were lazily
  re-exported from `dygraphs.*` via `*args, **kwargs` wrapper
  functions. Removed because `*args, **kwargs` kills Pylance hints —
  users should `from dygraphs.dash import DygraphChart` directly so
  the IDE sees the real signature. Slim and honest over "everything
  in one namespace."
- [x] **Fixed three clientside-renderer bugs** surfaced by an internal
  MR author's hand-patches:
  1. **`opts.dateWindow` ISO-string → ms normalisation.** Python
     serialises date bounds as `"2024-01-10T00:00:00.000Z"`; dygraphs
     JS expects `[number_ms, number_ms]`. Previously strings slipped
     through → silent NaN → initial window ignored. Fixed in
     `render_core.js` by mapping string entries via
     `new Date(v).getTime()`.
  2. **`Dygraph.Interaction.defaultModel` compat shim.** Some dygraphs
     builds only expose `Dygraph.defaultInteractionModel`, leaving
     `Dygraph.Interaction.defaultModel` undefined. Our
     `range_selector(keep_mouse_zoom=True)` emits a `JS` marker
     referencing the latter path, which silently eval'd to `undefined`
     → broken interaction model. The shim populates the namespace
     from the top-level default when missing.
  3. **`evalExtraJs` must run before `processJsMarkers`.**
     `.bar_chart()` etc. emit `plotter: JS("Dygraph.Plotters.BarChart")`
     AND an `extraJs` entry that defines that namespace via an IIFE.
     Evaluating the marker first returned `undefined` →
     silent fall-back to the default line plotter. Reordered so
     extraJs is evaluated first and the markers resolve against the
     populated namespace. Pinned by
     `TestExtraJsEvalOrder::test_evaljs_runs_before_processjsmarkers`
     plus per-plotter file assertions.
- [x] **Fixed timezone-incorrect date serialisation.** Annotations,
  shadings, events, and `range_selector(date_window=...)` all
  emitted `strftime("%Y-%m-%dT%H:%M:%S.000Z")` — but the `Z` suffix
  claims UTC, and for tz-aware non-UTC timestamps the `strftime`
  output is the *local wall-clock time* with a lying `Z` → value
  shifted by the local offset (e.g. 1–2h off for Europe/Zurich).
  Added `dygraphs.utils.ts_to_utc_iso()` helper that `tz_convert` /
  `tz_localize` to UTC first. All four callsites replaced; twelve
  tz-correctness tests pinned in `tests/dygraphs/test_timezone.py`.
- [x] **Fixed four integration test failures across plotter parity
  and stacked-bar rendering:**
  - `test_js_asset_parity.py::fillplotter.js` — the R upstream and
    Python disagree on the inner function name (`filledlineplotter`
    vs `fillplotter`); the Python rename is an intentional
    bug fix (see "Done" note above) so added an
    `_INTENTIONAL_DIVERGENCES` allowlist and `pytest.skip`.
  - `test_r_parity.py::TestPlotterFamily` (5 tests) — read from
    `dg$x$attrs$plotter` but R actually stores the plotter name
    at `dg$x$plotter` (top level). Fixed the R path in all five
    tests.
  - `test_r_parity.py::TestStrictJsonDiff` (3 tests) — the
    `_STRICT_SKIP_TOP` loop only popped `scale` from the R side; now
    that Python also emits `scale` (after the `periodicity=`
    addition), it needed popping from both. One-line fix.
  - `test_sync_and_bar.py` (3 tests) — `stacked_bar()` had a JS
    scoping bug: the group-registration block referenced
    `container` before it was declared (local to `render()`),
    throwing a `ReferenceError` whenever `group=` was passed and
    killing the callback silently. Hoisted the container lookup.
- [x] **Extracted shared renderer (`render_core.js`).** Both
  `dash_render.js` and the Shiny handler used to re-implement
  ~250 lines of rendering logic independently; three recent bug
  fixes had already diverged across them. Moved the framework-
  agnostic core (marker resolution, group sync, plugin
  instantiation, point shapes, annotation/shading/event
  overlays, dateWindow normalisation, interactionModel shim,
  destroy+recreate, resize observer) to
  `src/dygraphs/assets/render_core.js` exposing
  `window.dygraphs.render(container, config, options)`. The scaffold
  builder is a caller-provided callback, letting Dash inject its
  modebar HTML while Shiny uses a plain chart `<div>`. Kills the
  drift permanently — any future fix applies to both adapters.
- [x] **Expanded `Dygraph` class docstring per the project STYLEGUIDE.**
  Added full NumPy-convention coverage with every declarative
  parameter documented (`axes`, `series`, `options`, `legend`,
  `highlight`, `annotations`, `shadings`, `events`, `limits`,
  `range_selector`, `roller`, `callbacks`, `plotter`) — was
  previously uncovered. Examples cover builder + declarative +
  dict-mixed + CSV + group sync + three serialisation targets.
  `See Also` cross-refs every major builder method and the three
  framework adapters.
- [x] **Added mental-model diagram and recipes** to `docs/index.md` —
  ASCII sketch of the one-builder / four-rendering-paths split
  (Dash / Shiny / HTML / dict-JSON), plus eight "how do I…"
  recipes (notebook display, Dash render, callback update, empty
  placeholder, chart id access, error bars, group sync, standalone
  HTML export).

#### Next up

*(no items pending — the Dash adapter backlog is now closed; Shiny
parity work tracked under "Shiny parity plan" above)*

#### Decisions deferred (revisit when there's a reason)
- **Flask blueprint serving the asset** — would let us replace
  `html.Script(content)` with `<script src="/dygraphs/dash_render.js">`,
  matching R/htmlwidgets exactly. Only worth doing once a page has many
  charts and the duplicated callback bodies become a payload concern.
- **Real React component (`dash-dygraph` package)** — npm/webpack toolchain,
  separate distribution, version-compat matrix. Would unlock
  `Output("chart", "figure")` and interaction props (`hoverData`,
  `zoomData`, `clickData`). Worth doing if dygraphs-for-Dash adoption
  justifies the build pipeline. Not until then.
- **Selenium capture tests** — DPR/edge-probe browser tests. The static
  checks in `test_render_js_correctness.py` cover the same regressions;
  adding browser tests would be belt-and-suspenders.
- **Group sync stress tests** — multi-chart zoom propagation works in the
  demo. No automated coverage. Add when a regression actually happens.
- **Opts-override store** — preserved for possible future reintroduction.
  Purpose: a cheap cosmetic-update channel that merges a dict of
  option overrides on top of the current config without a full
  destroy+recreate. Removed for 1.0 (R has no equivalent, and the
  two-channel "which store do I write to" distinction added more
  cognitive load than it bought for typical chart sizes). Re-add if
  real users hit perf walls on large datasets with frequent stroke
  / color tweaks driven by sliders etc. Implementation sketch —
  everything that needs to come back:

  1. **Extra sibling in `DygraphChart.__init__`.** Alongside the
     primary `dcc.Store(id=cid, ...)` and `html.Div(id=f"{cid}-container")`,
     add `opts_store = dcc.Store(id=f"{cid}-opts", data=None)` and
     include it in `children=[...]`. Store a reference on the wrapper
     for the `chart.opts` property (`object.__setattr__` or the
     normal path — dash-wrap's `__setattr__` routes non-proxy names
     through `super()`).

  2. **`chart.opts` property** on `DygraphChart` returning the
     sibling `dcc.Store`. Users write `Output(chart.opts, "data")`
     in callbacks, or the equivalent `Output(f"{chart.chart_id}-opts",
     "data")` string-id form. Not proxied (no need for identity
     aliasing; it's a separate Dash component with its own id).

  3. **Second `Input` on the per-chart clientside callback.** Add
     `Input(opts_store.id, "data")` alongside the existing
     `Input(cid, "data")`. Both stores drive the same dummy-output
     callback so the renderer fires when either changes.

  4. **Pass `optsOverride` through the shim.** `_build_render_js`'s
     wrapper becomes `function(config, optsOverride) { ...;
     window.dygraphsDash.render({setup_json}, config, optsOverride);
     ... }`.

  5. **Merge in `dash_render.js`.** After the `var opts = JSON.parse(
     JSON.stringify(config.attrs));` line, add
     `if (optsOverride && typeof optsOverride === 'object') {
     Object.assign(opts, optsOverride); }` BEFORE the
     `processJsMarkers(opts)` call (so override markers also get
     evaluated). Update the renderer's top docstring to mention the
     third parameter; restore the `TestJsMarkerSinglePass::
     test_processjsmarkers_call_follows_object_assign` assertion.

  6. **Docs surface.** Re-add the "two write channels" table to
     `docs/index.md` with the `Output(chart.opts, "data")` example
     — emphasise when it's worth the extra mental load (large
     datasets + slider-driven tweaks) vs. when the single-channel
     primary-store write is fine.

  Total change: ~25 lines of Python + ~5 lines of JS + a doc block.
  The design is straightforward; the reason it's out is simplicity
  of the 1.0 public surface, not implementation difficulty.

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
