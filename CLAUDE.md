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

- `src/dygraphs/assets/` contains the dygraphs JavaScript library and plugins
- `dygraphs-js/` and `dygraphs-r/` are reference copies of the upstream JS library and R package (not part of the Python package)
- `PyDyGraphs/` is legacy code from an earlier implementation (untracked, not part of this package)

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
