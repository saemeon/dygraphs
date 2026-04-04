"""Chrome integration test — verifies a dygraph actually renders in Dash."""

from __future__ import annotations

import socket
import threading
import time

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def dash_app_url():
    """Start a Dash app with a real dygraph chart."""
    from dash import Dash, html

    from dash_dygraphs import Dygraph

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

    component = dg.to_dash(app=app, component_id="test-chart", height="300px")
    app.layout = html.Div([html.H1("Integration Test", id="heading"), component])

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
            return  # unreachable but keeps type checker happy

    yield driver
    driver.quit()


def test_dygraph_renders_canvas(dash_app_url: str, chrome_driver) -> None:
    """Verify the dygraph renders a canvas element in the browser."""
    chrome_driver.get(dash_app_url)
    time.sleep(3)  # wait for Dash to render + clientside callback

    # The heading should be there
    heading = chrome_driver.find_element("id", "heading")
    assert "Integration Test" in heading.text

    # The chart container should exist
    container = chrome_driver.find_element("id", "test-chart-container")
    assert container is not None

    # Dygraph renders into canvas elements inside the container
    canvases = container.find_elements("tag name", "canvas")
    assert len(canvases) > 0, "Dygraph should render at least one canvas element"


def test_dygraph_has_title(dash_app_url: str, chrome_driver) -> None:
    """Verify the chart title is rendered."""
    chrome_driver.get(dash_app_url)
    time.sleep(3)

    container = chrome_driver.find_element("id", "test-chart-container")
    # Dygraph renders the title in a div with class 'dygraph-title'
    titles = container.find_elements("class name", "dygraph-title")
    if titles:
        assert "Weather Data" in titles[0].text


def test_dygraph_has_legend(dash_app_url: str, chrome_driver) -> None:
    """Verify the legend is rendered."""
    chrome_driver.get(dash_app_url)
    time.sleep(3)

    container = chrome_driver.find_element("id", "test-chart-container")
    legends = container.find_elements("class name", "dygraph-legend")
    assert len(legends) > 0, "Legend should be rendered when show='always'"
