"""Verify bundled JS assets (plotters + plugins) match the R reference.

Compares files from dygraphs-r/inst/ against src/dygraphs/assets/.
Differences are whitespace-normalised before comparison — only functional
changes are flagged.

Skipped if the R reference directory is not available.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _find_r_inst() -> Path | None:
    """Find R dygraphs inst/ directory, checking worktrees if needed."""
    base = Path(__file__).resolve().parents[2]
    candidates = [base / "dygraphs-r" / "inst"]
    try:
        wt = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=base,
        )
        candidates.extend(
            Path(line[9:]) / "dygraphs-r" / "inst"
            for line in wt.stdout.splitlines()
            if line.startswith("worktree ")
        )
    except Exception:
        pass
    for c in candidates:
        if c.is_dir():
            return c
    return None


_R_BASE = Path(__file__).resolve().parents[2]
_R_INST = _find_r_inst()

_PY_ASSETS = _R_BASE / "src" / "dygraphs" / "assets"

# Plotter/plugin files whose content intentionally diverges from R.
# See CLAUDE.md "Done (recent)" entry "Fix shadow() / filled_line() plotter
# name collision": Python renamed the inner function in fillplotter.js from
# ``filledlineplotter`` to ``fillplotter`` to avoid global-symbol collision
# with filledline.js when both are injected into the same page. R doesn't
# have this bug because it inlines plotter source into each series.
_INTENTIONAL_DIVERGENCES: set[str] = {"fillplotter.js"}

pytestmark = pytest.mark.skipif(
    _R_INST is None, reason="R dygraphs reference (dygraphs-r/inst/) not found"
)


def _normalise_ws(text: str) -> str:
    """Strip trailing whitespace per line, collapse blank lines, strip trailing newline."""
    lines = [line.rstrip() for line in text.splitlines()]
    # Collapse multiple blank lines into one
    result: list[str] = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                result.append("")
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return "\n".join(result).strip()


def _get_pairs(subdir: str) -> list[tuple[str, Path, Path]]:
    """Return (name, r_path, py_path) for files in both R and Python."""
    if _R_INST is None:
        return []
    r_dir = _R_INST / subdir
    py_dir = _PY_ASSETS / subdir
    if not r_dir.is_dir() or not py_dir.is_dir():
        return []
    pairs = []
    for r_file in sorted(r_dir.glob("*.js")):
        py_file = py_dir / r_file.name
        if py_file.exists():
            pairs.append((r_file.name, r_file, py_file))
    return pairs


class TestPlotterParity:
    """All plotter JS files should be functionally identical to R."""

    @pytest.mark.parametrize(
        "name,r_path,py_path",
        _get_pairs("plotters"),
        ids=[p[0] for p in _get_pairs("plotters")],
    )
    def test_plotter_matches(self, name: str, r_path: Path, py_path: Path) -> None:
        if name in _INTENTIONAL_DIVERGENCES:
            pytest.skip(f"{name} intentionally diverges from R (see _INTENTIONAL_DIVERGENCES)")
        r_code = _normalise_ws(r_path.read_text())
        py_code = _normalise_ws(py_path.read_text())
        assert r_code == py_code, (
            f"Plotter {name} differs between R and Python (after whitespace normalisation)"
        )

    def test_no_missing_plotters(self) -> None:
        """Every R plotter should have a Python counterpart."""
        assert _R_INST is not None
        r_dir = _R_INST / "plotters"
        py_dir = _PY_ASSETS / "plotters"
        r_names = {f.name for f in r_dir.glob("*.js")}
        py_names = {f.name for f in py_dir.glob("*.js")}
        missing = r_names - py_names
        assert not missing, f"R plotters missing in Python: {missing}"


class TestPluginParity:
    """All plugin JS files should be functionally identical to R."""

    @pytest.mark.parametrize(
        "name,r_path,py_path",
        _get_pairs("plugins"),
        ids=[p[0] for p in _get_pairs("plugins")],
    )
    def test_plugin_matches(self, name: str, r_path: Path, py_path: Path) -> None:
        r_code = _normalise_ws(r_path.read_text())
        py_code = _normalise_ws(py_path.read_text())
        assert r_code == py_code, (
            f"Plugin {name} differs between R and Python (after whitespace normalisation)"
        )

    def test_no_missing_plugins(self) -> None:
        """Every R plugin should have a Python counterpart."""
        assert _R_INST is not None
        r_dir = _R_INST / "plugins"
        py_dir = _PY_ASSETS / "plugins"
        r_names = {f.name for f in r_dir.glob("*.js")}
        py_names = {f.name for f in py_dir.glob("*.js")}
        missing = r_names - py_names
        assert not missing, f"R plugins missing in Python: {missing}"
