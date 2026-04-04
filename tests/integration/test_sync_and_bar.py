"""Chrome integration tests for sync_dygraphs and stacked_bar."""

from __future__ import annotations

import socket
import threading
import time

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="module")
def synced_app_url():
    """Start a Dash app with synced dygraphs + stacked bar."""
    from dash import Dash, html

    from pydygraphs import Dygraph, stacked_bar, sync_dygraphs

    app = Dash(__name__)

    df1 = pd.DataFrame(
        {"temp": np.arange(30, dtype=float), "rain": np.arange(30, 60, dtype=float)},
        index=pd.date_range("2024-01-01", periods=30, freq="D"),
    )
    df2 = pd.DataFrame(
        {"pressure": np.arange(100, 130, dtype=float)},
        index=pd.date_range("2024-01-01", periods=30, freq="D"),
    )

    chart_a = (
        Dygraph(df1, title="Chart A")
        .options(animated_zooms=False)
        .range_selector(height=20)
        .to_dash(app=app, component_id="chart-a", height=200)
    )
    chart_b = (
        Dygraph(df2, title="Chart B")
        .options(animated_zooms=False)
        .range_selector(height=20)
        .to_dash(app=app, component_id="chart-b", height=200)
    )

    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    bar_csv = pd.DataFrame(
        {
            "Date": dates.strftime("%Y/%m/%d"),
            "Solar": np.random.rand(30).round(2),
            "Wind": np.random.rand(30).round(2),
        }
    ).to_csv(index=False)

    chart_c = stacked_bar(
        app,
        "chart-c",
        initial_data=bar_csv,
        colors=["#00d4aa", "#7eb8f7"],
        height=200,
        title="Stacked Bar",
    )

    sync = sync_dygraphs(app, ["chart-a", "chart-b", "chart-c"])

    app.layout = html.Div(
        [
            sync,
            html.H1("Sync Test", id="sync-heading"),
            chart_a,
            chart_b,
            chart_c,
        ]
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    server_thread = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()
    time.sleep(3)
    yield f"http://127.0.0.1:{port}"


@pytest.fixture(scope="module")
def chrome_driver():
    """Headless Chrome WebDriver."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1200,900")

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


# ---------------------------------------------------------------------------
# Sync tests
# ---------------------------------------------------------------------------


def test_all_three_charts_render(synced_app_url: str, chrome_driver) -> None:
    """All three chart containers should be present and non-empty."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    heading = chrome_driver.find_element("id", "sync-heading")
    assert "Sync Test" in heading.text

    for cid in ["chart-a-container", "chart-b-container", "chart-c-container"]:
        el = chrome_driver.find_element("id", cid)
        html = el.get_attribute("innerHTML")
        assert len(html) > 50, f"{cid} should have rendered content"


def test_dygraph_charts_have_canvas(synced_app_url: str, chrome_driver) -> None:
    """Dygraph charts (a, b) should render canvas elements."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    for cid in ["chart-a-container", "chart-b-container"]:
        el = chrome_driver.find_element("id", cid)
        canvases = el.find_elements("tag name", "canvas")
        assert len(canvases) > 0, f"{cid} should have canvas elements"


def test_stacked_bar_has_canvas(synced_app_url: str, chrome_driver) -> None:
    """Stacked bar chart should render a canvas element."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    el = chrome_driver.find_element("id", "chart-c-container")
    canvases = el.find_elements("tag name", "canvas")
    assert len(canvases) > 0, "Stacked bar should have a canvas element"


def test_dygraph_charts_have_range_selector(synced_app_url: str, chrome_driver) -> None:
    """Dygraph charts should have range selector elements."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    for cid in ["chart-a-container", "chart-b-container"]:
        el = chrome_driver.find_element("id", cid)
        fg = el.find_elements("class name", "dygraph-rangesel-fgcanvas")
        assert len(fg) > 0, f"{cid} should have a range selector foreground canvas"


def test_dygraph_charts_have_modebar(synced_app_url: str, chrome_driver) -> None:
    """Dygraph charts should have modebar overlay."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    for cid in ["chart-a-container", "chart-b-container"]:
        el = chrome_driver.find_element("id", cid)
        modebar = el.find_elements("class name", "dy-modebar")
        assert len(modebar) > 0, f"{cid} should have a modebar"


def test_dygraph_titles_rendered(synced_app_url: str, chrome_driver) -> None:
    """Chart titles should be visible."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    for cid, title in [
        ("chart-a-container", "Chart A"),
        ("chart-b-container", "Chart B"),
    ]:
        el = chrome_driver.find_element("id", cid)
        titles = el.find_elements("class name", "dygraph-title")
        assert len(titles) > 0, f"{cid} should have a title element"
        assert title in titles[0].text


def test_stacked_bar_title_rendered(synced_app_url: str, chrome_driver) -> None:
    """Stacked bar title should be rendered on canvas (check canvas is tall enough)."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    el = chrome_driver.find_element("id", "chart-c-container")
    canvas = el.find_element("tag name", "canvas")
    # Canvas should have reasonable dimensions
    height = canvas.get_attribute("height")
    assert int(height) > 200, (
        "Stacked bar canvas should be tall enough for chart + selector"
    )


def test_sync_zoom_propagates(synced_app_url: str, chrome_driver) -> None:
    """Zooming chart A should update chart B's date window via sync."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    # Get initial x-axis range of chart B
    initial_range_b = chrome_driver.execute_script("""
        var el = document.getElementById('chart-b-container');
        if (el && el._dygraphInstance) {
            return el._dygraphInstance.xAxisRange();
        }
        return null;
    """)
    assert initial_range_b is not None, "Chart B should have a dygraph instance"

    # Programmatically zoom chart A to a smaller window
    chrome_driver.execute_script("""
        var el = document.getElementById('chart-a-container');
        if (el && el._dygraphInstance) {
            var range = el._dygraphInstance.xAxisRange();
            var span = range[1] - range[0];
            el._dygraphInstance.updateOptions({
                dateWindow: [range[0] + span * 0.25, range[1] - span * 0.25]
            });
            // Manually trigger zoomCallback to propagate sync
            window['__dyZoom_chart_a'] = {
                dateWindow: [range[0] + span * 0.25, range[1] - span * 0.25],
                source: 'chart-a'
            };
        }
    """)
    time.sleep(2)

    # Check that chart B's range changed
    new_range_b = chrome_driver.execute_script("""
        var el = document.getElementById('chart-b-container');
        if (el && el._dygraphInstance) {
            return el._dygraphInstance.xAxisRange();
        }
        return null;
    """)

    assert new_range_b is not None
    # The range should have narrowed (larger start, smaller end)
    assert new_range_b[0] > initial_range_b[0] or new_range_b[1] < initial_range_b[1], (
        f"Chart B should have synced zoom. Initial: {initial_range_b}, After: {new_range_b}"
    )


def test_reset_zoom_via_modebar(synced_app_url: str, chrome_driver) -> None:
    """The reset zoom button should restore the full range."""
    chrome_driver.get(synced_app_url)
    time.sleep(5)

    # Zoom in first
    chrome_driver.execute_script("""
        var el = document.getElementById('chart-a-container');
        if (el && el._dygraphInstance) {
            var range = el._dygraphInstance.xAxisRange();
            var span = range[1] - range[0];
            el._dygraphInstance.updateOptions({
                dateWindow: [range[0] + span * 0.3, range[1] - span * 0.3]
            });
        }
    """)
    time.sleep(1)

    zoomed_range = chrome_driver.execute_script("""
        var el = document.getElementById('chart-a-container');
        return el._dygraphInstance.xAxisRange();
    """)

    # Reset via the global function (same as modebar button)
    chrome_driver.execute_script("window.__dyReset_chart_a();")
    time.sleep(1)

    reset_range = chrome_driver.execute_script("""
        var el = document.getElementById('chart-a-container');
        return el._dygraphInstance.xAxisRange();
    """)

    # After reset, range should be wider than zoomed
    assert (reset_range[1] - reset_range[0]) > (zoomed_range[1] - zoomed_range[0]), (
        f"Reset should restore full range. Zoomed: {zoomed_range}, Reset: {reset_range}"
    )
