"""JS syntax validation tests — catch serialization bugs without a browser.

Uses Node.js ``--check`` to validate that the generated HTML/JS is
syntactically valid.  Catches issues like:
- Multiline JS not unwrapped (``\\n`` literals instead of newlines)
- ``function`` declarations in expression position
- Broken JSON string escaping in ``unwrap_js_markers``

These run on CI without Selenium/Chrome.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from dygraphs import Dygraph
from dygraphs.utils import unwrap_js_markers

# ---------------------------------------------------------------------------
# Skip if Node.js unavailable
# ---------------------------------------------------------------------------

_HAS_NODE = False
try:
    subprocess.run(["node", "--version"], capture_output=True, check=True)
    _HAS_NODE = True
except (FileNotFoundError, subprocess.CalledProcessError):
    pass

pytestmark = pytest.mark.skipif(not _HAS_NODE, reason="Node.js not available")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2020-01-01", periods=10, freq="D")
_DF = pd.DataFrame({"a": range(1, 11), "b": range(10, 0, -1)}, index=_DATES)


def _validate_js_syntax(html: str) -> None:
    """Extract the main <script> block and validate with Node.js --check."""
    # Find the last <script>...</script> block (the main config/render block)
    scripts = list(re.finditer(r"<script>(.*?)</script>", html, re.DOTALL))
    assert scripts, "No <script> blocks found in HTML"
    main_script = scripts[-1].group(1)

    # Write to temp file and validate
    with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
        f.write(main_script)
        path = f.name

    try:
        result = subprocess.run(
            ["node", "--check", path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Show the error with context
            stderr = result.stderr.strip()
            pytest.fail(f"JS syntax error:\n{stderr}\n\nScript:\n{main_script[:500]}")
    finally:
        Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 1. Round-trip marker tests
# ---------------------------------------------------------------------------


class TestUnwrapJsMarkers:
    def test_single_line_function(self) -> None:
        raw = json.dumps({"cb": "__JS__:function(){return 1;}:__JS__"})
        result = unwrap_js_markers(raw)
        assert '"__JS__' not in result
        assert "(function(){return 1;})" in result

    def test_multiline_function(self) -> None:
        code = "function foo(e) {\n  var x = 1;\n  return x;\n}"
        raw = json.dumps({"plotter": f"__JS__:{code}:__JS__"})
        result = unwrap_js_markers(raw)
        # Should contain actual newlines, not \\n
        assert "\\n" not in result
        assert "\n" in result
        assert "(function foo(e)" in result

    def test_named_reference(self) -> None:
        raw = json.dumps({"plotter": "__JS__:Dygraph.Plotters.BarChart:__JS__"})
        result = unwrap_js_markers(raw)
        assert result == '{"plotter": Dygraph.Plotters.BarChart}'

    def test_escaped_quotes_in_js(self) -> None:
        code = 'function() { return "hello"; }'
        raw = json.dumps({"cb": f"__JS__:{code}:__JS__"})
        result = unwrap_js_markers(raw)
        assert '"hello"' in result

    def test_backslash_in_js(self) -> None:
        code = "function() { return '\\\\n'; }"
        raw = json.dumps({"cb": f"__JS__:{code}:__JS__"})
        result = unwrap_js_markers(raw)
        assert "\\n" in result  # literal backslash-n in JS string


# ---------------------------------------------------------------------------
# 2. JS syntax validation per chart type
# ---------------------------------------------------------------------------


class TestJsSyntaxBasic:
    def test_simple_chart(self) -> None:
        _validate_js_syntax(Dygraph(_DF).to_html(cdn=False))

    def test_with_options(self) -> None:
        html = Dygraph(_DF).options(fill_graph=True, stroke_width=2).to_html(cdn=False)
        _validate_js_syntax(html)


class TestJsSyntaxPlotters:
    def test_stem_plot_inline(self) -> None:
        _validate_js_syntax(Dygraph(_DF).options(stem_plot=True).to_html(cdn=False))

    def test_series_stem_plot(self) -> None:
        _validate_js_syntax(Dygraph(_DF).series("a", stem_plot=True).to_html(cdn=False))

    def test_custom_plotter_anonymous(self) -> None:
        js = "function(e) { var ctx = e.drawingContext; }"
        _validate_js_syntax(Dygraph(_DF).custom_plotter(js).to_html(cdn=False))

    def test_custom_plotter_named(self) -> None:
        js = "function myPlotter(e) { var ctx = e.drawingContext; }"
        _validate_js_syntax(Dygraph(_DF).custom_plotter(js).to_html(cdn=False))

    def test_bar_chart(self) -> None:
        _validate_js_syntax(Dygraph(_DF).bar_chart().to_html(cdn=False))

    def test_stacked_bar_chart(self) -> None:
        _validate_js_syntax(Dygraph(_DF).stacked_bar_chart().to_html(cdn=False))

    def test_multi_column(self) -> None:
        _validate_js_syntax(Dygraph(_DF).multi_column().to_html(cdn=False))

    def test_candlestick(self) -> None:
        ohlc = pd.DataFrame(
            {"O": [10, 11], "H": [12, 13], "L": [9, 10], "C": [11, 12]},
            index=_DATES[:2],
        )
        _validate_js_syntax(Dygraph(ohlc).candlestick().to_html(cdn=False))

    def test_bar_series(self) -> None:
        _validate_js_syntax(Dygraph(_DF).bar_series("a").to_html(cdn=False))

    def test_stem_series(self) -> None:
        _validate_js_syntax(Dygraph(_DF).stem_series("a").to_html(cdn=False))

    def test_shadow(self) -> None:
        _validate_js_syntax(Dygraph(_DF).shadow("a").to_html(cdn=False))

    def test_filled_line(self) -> None:
        _validate_js_syntax(Dygraph(_DF).filled_line("a").to_html(cdn=False))

    def test_error_fill(self) -> None:
        _validate_js_syntax(Dygraph(_DF).error_fill("a").to_html(cdn=False))


class TestJsSyntaxPlugins:
    def test_unzoom(self) -> None:
        _validate_js_syntax(Dygraph(_DF).unzoom().to_html(cdn=False))

    def test_crosshair(self) -> None:
        _validate_js_syntax(Dygraph(_DF).crosshair().to_html(cdn=False))

    def test_rebase(self) -> None:
        _validate_js_syntax(Dygraph(_DF).rebase().to_html(cdn=False))

    def test_ribbon(self) -> None:
        _validate_js_syntax(
            Dygraph(_DF)
            .ribbon(data=[0, 1] * 5, palette=["red", "green"])
            .to_html(cdn=False)
        )


class TestJsSyntaxCallbacks:
    def test_all_callbacks(self) -> None:
        dg = Dygraph(_DF).callbacks(
            click="function(e, x, pts) { console.log(x); }",
            zoom="function(min, max) { console.log(min, max); }",
            draw="function(g, initial) {}",
        )
        _validate_js_syntax(dg.to_html(cdn=False))


class TestJsSyntaxOverlays:
    def test_annotations_events_shadings(self) -> None:
        dg = (
            Dygraph(_DF)
            .annotation("2020-01-05", "A", series="a")
            .event("2020-01-03", "E")
            .shading("2020-01-02", "2020-01-04")
            .limit(5, "L")
        )
        _validate_js_syntax(dg.to_html(cdn=False))


class TestJsSyntaxInteraction:
    def test_disable_zoom(self) -> None:
        _validate_js_syntax(Dygraph(_DF).options(disable_zoom=True).to_html(cdn=False))

    def test_range_selector_with_date_window(self) -> None:
        _validate_js_syntax(
            Dygraph(_DF)
            .range_selector(date_window=("2020-01-03", "2020-01-08"))
            .to_html(cdn=False)
        )
