"""Dummy Chrome integration test — verifies Selenium + Chrome + Dash toolchain works."""

from __future__ import annotations

import threading
import time

import pytest


@pytest.fixture(scope="module")
def dash_app_url():
    """Start a minimal Dash app on a free port and return its URL."""
    from dash import Dash, html

    app = Dash(__name__)
    app.layout = html.Div("Hello from pydygraphs integration test", id="root")

    # Find a free port
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    server_thread = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()
    time.sleep(2)  # give Dash time to start
    yield f"http://127.0.0.1:{port}"


@pytest.fixture(scope="module")
def chrome_driver():
    """Create a headless Chrome WebDriver."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # Try to find chromedriver; fall back to Chrome for Testing
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
    except Exception:
        # Try with explicit Chrome binary path on macOS
        options.binary_location = (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        )
        try:
            driver = webdriver.Chrome(options=options)
        except Exception as exc:
            pytest.skip(f"Chrome/chromedriver not available: {exc}")

    yield driver
    driver.quit()


def test_dash_app_renders_in_chrome(dash_app_url: str, chrome_driver) -> None:
    """Verify we can start Dash, open it in headless Chrome, and read the DOM."""
    chrome_driver.get(dash_app_url)
    time.sleep(1)

    root = chrome_driver.find_element("id", "root")
    assert "Hello from pydygraphs" in root.text
