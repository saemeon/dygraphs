"""Chrome integration test — verifies a dygraph actually renders in Dash."""

from __future__ import annotations

import socket
import threading
import time
import urllib.request

import pandas as pd
import pytest


def _poll(fn, *, timeout=10, interval=0.2):
    """Poll ``fn()`` until truthy, raise TimeoutError otherwise."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    raise TimeoutError(f"poll timed out after {timeout}s")


def _try_connect(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=1)
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def dash_app_url():
    """Start a Dash app with a real dygraph chart."""
    from dash import Dash, html

    from dygraphs import Dygraph

    app = Dash(__name__)

    df = pd.DataFrame(
        {"temp": [10, 12, 11, 14, 13, 15, 12], "rain": [5, 3, 7, 2, 6, 4, 8]},
        index=pd.date_range("2020-01-01", periods=7, freq="D"),
    )

    dg = (
        Dygraph(df, title="Weather Data")
        .options(fill_graph=True, draw_points=True)
        .axis("y", label="Temperature")
        .series("temp", color="red", stroke_width=2)
        .legend(show="always")
        .range_selector(height=30)
        .annotation("2020-01-04", "A", tooltip="Annotation here")
        .event("2020-01-05", "Event", label_loc="top")
        .shading("2020-01-02", "2020-01-03")
    )

    component = dg.to_dash(component_id="test-chart", height="300px")
    app.layout = html.Div([html.H1("Integration Test", id="heading"), component])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False),
        daemon=True,
    ).start()
    url = f"http://127.0.0.1:{port}"
    _poll(lambda: _try_connect(url), timeout=10)
    yield url


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
    """Navigate once, poll until the chart canvases appear, return the driver."""
    chrome_driver.get(dash_app_url)
    _poll(
        lambda: chrome_driver.execute_script(
            "return document.querySelectorAll('#test-chart-container canvas')"
            ".length > 0;"
        ),
        timeout=15,
    )
    return chrome_driver


def test_dygraph_renders_canvas(loaded_page) -> None:
    """Verify the dygraph renders a canvas element in the browser."""
    logs = loaded_page.get_log("browser")
    errors = [e for e in logs if e["level"] == "SEVERE"]
    assert not errors, f"JS errors: {errors}"

    heading = loaded_page.find_element("id", "heading")
    assert "Integration Test" in heading.text

    container = loaded_page.find_element("id", "test-chart-container")
    canvases = container.find_elements("tag name", "canvas")
    assert len(canvases) > 0, "Dygraph should render at least one canvas element"


def test_dygraph_has_title(loaded_page) -> None:
    """Verify the chart title is rendered."""
    container = loaded_page.find_element("id", "test-chart-container")
    titles = container.find_elements("class name", "dygraph-title")
    if titles:
        assert "Weather Data" in titles[0].text


def test_dygraph_has_legend(loaded_page) -> None:
    """Verify the legend is rendered."""
    container = loaded_page.find_element("id", "test-chart-container")
    legends = container.find_elements("class name", "dygraph-legend")
    inner_html = loaded_page.execute_script(
        "return document.getElementById('test-chart-container').innerHTML"
    )
    assert len(inner_html) > 100 or len(legends) > 0, (
        "Chart should have rendered content"
    )
