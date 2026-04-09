"""Browser-side capture strategy tests.

Spins up a real Dash app with a Dygraph chart of known dimensions and
known content, then runs the multi-canvas merge JS via
``driver.execute_script`` and asserts on the resulting PNG.

These tests catch the bugs we hit during the capture refactor:
* DPR cropping (output canvas sized in CSS px while drawing device-px sources)
* IIFE-wrapper-vs-statement confusion
* Drift between the modebar download and dash-capture wizard code paths

Requires Chrome + chromedriver. Skipped if Chrome is unavailable.
"""

from __future__ import annotations

import base64
import socket
import threading
import time
from io import BytesIO

import pandas as pd
import pytest

# Known dimensions / data so the assertions can be precise.
_CHART_HEIGHT_PX = 240
_SERIES_COLOR = "#00d4aa"
_DATES = pd.date_range("2024-01-01", periods=120, freq="D")


def _make_chart_df() -> pd.DataFrame:
    # A predictable, monotonic series so we know content reaches all four
    # corners of the plot area when zoomed out.
    return pd.DataFrame(
        {"y": list(range(120))},
        index=_DATES,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dash_app_url():
    """Spin up a Dash app with one chart at known dimensions."""
    from dash import Dash, html

    from dygraphs import Dygraph

    app = Dash(__name__)

    dg = (
        Dygraph(_make_chart_df(), title="Capture Test")
        .options(stroke_width=2, colors=[_SERIES_COLOR])
        .legend(show="always")
    )
    component = dg.to_dash(
        app=app, component_id="cap-chart", height=f"{_CHART_HEIGHT_PX}px"
    )
    app.layout = html.Div([component])

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
    """Navigate once, wait for the chart to render, return the driver."""
    chrome_driver.get(dash_app_url)
    time.sleep(5)  # CDN load + clientside callback + dygraph init
    # Sanity check: the chart's canvases must exist before any test runs.
    canvas_count = chrome_driver.execute_script(
        "return document.querySelectorAll('#cap-chart-container canvas').length;"
    )
    assert canvas_count > 0, (
        f"chart container has no canvases — chart didn't render. "
        f"Browser logs: {chrome_driver.get_log('browser')}"
    )
    return chrome_driver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_capture(driver, container_id: str) -> str:
    """Invoke the shared MULTI_CANVAS_CAPTURE_JS on a container element.

    This is the same JS used by both the dash-capture wizard strategy
    (via ``dygraph_strategy``) and the chart's modebar camera button
    (via ``window.__dyCap_*``). Calling it directly bypasses dash-capture
    so the test runs without the wizard infrastructure.
    """
    from dygraphs.dash.capture import MULTI_CANVAS_CAPTURE_JS

    js = (
        f"var captureFn = ({MULTI_CANVAS_CAPTURE_JS});\n"
        f"var el = document.getElementById('{container_id}');\n"
        "if (!el) throw new Error('container not found');\n"
        "return captureFn(el, 'png', true, false);"
    )
    return driver.execute_script(js)


def _decode_data_uri(uri: str):
    from PIL import Image

    assert uri.startswith("data:image/png;base64,"), (
        f"expected png data-URI, got: {uri[:60]}"
    )
    b64 = uri.split(",", 1)[1]
    return Image.open(BytesIO(base64.b64decode(b64)))


def _non_white_bbox(img):
    """Bounding box of pixels that aren't pure white.

    Returns ``None`` if the entire image is white. ``Image.getbbox`` is
    not useful here because it considers any non-zero pixel as content,
    and our white background is RGB(255, 255, 255).
    """
    import numpy as np

    arr = np.array(img.convert("RGB"))
    non_white = arr.sum(axis=-1) < 765  # 3 * 255
    ys, xs = np.where(non_white)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def _container_dimensions(driver, container_id: str) -> tuple[int, int, float]:
    info = driver.execute_script(
        f"var el = document.getElementById('{container_id}');"
        "return [el.offsetWidth, el.offsetHeight, window.devicePixelRatio || 1];"
    )
    return int(info[0]), int(info[1]), float(info[2])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_capture_returns_data_uri(loaded_page) -> None:
    """The capture function actually executes and returns a PNG data-URI.

    Catches gross failures: function not loaded, syntax error, IIFE
    parser collisions, etc.
    """
    uri = _run_capture(loaded_page, "cap-chart-container")
    assert uri.startswith("data:image/png;base64,")
    # Sanity check: a real PNG should decode to a non-trivial image.
    img = _decode_data_uri(uri)
    assert img.width > 0 and img.height > 0


def test_capture_dimensions_match_container_times_dpr(loaded_page) -> None:
    """Output PNG is sized at container CSS px × devicePixelRatio.

    This is the original DPR bug. The first version sized the output
    canvas in CSS pixels and called drawImage's 3-arg form, which paints
    the source canvas at its *natural* (device-px) size, so on a retina
    display the right and bottom of the chart got cropped.
    """
    css_w, css_h, dpr = _container_dimensions(loaded_page, "cap-chart-container")
    img = _decode_data_uri(_run_capture(loaded_page, "cap-chart-container"))

    expected_w = round(css_w * dpr)
    expected_h = round(css_h * dpr)
    # Allow ±1 px for rounding.
    assert abs(img.width - expected_w) <= 1, (
        f"width mismatch: img={img.width}, expected≈{expected_w} "
        f"(css_w={css_w}, dpr={dpr})"
    )
    assert abs(img.height - expected_h) <= 1, (
        f"height mismatch: img={img.height}, expected≈{expected_h} "
        f"(css_h={css_h}, dpr={dpr})"
    )


def test_capture_content_fills_canvas(loaded_page) -> None:
    """Non-white content occupies most of the captured image.

    The original DPR bug manifested as content concentrated in the
    top-left quadrant (the source canvas was drawn at its natural
    backing size, so a 1600x600 source ended up painted into an 800x300
    output and only the upper-left fit). The bbox of non-white pixels
    catches that symptom directly.
    """
    img = _decode_data_uri(_run_capture(loaded_page, "cap-chart-container"))
    bbox = _non_white_bbox(img)
    assert bbox is not None, "captured image is entirely white"
    bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    img_area = img.width * img.height
    coverage = bbox_area / img_area
    assert coverage > 0.85, (
        f"non-white bbox covers only {coverage:.0%} of the image — "
        f"likely cropped to a corner. bbox={bbox}, image={img.size}"
    )


def test_capture_edge_probes_find_content(loaded_page) -> None:
    """Each edge of the inner image area contains non-white pixels.

    Targeted regression check for direction-specific cropping. We probe
    the inner 80% of the image (excluding the outer 10% margin to avoid
    border anti-aliasing) on all four edges. If any edge is entirely
    white, content is being clipped on that side.
    """
    import numpy as np

    img = _decode_data_uri(_run_capture(loaded_page, "cap-chart-container"))
    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]
    mx, my = int(w * 0.1), int(h * 0.1)
    inner = arr[my : h - my, mx : w - mx]
    non_white = inner.sum(axis=-1) < 765

    edges = {
        "top": non_white[0, :].any(),
        "bottom": non_white[-1, :].any(),
        "left": non_white[:, 0].any(),
        "right": non_white[:, -1].any(),
    }
    missing = [name for name, has in edges.items() if not has]
    assert not missing, (
        f"no content found on edge(s): {missing}. "
        f"This usually means the chart is cropped on that side."
    )


def test_capture_after_zoom_keeps_dimensions(loaded_page) -> None:
    """Triggering a programmatic zoom and re-capturing still produces a
    correctly-sized PNG.

    Catches regressions where the post-zoom DOM state confuses the
    capture (e.g. range-selector hiding side-effects, group-sync
    callbacks tampering with size).
    """
    # Force a zoom by calling updateOptions on the underlying instance.
    loaded_page.execute_script(
        "var c = document.getElementById('cap-chart-container');"
        "var dw = ['2024-02-01', '2024-03-15'].map(function(s){"
        "  return new Date(s).getTime(); });"
        "if (c._dygraphInstance) c._dygraphInstance.updateOptions({dateWindow: dw});"
    )
    time.sleep(0.5)
    css_w, css_h, dpr = _container_dimensions(loaded_page, "cap-chart-container")
    img = _decode_data_uri(_run_capture(loaded_page, "cap-chart-container"))
    assert abs(img.width - round(css_w * dpr)) <= 1
    assert abs(img.height - round(css_h * dpr)) <= 1
