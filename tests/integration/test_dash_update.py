"""Dash update behavior tests.

Spins up a Dash app with a dygraph chart and a button that triggers a
server-side callback writing new data to the chart's data store. Tests
verify the chart re-renders, instance identity, zoom preservation, and
that modebar interactions survive a data update.

These tests pin the *current* behaviour so Phase 2 (always-recreate)
can flip specific assertions and the diff is the change record.

Requires Chrome + chromedriver. Skipped if unavailable.
"""

from __future__ import annotations

import socket
import threading
import time

import numpy as np
import pandas as pd
import pytest


def _make_df(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {"value": rng.standard_normal(60).cumsum().round(2)},
        index=pd.date_range("2024-01-01", periods=60, freq="D"),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dash_app_url():
    """Dash app with a chart and an 'Update Data' button."""
    from dash import Dash, Input, Output, html

    from dygraphs import Dygraph
    from dygraphs.utils import serialise_js

    app = Dash(__name__)

    initial = Dygraph(_make_df(0), title="Update Test").options(
        stroke_width=2, colors=["#00d4aa"]
    )

    component = initial.to_dash(app=app, component_id="upd-chart", height="240px")

    app.layout = html.Div(
        [
            html.Button("Update Data", id="update-btn"),
            component,
        ]
    )

    @app.callback(
        Output("upd-chart-store", "data"),
        Input("update-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_click(n):
        new = Dygraph(_make_df(n or 1), title=f"Update #{n}").options(
            stroke_width=2, colors=["#e74c3c"]
        )
        return serialise_js(new.to_dict())

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False),
        daemon=True,
    ).start()
    time.sleep(3)
    yield f"http://127.0.0.1:{port}"


@pytest.fixture(scope="module")
def chrome_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=900,600")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    try:
        driver = webdriver.Chrome(options=options)
    except Exception:
        options.binary_location = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as exc:
            pytest.skip(f"Chrome/chromedriver not available: {exc}")
            return

    yield driver
    driver.quit()


@pytest.fixture(scope="module")
def loaded_page(dash_app_url, chrome_driver):
    chrome_driver.get(dash_app_url)
    time.sleep(5)
    canvas_count = chrome_driver.execute_script(
        "return document.querySelectorAll('#upd-chart-container canvas').length;"
    )
    assert canvas_count > 0, "chart did not render"
    return chrome_driver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _click_update(driver):
    """Click the Update Data button and wait for the callback to complete."""
    driver.find_element("id", "update-btn").click()
    time.sleep(3)  # server callback + clientside re-render


def _get_instance_id(driver) -> str:
    """Return a unique identifier for the current dygraph JS instance.

    We use the instance's creation timestamp (stringified) to detect
    whether the same object was reused or a new one was created.
    """
    return driver.execute_script(
        "var c = document.getElementById('upd-chart-container');"
        "if (!c || !c._dygraphInstance) return null;"
        "if (!c._dygraphInstance._testId) {"
        "  c._dygraphInstance._testId = Math.random().toString(36);"
        "}"
        "return c._dygraphInstance._testId;"
    )


def _get_title_text(driver) -> str:
    """Read the chart title from the DOM."""
    return driver.execute_script(
        "var t = document.querySelector('#upd-chart-container .dygraph-title');"
        "return t ? t.textContent : '';"
    )


def _has_canvases(driver) -> bool:
    return driver.execute_script(
        "return document.querySelectorAll('#upd-chart-container canvas').length > 0;"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInitialRender:
    def test_chart_has_canvases(self, loaded_page) -> None:
        assert _has_canvases(loaded_page)

    def test_chart_has_title(self, loaded_page) -> None:
        assert "Update Test" in _get_title_text(loaded_page)

    def test_no_severe_js_errors(self, loaded_page) -> None:
        logs = loaded_page.get_log("browser")
        errors = [e for e in logs if e["level"] == "SEVERE"]
        assert not errors, f"JS errors on initial render: {errors}"


class TestDataUpdate:
    def test_update_changes_title(self, loaded_page) -> None:
        """Pushing new data to the store triggers a re-render with new config."""
        _click_update(loaded_page)
        title = _get_title_text(loaded_page)
        assert "Update #" in title, f"title after update: {title!r}"

    def test_canvases_still_present_after_update(self, loaded_page) -> None:
        assert _has_canvases(loaded_page)

    def test_instance_recreated_after_update(self, loaded_page) -> None:
        """Always-recreate: each data update destroys the old instance
        and builds a new one (R/htmlwidgets model).
        """
        id_before = _get_instance_id(loaded_page)
        assert id_before is not None, "no dygraph instance found"
        _click_update(loaded_page)
        id_after = _get_instance_id(loaded_page)
        assert id_after is not None, "no dygraph instance after update"
        assert id_before != id_after, (
            "instance was reused — expected always-recreate to build a new one"
        )

    def test_no_severe_js_errors_after_update(self, loaded_page) -> None:
        _click_update(loaded_page)
        logs = loaded_page.get_log("browser")
        errors = [e for e in logs if e["level"] == "SEVERE"]
        assert not errors, f"JS errors after update: {errors}"


class TestZoomBehavior:
    def test_zoom_resets_on_update_by_default(self, loaded_page) -> None:
        """With always-recreate, zoom resets to full range on data update.

        This matches R's default (retainDateWindow = FALSE). The chart
        is destroyed and rebuilt, so no prior zoom state carries over.
        """
        # Set a narrow zoom window
        loaded_page.execute_script(
            "var c = document.getElementById('upd-chart-container');"
            "if (c._dygraphInstance) {"
            "  var dw = ['2024-02-01','2024-02-15'].map(function(s){"
            "    return new Date(s).getTime(); });"
            "  c._dygraphInstance.updateOptions({dateWindow: dw});"
            "}"
        )
        time.sleep(0.3)

        # Trigger data update — should reset zoom to full range
        _click_update(loaded_page)

        xrange = loaded_page.execute_script(
            "var c = document.getElementById('upd-chart-container');"
            "return c._dygraphInstance ? c._dygraphInstance.xAxisRange() : null;"
        )
        assert xrange is not None
        span_days = (xrange[1] - xrange[0]) / 86400000
        # Full data is 60 days. After reset, should span most of that.
        assert span_days > 50, (
            f"after update, range spans {span_days:.0f} days — "
            "expected zoom to reset to full range (~60 days)"
        )


class TestModebarAfterUpdate:
    def test_reset_zoom_works(self, loaded_page) -> None:
        """The modebar reset-zoom button works after a data update."""
        _click_update(loaded_page)

        # Zoom in first
        loaded_page.execute_script(
            "var c = document.getElementById('upd-chart-container');"
            "if (c._dygraphInstance) {"
            "  c._dygraphInstance.updateOptions({dateWindow: ["
            "    new Date('2024-02-01').getTime(),"
            "    new Date('2024-02-15').getTime()"
            "  ]});"
            "}"
        )
        time.sleep(0.3)

        # Reset via the global function (same as modebar button click)
        loaded_page.execute_script("window.__dyReset_upd_chart();")
        time.sleep(0.3)

        xrange = loaded_page.execute_script(
            "var c = document.getElementById('upd-chart-container');"
            "return c._dygraphInstance ? c._dygraphInstance.xAxisRange() : null;"
        )
        assert xrange is not None
        # After reset, the range should span the full data (Jan-Feb 2024)
        span_days = (xrange[1] - xrange[0]) / 86400000
        assert span_days > 50, (
            f"after reset, range spans only {span_days:.0f} days — expected ~60"
        )
