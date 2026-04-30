# Changelog

All notable changes to **dygraphs** are documented here.

The format is loosely based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(pre-1.0: minor and patch bumps may both contain new features).

## Unreleased

### Added

- **New `DyModebarButton` class** in `dygraphs.dash` — injects a
  custom button into the chart's modebar overlay and exposes the
  bridge protocol expected by `dash_capture.capture_element(trigger=...)`.
  This gives the dygraphs modebar the same one-line UX that
  `dash_capture.ModebarButton` gives the plotly modebar: pass the
  button as `trigger=`, drop the returned wizard component into your
  layout, and the bridge is folded in automatically — no hidden
  `html.Button` in user code.
- **New `DYGRAPH_HIDE_SELECTORS` constant** — the CSS selectors hidden
  during capture (range-selector chrome). Single source of truth for
  both `dygraph_strategy` and the modebar's camera-icon download.

### Changed

- **`dygraph_strategy()` is now a thin wrapper** around
  `dash_capture.multi_canvas_strategy(...)`. The canvas-walking JS
  (`MULTI_CANVAS_CAPTURE_JS`), the html2canvas overlay, and the
  live-resize preprocess (`build_reflow_preprocess`) all live in
  dash-capture so other chart libraries can reuse them. `dygraphs`
  keeps the dygraphs-specific knowledge (which selectors to hide).
  Public behaviour and parameters are unchanged.
- `dygraphs.dash.capture.MULTI_CANVAS_CAPTURE_JS` is now a re-export
  of `dash_capture.MULTI_CANVAS_CAPTURE_JS`. Existing imports keep
  working (`from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS`).

### Breaking

- **JS contract change** for direct invokers of
  `MULTI_CANVAS_CAPTURE_JS`. The third positional argument went from
  `hideRangeSelector: boolean` to `hideSelectors: string[]`. Anyone
  calling the IIFE directly (outside `dygraph_strategy()`) needs to
  pass an array of CSS selectors instead of a boolean. The shipped
  modebar download path (in `dash_render.js`) was already updated to
  pass the new array. Most users will be unaffected — they go through
  `dygraph_strategy()` which builds the call site for them.

### Dependencies

- The `[dash]` extra now requires `dash-capture>=0.0.11` to
  pick up the `multi_canvas_strategy` / `MULTI_CANVAS_CAPTURE_JS` /
  `build_reflow_preprocess` APIs.

### Tests

- Added `TestDyModebarButton` (5 tests) covering: construction +
  attribute shape, the default download-glyph icon, custom icon
  passthrough, the bridge-protocol attributes (`bridge`, `open_input`),
  and an end-to-end check that `capture_element(trigger=DyModebarButton(...))`
  folds the bridge into the returned wizard component tree.
