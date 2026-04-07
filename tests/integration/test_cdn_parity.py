"""CDN vs bundled parity tests.

Verifies that the compatibility shim makes CDN builds expose the same
namespaces as the bundled version (Dygraph.Interaction, Dygraph.Plotters).
Also checks that both CDN and inline modes render all chart types.

Requires Chrome + chromedriver. Skipped if unavailable.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from dygraphs import Dygraph

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2020-01-01", periods=10, freq="D")
_DF = pd.DataFrame({"a": range(1, 11), "b": range(10, 0, -1)}, index=_DATES)


@pytest.fixture(scope="module")
def driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        pytest.skip("selenium not installed")
        return

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    try:
        d = webdriver.Chrome(options=options)
    except Exception:
        options.binary_location = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        try:
            d = webdriver.Chrome(options=options)
        except Exception as exc:
            pytest.skip(f"Chrome/chromedriver not available: {exc}")
            return

    yield d
    d.quit()


def _open(driver: Any, dg: Dygraph, *, cdn: bool) -> None:
    html = dg.to_html(cdn=cdn)
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        f.write(html)
        path = f.name
    driver.get(f"file://{path}")
    time.sleep(3)
    Path(path).unlink(missing_ok=True)


def _no_errors(driver: Any) -> None:
    logs = driver.get_log("browser")
    errors = [
        e["message"]
        for e in logs
        if e["level"] == "SEVERE" and "favicon" not in e["message"].lower()
    ]
    assert not errors, f"JS errors: {errors}"


def _has_canvas(driver: Any) -> None:
    count = driver.execute_script("return document.querySelectorAll('canvas').length")
    assert count > 0, "No canvas — chart did not render"


# ---------------------------------------------------------------------------
# Namespace parity
# ---------------------------------------------------------------------------


class TestNamespaceParity:
    """Both CDN+shim and inline should expose the same critical namespaces."""

    def test_cdn_has_interaction(self, driver) -> None:
        _open(driver, Dygraph(_DF), cdn=True)
        _no_errors(driver)
        has_interaction = driver.execute_script(
            "return typeof Dygraph.Interaction === 'object'"
        )
        assert has_interaction, "Dygraph.Interaction not available with CDN+shim"

    def test_cdn_has_default_model(self, driver) -> None:
        _open(driver, Dygraph(_DF), cdn=True)
        _no_errors(driver)
        has_model = driver.execute_script(
            "return typeof Dygraph.Interaction.defaultModel === 'object'"
        )
        assert has_model, "Dygraph.Interaction.defaultModel not available"

    def test_cdn_has_non_interactive_model(self, driver) -> None:
        _open(driver, Dygraph(_DF), cdn=True)
        _no_errors(driver)
        has_model = driver.execute_script(
            "return typeof Dygraph.Interaction.nonInteractiveModel_ === 'object'"
        )
        assert has_model, "Dygraph.Interaction.nonInteractiveModel_ not available"

    def test_cdn_has_plotters(self, driver) -> None:
        _open(driver, Dygraph(_DF), cdn=True)
        _no_errors(driver)
        has_plotters = driver.execute_script(
            "return typeof Dygraph.Plotters === 'object'"
        )
        assert has_plotters, "Dygraph.Plotters not available with CDN+shim"

    def test_inline_has_interaction(self, driver) -> None:
        _open(driver, Dygraph(_DF), cdn=False)
        _no_errors(driver)
        has_interaction = driver.execute_script(
            "return typeof Dygraph.Interaction === 'object'"
        )
        assert has_interaction, "Dygraph.Interaction not available inline"


# ---------------------------------------------------------------------------
# Render parity: same charts should work on both CDN and inline
# ---------------------------------------------------------------------------


class TestRenderParity:
    """Charts that need Dygraph.Interaction should render on both CDN and inline."""

    def test_disable_zoom_cdn(self, driver) -> None:
        _open(driver, Dygraph(_DF).options(disable_zoom=True), cdn=True)
        _no_errors(driver)
        _has_canvas(driver)

    def test_disable_zoom_inline(self, driver) -> None:
        _open(driver, Dygraph(_DF).options(disable_zoom=True), cdn=False)
        _no_errors(driver)
        _has_canvas(driver)

    def test_range_selector_cdn(self, driver) -> None:
        _open(driver, Dygraph(_DF).range_selector(), cdn=True)
        _no_errors(driver)
        _has_canvas(driver)

    def test_range_selector_inline(self, driver) -> None:
        _open(driver, Dygraph(_DF).range_selector(), cdn=False)
        _no_errors(driver)
        _has_canvas(driver)

    def test_simple_chart_cdn(self, driver) -> None:
        _open(driver, Dygraph(_DF), cdn=True)
        _no_errors(driver)
        _has_canvas(driver)

    def test_simple_chart_inline(self, driver) -> None:
        _open(driver, Dygraph(_DF), cdn=False)
        _no_errors(driver)
        _has_canvas(driver)
