"""Compare Python dygraphs JSON output against R dygraphs output.

These tests call Rscript to generate the R reference output and compare
it structurally against the Python equivalent.  They require R with the
``dygraphs`` package installed and are skipped otherwise.

Run with::

    uv run pytest tests/integration/test_r_parity.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from typing import Any

import pandas as pd
import pytest

from dygraphs import Dygraph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RSCRIPT = shutil.which("Rscript")

# Common preamble for all R scripts
_R_PREAMBLE = textwrap.dedent("""\
    suppressPackageStartupMessages({
        library(dygraphs)
        library(jsonlite)
        library(xts)
    })
    strip_js <- function(obj) {
        if (is.list(obj)) return(lapply(obj, strip_js))
        if (inherits(obj, "JS_EVAL")) return(paste0("__JS__:", as.character(obj)))
        return(obj)
    }
""")


def _r_available() -> bool:
    """Check if Rscript and the dygraphs package are available."""
    if _RSCRIPT is None:
        return False
    try:
        result = subprocess.run(
            [_RSCRIPT, "-e", "library(dygraphs)"],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


_HAS_R = _r_available()
pytestmark = pytest.mark.skipif(not _HAS_R, reason="R + dygraphs not available")


def _run_r(script: str) -> dict[str, Any]:
    """Run an R script and parse the JSON output."""
    full = _R_PREAMBLE + script
    result = subprocess.run(
        [_RSCRIPT, "-e", full],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        pytest.fail(f"R script failed:\n{result.stderr}")
    return json.loads(result.stdout)


def _python_config(dg: Dygraph) -> dict[str, Any]:
    """Get the Python config dict, normalised for comparison."""
    return dg.to_dict()


# --- Key-level comparison helpers ---


def _normalise_value(val: Any) -> Any:
    """Normalise a value for comparison across R/Python."""
    if isinstance(val, str):
        # R has a bug: " #A7B1C4" (leading space) in rangeSelectorPlotFillColor
        val = val.strip()
        # R serialises JS_EVAL as "__JS__:code", Python stores JS objects
        if val.startswith("__JS__:"):
            return ("__JS__", val[7:])
    if hasattr(val, "code"):  # Python JS object
        return ("__JS__", val.code)
    return val


def _compare_attrs(
    r_attrs: dict[str, Any],
    py_attrs: dict[str, Any],
    *,
    ignore_keys: set[str] | None = None,
) -> list[str]:
    """Compare R attrs against Python attrs, returning list of differences.

    Only checks keys present in R — Python may have extra keys (features
    not in R) which are not flagged.
    """
    diffs: list[str] = []
    skip = ignore_keys or set()
    for key in r_attrs:
        if key in skip:
            continue
        if key not in py_attrs:
            diffs.append(f"Key {key!r} in R but missing in Python")
            continue
        r_val = _normalise_value(r_attrs[key])
        py_val = _normalise_value(py_attrs[key])
        if isinstance(r_val, dict) and isinstance(py_val, dict):
            sub = _compare_attrs(r_val, py_val, ignore_keys=skip)
            diffs.extend(f"{key}.{d}" for d in sub)
        elif isinstance(r_val, float) and isinstance(py_val, int | float):
            if abs(r_val - py_val) > 1e-9:
                diffs.append(f"{key}: R={r_val!r} != Py={py_val!r}")
        elif r_val != py_val:
            diffs.append(f"{key}: R={r_val!r} != Py={py_val!r}")
    return diffs


# --- Shared test data ---

_DATES = pd.date_range("2020-01-01", periods=5, freq="D")

_R_TS_2COL = textwrap.dedent("""\
    data <- data.frame(Date=as.Date("2020-01-01") + 0:4,
                       a=c(1,2,3,4,5), b=c(5,4,3,2,1))
    ts <- xts(data[,c("a","b")], order.by=data$Date)
""")


def _py_df_2col() -> pd.DataFrame:
    return pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1]}, index=_DATES)


_R_TS_3COL = textwrap.dedent("""\
    data <- data.frame(Date=as.Date("2020-01-01") + 0:4,
                       a=c(1,2,3,4,5), b=c(5,4,3,2,1), c=c(3,1,4,1,5))
    ts <- xts(data[,c("a","b","c")], order.by=data$Date)
""")


def _py_df_3col() -> pd.DataFrame:
    return pd.DataFrame(
        {"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1], "c": [3, 1, 4, 1, 5]},
        index=_DATES,
    )


_R_TS_1COL = textwrap.dedent("""\
    data <- data.frame(Date=as.Date("2020-01-01") + 0:4, y=c(1,2,3,4,5))
    ts <- xts(data[,"y",drop=FALSE], order.by=data$Date)
""")


def _py_df_1col() -> pd.DataFrame:
    return pd.DataFrame({"y": [1, 2, 3, 4, 5]}, index=_DATES)


# Keys we intentionally skip in comparison.
# - labels: first element differs (R: "day"/"month", Python: "Date"/"x") — cosmetic
# - pixelsPerLabel: R sets 60 on x-axis by default, Python doesn't (cosmetic)
# - scale: R includes "daily"/"monthly" etc., Python doesn't (unused by JS)
# - mobileDisableYTouch: R always emits, Python only emits when False
# - highlightSeriesOpts: R emits [] for empty, Python omits
# - colors: R may reorder when series labels are renamed; compare separately
_SKIP_KEYS = {
    "labels",
    "scale",
    "mobileDisableYTouch",
    "highlightSeriesOpts",
    "colors",
}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestBasicChart:
    """Compare minimal chart creation."""

    def test_data_format_and_labels(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts, main="Test")
            cat(toJSON(strip_js(dg$x), auto_unbox=TRUE))
        """)
        py = _python_config(Dygraph(_py_df_1col(), title="Test"))

        assert r["format"] == py["format"] == "date"
        # Series labels match (skip x-axis label — R:"day", Python:"Date")
        assert r["attrs"]["labels"][1:] == py["attrs"]["labels"][1:]
        assert len(r["data"]) == len(py["data"])
        assert r["data"][1] == py["data"][1]  # y-values match
        assert r["attrs"]["title"] == py["attrs"]["title"]

    def test_data_values_match(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts)
            cat(toJSON(strip_js(dg$x), auto_unbox=TRUE))
        """)
        py = _python_config(Dygraph(_py_df_2col()))

        assert r["format"] == py["format"]
        # Compare actual data values (skip x-axis dates — format may differ)
        for col_idx in range(1, len(r["data"])):
            assert r["data"][col_idx] == py["data"][col_idx]


class TestDyOptions:
    """Compare dyOptions() output."""

    def test_default_options_match(self) -> None:
        """R dyOptions() with defaults should produce same attrs as Python."""
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyOptions()
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col()).options().to_dict()["attrs"]

        diffs = _compare_attrs(r, py, ignore_keys=_SKIP_KEYS)
        assert diffs == [], "Attribute differences:\n" + "\n".join(diffs)

    def test_non_default_options_match(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyOptions(fillGraph=TRUE, fillAlpha=0.3, strokeWidth=2,
                          drawPoints=TRUE, pointSize=3, stackedGraph=TRUE,
                          includeZero=TRUE, animatedZooms=TRUE, drawGrid=FALSE,
                          stepPlot=TRUE, labelsKMB=TRUE, disableZoom=TRUE,
                          colors=c("#ff0000","#00ff00"))
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .options(
                fill_graph=True,
                fill_alpha=0.3,
                stroke_width=2,
                draw_points=True,
                point_size=3,
                stacked_graph=True,
                include_zero=True,
                animated_zooms=True,
                draw_grid=False,
                step_plot=True,
                labels_kmb=True,
                disable_zoom=True,
                colors=["#ff0000", "#00ff00"],
            )
            .to_dict()["attrs"]
        )

        diffs = _compare_attrs(r, py, ignore_keys=_SKIP_KEYS)
        assert diffs == [], "Attribute differences:\n" + "\n".join(diffs)


class TestDySeries:
    """Compare dySeries() output."""

    def test_series_with_label_and_style(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dySeries("a", label="Alpha", color="#ff0000", strokeWidth=2)
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .series("a", label="Alpha", color="#ff0000", stroke_width=2)
            .to_dict()["attrs"]
        )

        # R renames "a" to "Alpha" in both labels and series keys
        assert "Alpha" in r["labels"]
        assert "Alpha" in py["labels"]
        assert (
            r["series"]["Alpha"]["strokeWidth"] == py["series"]["Alpha"]["strokeWidth"]
        )
        # Colors: both have #ff0000 for Alpha; other color auto-generated
        assert "#ff0000" in r["colors"]
        assert "#ff0000" in py["colors"]

    def test_series_y2_axis(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dySeries("b", axis="y2")
            cat(toJSON(strip_js(dg$x$attrs$series), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col()).series("b", axis="y2").to_dict()["attrs"]["series"]

        assert r["b"]["axis"] == py["b"]["axis"] == "y2"


class TestDyAxis:
    """Compare dyAxis() output."""

    def test_y_axis_with_range(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAxis("y", label="Values", valueRange=c(0, 10),
                       drawGrid=FALSE, axisLineColor="red")
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .axis(
                "y",
                label="Values",
                value_range=(0, 10),
                draw_grid=False,
                axis_line_color="red",
            )
            .to_dict()["attrs"]
        )

        assert r["ylabel"] == py["ylabel"] == "Values"
        assert r["axes"]["y"]["valueRange"] == py["axes"]["y"]["valueRange"]
        assert r["axes"]["y"]["drawGrid"] == py["axes"]["y"]["drawGrid"] == False  # noqa: E712
        assert r["axes"]["y"]["axisLineColor"] == py["axes"]["y"]["axisLineColor"]


class TestDyLegend:
    """Compare dyLegend() output."""

    def test_legend_always(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyLegend(show="always", width=200)
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).legend(show="always", width=200).to_dict()["attrs"]

        assert r["legend"] == py["legend"] == "always"
        assert r["labelsDivWidth"] == py["labelsDivWidth"] == 200


class TestDyHighlight:
    """Compare dyHighlight() output."""

    def test_highlight_options(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>%
                dyHighlight(highlightCircleSize=5,
                            highlightSeriesBackgroundAlpha=0.3,
                            hideOnMouseOut=FALSE)
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .highlight(
                circle_size=5, series_background_alpha=0.3, hide_on_mouse_out=False
            )
            .to_dict()["attrs"]
        )

        assert r["highlightCircleSize"] == py["highlightCircleSize"] == 5
        assert (
            r["highlightSeriesBackgroundAlpha"] == py["highlightSeriesBackgroundAlpha"]
        )
        assert r["hideOverlayOnMouseOut"] == py["hideOverlayOnMouseOut"] == False  # noqa: E712


class TestDyRangeSelector:
    """Compare dyRangeSelector() output."""

    def test_range_selector(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyRangeSelector(height=30)
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).range_selector(height=30).to_dict()["attrs"]

        assert r["showRangeSelector"] == py["showRangeSelector"] == True  # noqa: E712
        assert r["rangeSelectorHeight"] == py["rangeSelectorHeight"] == 30
        # Both should have interactionModel for keepMouseZoom
        r_im = _normalise_value(r.get("interactionModel", ""))
        py_im = _normalise_value(py.get("interactionModel"))
        assert r_im == py_im


class TestDyRoller:
    """Compare dyRoller() output."""

    def test_roller(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyRoller(rollPeriod=5)
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).roller(roll_period=5).to_dict()["attrs"]

        assert r["showRoller"] == py["showRoller"] == True  # noqa: E712
        assert r["rollPeriod"] == py["rollPeriod"] == 5


class TestAnnotations:
    """Compare dyAnnotation() output."""

    def test_annotation_structure(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>%
                dyAnnotation("2020-01-03", text="A", tooltip="Note")
            cat(toJSON(strip_js(dg$x$annotations), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .annotation("2020-01-03", text="A", tooltip="Note")
            .to_dict()["annotations"]
        )

        assert len(r) == len(py) == 1
        assert r[0]["shortText"] == py[0]["shortText"] == "A"
        assert r[0]["text"] == py[0]["text"] == "Note"
        assert r[0]["attachAtBottom"] == py[0]["attachAtBottom"] == False  # noqa: E712


class TestShadings:
    """Compare dyShading() output."""

    def test_shading_structure(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>%
                dyShading(from="2020-01-01", to="2020-01-03", color="#eee")
            cat(toJSON(strip_js(dg$x$shadings), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .shading("2020-01-01", "2020-01-03", color="#eee")
            .to_dict()["shadings"]
        )

        assert len(r) == len(py) == 1
        assert r[0]["color"] == py[0]["color"]
        assert r[0]["axis"] == py[0]["axis"] == "x"


class TestEvents:
    """Compare dyEvent() and dyLimit() output."""

    def test_event_structure(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>%
                dyEvent("2020-01-02", label="Evt", color="red")
            cat(toJSON(strip_js(dg$x$events), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .event("2020-01-02", label="Evt", color="red")
            .to_dict()["events"]
        )

        assert len(r) == len(py) == 1
        assert r[0]["label"] == py[0]["label"] == "Evt"
        assert r[0]["color"] == py[0]["color"] == "red"
        assert r[0]["strokePattern"] == py[0]["strokePattern"] == [7, 3]
        assert r[0]["axis"] == py[0]["axis"] == "x"

    def test_limit_structure(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyLimit(3, label="L", color="blue")
            cat(toJSON(strip_js(dg$x$events), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col()).limit(3, label="L", color="blue").to_dict()["events"]
        )

        assert len(r) == len(py) == 1
        assert r[0]["pos"] == py[0]["pos"] == 3
        assert r[0]["label"] == py[0]["label"] == "L"
        assert r[0]["color"] == py[0]["color"] == "blue"
        assert r[0]["axis"] == py[0]["axis"] == "y"


class TestFullPipeline:
    """Compare a full chart with many features."""

    def test_combined_features(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts, main="Full") %>%
                dyOptions(fillGraph=TRUE, strokeWidth=2) %>%
                dySeries("a", label="Alpha", color="#ff0000") %>%
                dyAxis("y", label="Y-Values") %>%
                dyLegend(show="always") %>%
                dyHighlight(highlightCircleSize=4) %>%
                dyRangeSelector(height=25) %>%
                dyRoller(rollPeriod=2) %>%
                dyAnnotation("2020-01-03", text="X", tooltip="Note") %>%
                dyEvent("2020-01-02", label="E") %>%
                dyShading(from="2020-01-01", to="2020-01-02") %>%
                dyLimit(2.5, label="Lim")
            cat(toJSON(strip_js(dg$x), auto_unbox=TRUE))
        """)
        py_dg = (
            Dygraph(_py_df_2col(), title="Full")
            .options(fill_graph=True, stroke_width=2)
            .series("a", label="Alpha", color="#ff0000")
            .axis("y", label="Y-Values")
            .legend(show="always")
            .highlight(circle_size=4)
            .range_selector(height=25)
            .roller(roll_period=2)
            .annotation("2020-01-03", text="X", tooltip="Note")
            .event("2020-01-02", label="E")
            .shading("2020-01-01", "2020-01-02")
            .limit(2.5, label="Lim")
        )
        py = _python_config(py_dg)

        # Top-level structure
        assert r["format"] == py["format"]
        assert len(r["annotations"]) == len(py["annotations"])
        assert len(r["shadings"]) == len(py["shadings"])
        assert len(r["events"]) == len(py["events"])

        # Attrs comparison (skip known cosmetic differences)
        diffs = _compare_attrs(r["attrs"], py["attrs"], ignore_keys=_SKIP_KEYS)
        assert diffs == [], "Attribute differences:\n" + "\n".join(diffs)

        # Data values match by series name (R may reorder columns on rename)
        r_labels = r["attrs"]["labels"]
        py_labels = py["attrs"]["labels"]
        for series_name in r_labels[1:]:
            if series_name in py_labels:
                r_idx = r_labels.index(series_name)
                py_idx = py_labels.index(series_name)
                assert r["data"][r_idx] == py["data"][py_idx], (
                    f"Data mismatch for series {series_name!r}"
                )


# ---------------------------------------------------------------------------
# Expanded comparisons
# ---------------------------------------------------------------------------


class TestStrokePatterns:
    """All named stroke patterns produce identical numeric arrays."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("dashed", [7, 3]),
            ("dotted", [2, 2]),
            ("dotdash", [7, 2, 2, 2]),
            ("solid", [1, 0]),
        ],
    )
    def test_named_pattern(self, name: str, expected: list[int]) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dySeries("a", strokePattern="{name}")
            cat(toJSON(strip_js(dg$x$attrs$series$a$strokePattern), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .series("a", stroke_pattern=name)
            .to_dict()["attrs"]["series"]["a"]["strokePattern"]
        )
        assert r == expected
        assert py == expected


class TestPerSeriesOptions:
    """Per-series styling options match R."""

    def test_fill_and_points(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dySeries("a", fillGraph=TRUE, drawPoints=TRUE, pointSize=3, stepPlot=TRUE)
            cat(toJSON(strip_js(dg$x$attrs$series$a), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .series(
                "a", fill_graph=True, draw_points=True, point_size=3, step_plot=True
            )
            .to_dict()["attrs"]["series"]["a"]
        )
        assert r["fillGraph"] == py["fillGraph"] == True  # noqa: E712
        assert r["drawPoints"] == py["drawPoints"] == True  # noqa: E712
        assert r["pointSize"] == py["pointSize"] == 3
        assert r["stepPlot"] == py["stepPlot"] == True  # noqa: E712

    def test_stroke_width_and_pattern(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dySeries("b", strokeWidth=3, strokePattern="dotdash")
            cat(toJSON(strip_js(dg$x$attrs$series$b), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .series("b", stroke_width=3, stroke_pattern="dotdash")
            .to_dict()["attrs"]["series"]["b"]
        )
        assert r["strokeWidth"] == py["strokeWidth"] == 3
        assert r["strokePattern"] == py["strokePattern"] == [7, 2, 2, 2]

    def test_multiple_series_different_opts(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dySeries("a", strokePattern="dashed", fillGraph=TRUE) %>%
                dySeries("b", strokePattern="dotted", stepPlot=TRUE)
            cat(toJSON(strip_js(dg$x$attrs$series), auto_unbox=TRUE))
        """)
        py_cfg = (
            Dygraph(_py_df_2col())
            .series("a", stroke_pattern="dashed", fill_graph=True)
            .series("b", stroke_pattern="dotted", step_plot=True)
            .to_dict()["attrs"]["series"]
        )
        assert r["a"]["strokePattern"] == py_cfg["a"]["strokePattern"]
        assert r["a"]["fillGraph"] == py_cfg["a"]["fillGraph"]
        assert r["b"]["strokePattern"] == py_cfg["b"]["strokePattern"]
        assert r["b"]["stepPlot"] == py_cfg["b"]["stepPlot"]


class TestDyGroup:
    """Compare dyGroup() output."""

    def test_group_with_colors_and_step(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyGroup(c("a","b"), color=c("red","blue"), stepPlot=TRUE)
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .group(["a", "b"], color=["red", "blue"], step_plot=True)
            .to_dict()["attrs"]
        )
        # Both should have series with stepPlot and group ID
        assert r["series"]["a"]["stepPlot"] == py["series"]["a"]["stepPlot"] == True  # noqa: E712
        assert r["series"]["b"]["stepPlot"] == py["series"]["b"]["stepPlot"] == True  # noqa: E712
        # Colors match
        assert r["colors"] == py["colors"] == ["red", "blue"]
        # Both assign a group ID (value differs — R: "ab", Python: "a\x1fb")
        assert r["series"]["a"]["group"] is not None
        assert py["series"]["a"]["group"] is not None
        assert r["series"]["a"]["group"] == r["series"]["b"]["group"]
        assert py["series"]["a"]["group"] == py["series"]["b"]["group"]

    def test_group_with_fill(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyGroup(c("a","b"), fillGraph=TRUE)
            cat(toJSON(strip_js(dg$x$attrs$series), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .group(["a", "b"], fill_graph=True)
            .to_dict()["attrs"]["series"]
        )
        assert r["a"]["fillGraph"] == py["a"]["fillGraph"] == True  # noqa: E712
        assert r["b"]["fillGraph"] == py["b"]["fillGraph"] == True  # noqa: E712


class TestAxisVariants:
    """Compare different axis configurations."""

    def test_x_axis_label_and_font(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyAxis("x", label="Time", axisLabelFontSize=12)
            cat(toJSON(strip_js(dg$x$attrs), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .axis("x", label="Time", axis_label_font_size=12)
            .to_dict()["attrs"]
        )
        assert r["xlabel"] == py["xlabel"] == "Time"
        assert (
            r["axes"]["x"]["axisLabelFontSize"]
            == py["axes"]["x"]["axisLabelFontSize"]
            == 12
        )

    def test_y2_axis_independent_ticks(self) -> None:
        r = _run_r(f"""
            {_R_TS_3COL}
            dg <- dygraph(ts) %>%
                dySeries("c", axis="y2") %>%
                dyAxis("y2", label="Right", independentTicks=TRUE, valueRange=c(0,10))
            cat(toJSON(strip_js(dg$x$attrs$axes$y2), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_3col())
            .series("c", axis="y2")
            .axis("y2", label="Right", independent_ticks=True, value_range=(0, 10))
            .to_dict()["attrs"]["axes"]["y2"]
        )
        assert r["independentTicks"] == py["independentTicks"] == True  # noqa: E712
        assert r["valueRange"] == py["valueRange"] == [0, 10]

    def test_y_axis_grid_options(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAxis("y", drawGrid=FALSE, gridLineColor="#ccc", gridLineWidth=0.5)
            cat(toJSON(strip_js(dg$x$attrs$axes$y), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .axis("y", draw_grid=False, grid_line_color="#ccc", grid_line_width=0.5)
            .to_dict()["attrs"]["axes"]["y"]
        )
        assert r["drawGrid"] == py["drawGrid"] == False  # noqa: E712
        assert r["gridLineColor"] == py["gridLineColor"] == "#ccc"
        assert r["gridLineWidth"] == py["gridLineWidth"] == 0.5


class TestMultipleOverlays:
    """Compare multiple events, shadings, annotations."""

    def test_multiple_events_different_locs(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyEvent("2020-01-02", label="E1", labelLoc="top") %>%
                dyEvent("2020-01-04", label="E2", labelLoc="bottom", color="red")
            cat(toJSON(strip_js(dg$x$events), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .event("2020-01-02", label="E1", label_loc="top")
            .event("2020-01-04", label="E2", label_loc="bottom", color="red")
            .to_dict()["events"]
        )
        assert len(r) == len(py) == 2
        assert r[0]["label"] == py[0]["label"] == "E1"
        assert r[0]["labelLoc"] == py[0]["labelLoc"] == "top"
        assert r[1]["label"] == py[1]["label"] == "E2"
        assert r[1]["labelLoc"] == py[1]["labelLoc"] == "bottom"
        assert r[1]["color"] == py[1]["color"] == "red"

    def test_multiple_shadings(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyShading(from="2020-01-01", to="2020-01-02", color="#fee") %>%
                dyShading(from="2020-01-03", to="2020-01-04", color="#efe")
            cat(toJSON(strip_js(dg$x$shadings), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .shading("2020-01-01", "2020-01-02", color="#fee")
            .shading("2020-01-03", "2020-01-04", color="#efe")
            .to_dict()["shadings"]
        )
        assert len(r) == len(py) == 2
        assert r[0]["color"] == py[0]["color"] == "#fee"
        assert r[1]["color"] == py[1]["color"] == "#efe"

    def test_multiple_annotations_with_dims(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAnnotation("2020-01-02", text="A", series="a", tooltip="First") %>%
                dyAnnotation("2020-01-04", text="B", series="b", tooltip="Second",
                             width=20, height=20)
            cat(toJSON(strip_js(dg$x$annotations), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .annotation("2020-01-02", text="A", series="a", tooltip="First")
            .annotation(
                "2020-01-04",
                text="B",
                series="b",
                tooltip="Second",
                width=20,
                height=20,
            )
            .to_dict()["annotations"]
        )
        assert len(r) == len(py) == 2
        assert r[0]["shortText"] == py[0]["shortText"] == "A"
        assert r[0]["series"] == py[0]["series"] == "a"
        assert r[1]["shortText"] == py[1]["shortText"] == "B"
        assert r[1]["series"] == py[1]["series"] == "b"
        assert r[1]["width"] == py[1]["width"] == 20
        assert r[1]["height"] == py[1]["height"] == 20


class TestLegendModes:
    """Compare legend mode variants."""

    def test_legend_never(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyLegend(show="never")
            cat(toJSON(strip_js(dg$x$attrs[c("showLabelsOnHighlight")]), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).legend(show="never").to_dict()["attrs"]
        # R sets showLabelsOnHighlight=false
        assert r["showLabelsOnHighlight"] == False  # noqa: E712
        assert py["showLabelsOnHighlight"] == False  # noqa: E712

    def test_legend_follow(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyLegend(show="follow")
            cat(toJSON(strip_js(dg$x$attrs$legend), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).legend(show="follow").to_dict()["attrs"]
        assert r == "follow"
        assert py["legend"] == "follow"


class TestHighlightAdvanced:
    """Compare highlight with seriesOpts."""

    def test_highlight_series_opts(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyHighlight(highlightSeriesOpts=list(strokeWidth=3, strokeBorderWidth=1))
            cat(toJSON(strip_js(dg$x$attrs$highlightSeriesOpts), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .highlight(series_opts={"strokeWidth": 3, "strokeBorderWidth": 1})
            .to_dict()["attrs"]["highlightSeriesOpts"]
        )
        assert r["strokeWidth"] == py["strokeWidth"] == 3
        assert r["strokeBorderWidth"] == py["strokeBorderWidth"] == 1


class TestRangeSelectorAdvanced:
    """Compare range selector with dateWindow and custom colors."""

    def test_range_selector_full(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyRangeSelector(dateWindow=c("2020-01-02","2020-01-04"),
                                height=50, fillColor="#aabbcc", strokeColor="#112233")
            cat(toJSON(strip_js(dg$x$attrs[c("showRangeSelector","rangeSelectorHeight",
                "rangeSelectorPlotStrokeColor","dateWindow")]), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .range_selector(
                date_window=("2020-01-02", "2020-01-04"),
                height=50,
                fill_color="#aabbcc",
                stroke_color="#112233",
            )
            .to_dict()["attrs"]
        )
        assert r["rangeSelectorHeight"] == py["rangeSelectorHeight"] == 50
        assert r["rangeSelectorPlotStrokeColor"] == py["rangeSelectorPlotStrokeColor"]
        # dateWindow: both should have 2020-01-02 and 2020-01-04
        assert "2020-01-02" in r["dateWindow"][0]
        assert "2020-01-02" in py["dateWindow"][0]


class TestCallbacksStructure:
    """Compare callback JS marker structure."""

    def test_multiple_callbacks(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyCallbacks(clickCallback="function(e,x,pts){{}}",
                            zoomCallback="function(a,b){{}}")
            cat(toJSON(strip_js(dg$x$attrs[c("clickCallback","zoomCallback")]),
                auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .callbacks(click="function(e,x,pts){}", zoom="function(a,b){}")
            .to_dict()["attrs"]
        )
        # R: "__JS__:function(e,x,pts){}" vs Python: JS object
        r_click = _normalise_value(r["clickCallback"])
        py_click = _normalise_value(py["clickCallback"])
        assert r_click == py_click
        r_zoom = _normalise_value(r["zoomCallback"])
        py_zoom = _normalise_value(py["zoomCallback"])
        assert r_zoom == py_zoom


class TestPluginStructure:
    """Compare plugin config structure.

    Note: R stores plugins as ``{"PluginName": options}`` while Python
    stores them as ``[{"name": "PluginName", "options": options}]``.
    We compare the logical content, not the container format.
    """

    def test_crosshair_direction(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyCrosshair(direction="vertical")
            cat(toJSON(strip_js(dg$x$plugins), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).crosshair(direction="vertical").to_dict()["plugins"]
        # R: {"Crosshair": {"direction": "vertical"}}
        # Python: [{"name": "Crosshair", "options": {"direction": "vertical"}}]
        assert r["Crosshair"]["direction"] == "vertical"
        py_plugin = next(p for p in py if p["name"] == "Crosshair")
        assert py_plugin["options"]["direction"] == "vertical"

    def test_rebase_value(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyRebase(value=100)
            cat(toJSON(strip_js(dg$x$plugins), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).rebase(value=100).to_dict()["plugins"]
        assert r["Rebase"] == 100
        py_plugin = next(p for p in py if p["name"] == "Rebase")
        assert py_plugin["options"] == 100

    def test_rebase_percent(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyRebase(percent=TRUE)
            cat(toJSON(strip_js(dg$x$plugins), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).rebase(percent=True).to_dict()["plugins"]
        assert r["Rebase"] == "percent"
        py_plugin = next(p for p in py if p["name"] == "Rebase")
        assert py_plugin["options"] == "percent"

    def test_ribbon_with_data(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>%
                dyRibbon(data=c(0,1,0,1,0), palette=c("red","blue"))
            cat(toJSON(strip_js(dg$x$plugins), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .ribbon(data=[0, 1, 0, 1, 0], palette=["red", "blue"])
            .to_dict()["plugins"]
        )
        # R: {"Ribbon": {"data": [...], "options": {"palette": [...], "top": 1, "bottom": 0}}}
        # Python: [{"name": "Ribbon", "options": {"data": [...], "options": {"palette": [...]}}}]
        assert r["Ribbon"]["data"] == [0, 1, 0, 1, 0]
        assert r["Ribbon"]["options"]["palette"] == ["red", "blue"]
        py_plugin = next(p for p in py if p["name"] == "Ribbon")
        assert py_plugin["options"]["data"] == [0, 1, 0, 1, 0]
        assert py_plugin["options"]["options"]["palette"] == ["red", "blue"]


class TestEventVariants:
    """Compare event/limit stroke pattern variants."""

    def test_event_solid_pattern(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyEvent("2020-01-03", strokePattern="solid")
            cat(toJSON(strip_js(dg$x$events[[1]]$strokePattern), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .event("2020-01-03", stroke_pattern="solid")
            .to_dict()["events"][0]["strokePattern"]
        )
        assert r == py == [1, 0]

    def test_limit_right_label_dotted(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>%
                dyLimit(2, label="Max", labelLoc="right", strokePattern="dotted")
            cat(toJSON(strip_js(dg$x$events[[1]]), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .limit(2, label="Max", label_loc="right", stroke_pattern="dotted")
            .to_dict()["events"][0]
        )
        assert r["pos"] == py["pos"] == 2
        assert r["labelLoc"] == py["labelLoc"] == "right"
        assert r["strokePattern"] == py["strokePattern"] == [2, 2]
        assert r["axis"] == py["axis"] == "y"


class TestRollerVariants:
    """Compare roller on/off."""

    def test_roller_disabled(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyRoller(showRoller=FALSE, rollPeriod=1)
            cat(toJSON(strip_js(dg$x$attrs[c("showRoller","rollPeriod")]), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).roller(show=False, roll_period=1).to_dict()["attrs"]
        assert r["showRoller"] == py["showRoller"] == False  # noqa: E712
        assert r["rollPeriod"] == py["rollPeriod"] == 1


class TestOptionsEdgeCases:
    """Compare edge-case option combinations."""

    def test_grid_line_overrides(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyOptions(gridLineColor="#ccc", gridLineWidth=0.5)
            cat(toJSON(strip_js(dg$x$attrs[c("gridLineColor","gridLineWidth")]),
                auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .options(grid_line_color="#ccc", grid_line_width=0.5)
            .to_dict()["attrs"]
        )
        assert r["gridLineColor"] == py["gridLineColor"] == "#ccc"
        assert r["gridLineWidth"] == py["gridLineWidth"] == 0.5

    def test_formatting_options(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyOptions(digitsAfterDecimal=4, maxNumberWidth=10, sigFigs=3,
                          labelsKMG2=TRUE, labelsUTC=TRUE)
            cat(toJSON(strip_js(dg$x$attrs[c("digitsAfterDecimal","maxNumberWidth",
                "sigFigs","labelsKMG2","labelsUTC")]), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .options(
                digits_after_decimal=4,
                max_number_width=10,
                sig_figs=3,
                labels_kmg2=True,
                labels_utc=True,
            )
            .to_dict()["attrs"]
        )
        assert r["digitsAfterDecimal"] == py["digitsAfterDecimal"] == 4
        assert r["maxNumberWidth"] == py["maxNumberWidth"] == 10
        assert r["sigFigs"] == py["sigFigs"] == 3
        assert r["labelsKMG2"] == py["labelsKMG2"] == True  # noqa: E712
        assert r["labelsUTC"] == py["labelsUTC"] == True  # noqa: E712

    def test_styling_options(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyOptions(axisLineColor="red", axisLineWidth=2, axisLabelColor="blue",
                          axisLabelFontSize=10, axisLabelWidth=80, axisTickSize=5,
                          titleHeight=30, rightGap=10, strokeBorderColor="green",
                          colorValue=0.7, colorSaturation=0.8)
            cat(toJSON(strip_js(dg$x$attrs[c("axisLineColor","axisLineWidth",
                "axisLabelColor","axisLabelFontSize","axisLabelWidth","axisTickSize",
                "titleHeight","rightGap","strokeBorderColor",
                "colorValue","colorSaturation")]), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .options(
                axis_line_color="red",
                axis_line_width=2,
                axis_label_color="blue",
                axis_label_font_size=10,
                axis_label_width=80,
                axis_tick_size=5,
                title_height=30,
                right_gap=10,
                stroke_border_color="green",
                color_value=0.7,
                color_saturation=0.8,
            )
            .to_dict()["attrs"]
        )
        for key in [
            "axisLineColor",
            "axisLineWidth",
            "axisLabelColor",
            "axisLabelFontSize",
            "axisLabelWidth",
            "axisTickSize",
            "titleHeight",
            "rightGap",
            "strokeBorderColor",
            "colorValue",
            "colorSaturation",
        ]:
            assert r[key] == py[key], f"{key}: R={r[key]!r} != Py={py[key]!r}"

    def test_boolean_options(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyOptions(drawGapEdgePoints=TRUE, connectSeparatedPoints=TRUE,
                          drawAxesAtZero=TRUE, retainDateWindow=TRUE)
            cat(toJSON(strip_js(dg$x$attrs[c("drawGapEdgePoints",
                "connectSeparatedPoints","drawAxesAtZero","retainDateWindow")]),
                auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .options(
                draw_gap_edge_points=True,
                connect_separated_points=True,
                draw_axes_at_zero=True,
                retain_date_window=True,
            )
            .to_dict()["attrs"]
        )
        for key in [
            "drawGapEdgePoints",
            "connectSeparatedPoints",
            "drawAxesAtZero",
            "retainDateWindow",
        ]:
            assert r[key] == py[key] == True, f"{key} mismatch"  # noqa: E712

    def test_stroke_border_width(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyOptions(strokeBorderWidth=2)
            cat(toJSON(strip_js(dg$x$attrs$strokeBorderWidth), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col()).options(stroke_border_width=2).to_dict()["attrs"]
        assert r == py["strokeBorderWidth"] == 2

    def test_pan_edge_fraction(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyOptions(panEdgeFraction=0.1)
            cat(toJSON(strip_js(dg$x$attrs$panEdgeFraction), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col()).options(pan_edge_fraction=0.1).to_dict()["attrs"]
        assert r == py["panEdgeFraction"] == 0.1


# ---------------------------------------------------------------------------
# Remaining per-series parameter coverage
# ---------------------------------------------------------------------------


class TestSeriesRemainingParams:
    """Cover all dySeries params not yet tested."""

    def test_series_stroke_border(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dySeries("a", strokeBorderWidth=2, strokeBorderColor="red")
            cat(toJSON(strip_js(dg$x$attrs$series$a), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .series("a", stroke_border_width=2, stroke_border_color="red")
            .to_dict()["attrs"]["series"]["a"]
        )
        assert r["strokeBorderWidth"] == py["strokeBorderWidth"] == 2
        assert r["strokeBorderColor"] == py["strokeBorderColor"] == "red"

    def test_series_stem_plot(self) -> None:
        """R stemPlot uses a plotter JS function; Python does the same."""
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dySeries("a", stemPlot=TRUE)
            cat(toJSON(strip_js(dg$x$attrs$series$a), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .series("a", stem_plot=True)
            .to_dict()["attrs"]["series"]["a"]
        )
        # Both should have a plotter (JS function for stem)
        r_plotter = _normalise_value(r.get("plotter", ""))
        py_plotter = _normalise_value(py.get("plotter"))
        assert r_plotter[0] == "__JS__"
        assert py_plotter[0] == "__JS__"
        # Both plotter functions should contain "stemPlotter"
        assert "stemPlotter" in r_plotter[1] or "stem" in r_plotter[1].lower()
        assert "stemPlotter" in py_plotter[1] or "stem" in py_plotter[1].lower()

    def test_series_fill_graph(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dySeries("b", fillGraph=TRUE)
            cat(toJSON(strip_js(dg$x$attrs$series$b), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .series("b", fill_graph=True)
            .to_dict()["attrs"]["series"]["b"]
        )
        assert r["fillGraph"] == py["fillGraph"] == True  # noqa: E712


# ---------------------------------------------------------------------------
# Remaining axis parameter coverage
# ---------------------------------------------------------------------------


class TestAxisRemainingParams:
    """Cover all dyAxis params not yet tested."""

    def test_axis_label_dimensions(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAxis("y", labelWidth=100, labelHeight=30) %>%
                dyAxis("x", labelHeight=25)
            cat(toJSON(strip_js(dg$x$attrs[c("yLabelWidth","yLabelHeight","xLabelHeight")]),
                auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .axis("y", label_width=100, label_height=30)
            .axis("x", label_height=25)
            .to_dict()["attrs"]
        )
        assert r["yLabelWidth"] == py["yLabelWidth"] == 100
        assert r["yLabelHeight"] == py["yLabelHeight"] == 30
        assert r["xLabelHeight"] == py["xLabelHeight"] == 25

    def test_axis_height_and_pixels_per_label(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAxis("x", axisHeight=30, pixelsPerLabel=80)
            cat(toJSON(strip_js(dg$x$attrs$axes$x), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .axis("x", axis_height=30, pixels_per_label=80)
            .to_dict()["attrs"]["axes"]["x"]
        )
        assert r["pixelsPerLabel"] == py["pixelsPerLabel"] == 80

    def test_axis_range_pad(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyAxis("y", rangePad=20)
            cat(toJSON(strip_js(dg$x$attrs$yRangePad), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col()).axis("y", range_pad=20).to_dict()["attrs"]
        assert r == py["yRangePad"] == 20

    def test_axis_line_styling(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAxis("y", axisLineColor="blue", axisLineWidth=2)
            cat(toJSON(strip_js(dg$x$attrs$axes$y), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .axis("y", axis_line_color="blue", axis_line_width=2)
            .to_dict()["attrs"]["axes"]["y"]
        )
        assert r["axisLineColor"] == py["axisLineColor"] == "blue"
        assert r["axisLineWidth"] == py["axisLineWidth"] == 2

    def test_axis_label_styling(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAxis("y", axisLabelColor="green", axisLabelFontSize=10,
                       axisLabelWidth=80)
            cat(toJSON(strip_js(dg$x$attrs$axes$y), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .axis(
                "y",
                axis_label_color="green",
                axis_label_font_size=10,
                axis_label_width=80,
            )
            .to_dict()["attrs"]["axes"]["y"]
        )
        assert r["axisLabelColor"] == py["axisLabelColor"] == "green"
        assert r["axisLabelFontSize"] == py["axisLabelFontSize"] == 10
        assert r["axisLabelWidth"] == py["axisLabelWidth"] == 80

    def test_axis_formatters(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAxis("y", valueFormatter="function(v){{return v.toFixed(1);}}",
                       axisLabelFormatter="function(v){{return v + ' m';}}")
            cat(toJSON(strip_js(dg$x$attrs$axes$y), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .axis(
                "y",
                value_formatter="function(v){return v.toFixed(1);}",
                axis_label_formatter="function(v){return v + ' m';}",
            )
            .to_dict()["attrs"]["axes"]["y"]
        )
        r_vf = _normalise_value(r["valueFormatter"])
        py_vf = _normalise_value(py["valueFormatter"])
        assert r_vf == py_vf
        r_af = _normalise_value(r["axisLabelFormatter"])
        py_af = _normalise_value(py["axisLabelFormatter"])
        assert r_af == py_af


# ---------------------------------------------------------------------------
# Remaining annotation parameter coverage
# ---------------------------------------------------------------------------


class TestAnnotationRemainingParams:
    """Cover all dyAnnotation params not yet tested."""

    def test_annotation_css_class_and_tick(self) -> None:
        r = _run_r(f"""
            {_R_TS_3COL}
            dg <- dygraph(ts) %>%
                dyAnnotation("2020-01-03", text="X", cssClass="my-ann", tickHeight=20)
            cat(toJSON(strip_js(dg$x$annotations[[1]]), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_3col())
            .annotation("2020-01-03", text="X", css_class="my-ann", tick_height=20)
            .to_dict()["annotations"][0]
        )
        assert r["cssClass"] == py["cssClass"] == "my-ann"
        assert r["tickHeight"] == py["tickHeight"] == 20

    def test_annotation_attach_at_bottom(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>%
                dyAnnotation("2020-01-03", text="B", attachAtBottom=TRUE)
            cat(toJSON(strip_js(dg$x$annotations[[1]]$attachAtBottom), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .annotation("2020-01-03", text="B", attach_at_bottom=True)
            .to_dict()["annotations"][0]
        )
        assert r == True  # noqa: E712
        assert py["attachAtBottom"] == True  # noqa: E712

    def test_annotation_with_series(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyAnnotation("2020-01-02", text="S", series="a")
            cat(toJSON(strip_js(dg$x$annotations[[1]]$series), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .annotation("2020-01-02", text="S", series="a")
            .to_dict()["annotations"][0]
        )
        assert r == "a"
        assert py["series"] == "a"


# ---------------------------------------------------------------------------
# Remaining legend parameter coverage
# ---------------------------------------------------------------------------


class TestLegendRemainingParams:
    """Cover all dyLegend params not yet tested."""

    def test_legend_zero_values_and_separate_lines(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyLegend(show="always", showZeroValues=FALSE, labelsSeparateLines=TRUE)
            cat(toJSON(strip_js(dg$x$attrs[c("labelsShowZeroValues","labelsSeparateLines")]),
                auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .legend(show="always", show_zero_values=False, labels_separate_lines=True)
            .to_dict()["attrs"]
        )
        assert r["labelsShowZeroValues"] == py["labelsShowZeroValues"] == False  # noqa: E712
        assert r["labelsSeparateLines"] == py["labelsSeparateLines"] == True  # noqa: E712


# ---------------------------------------------------------------------------
# Remaining range selector parameter coverage
# ---------------------------------------------------------------------------


class TestRangeSelectorRemainingParams:
    """Cover retainDateWindow and keepMouseZoom=FALSE."""

    def test_retain_date_window(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyRangeSelector(retainDateWindow=TRUE)
            cat(toJSON(strip_js(dg$x$attrs$retainDateWindow), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .range_selector(retain_date_window=True)
            .to_dict()["attrs"]
        )
        assert r == True  # noqa: E712
        assert py["retainDateWindow"] == True  # noqa: E712

    def test_no_mouse_zoom(self) -> None:
        """keepMouseZoom=FALSE should NOT set interactionModel."""
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyRangeSelector(keepMouseZoom=FALSE)
            cat(toJSON(strip_js(dg$x$attrs$showRangeSelector), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_1col())
            .range_selector(keep_mouse_zoom=False)
            .to_dict()["attrs"]
        )
        assert r == True  # noqa: E712
        assert py["showRangeSelector"] == True  # noqa: E712
        # When keepMouseZoom=FALSE, interactionModel should NOT be set
        assert "interactionModel" not in py


# ---------------------------------------------------------------------------
# Remaining group parameter coverage
# ---------------------------------------------------------------------------


class TestGroupRemainingParams:
    """Cover dyGroup params not yet tested: label, stemPlot, drawPoints,
    pointSize, strokeBorder."""

    def test_group_stroke_border(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyGroup(c("a","b"), strokeBorderWidth=2, strokeBorderColor="green")
            cat(toJSON(strip_js(dg$x$attrs$series), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .group(["a", "b"], stroke_border_width=2, stroke_border_color="green")
            .to_dict()["attrs"]["series"]
        )
        for s in ("a", "b"):
            assert r[s]["strokeBorderWidth"] == py[s]["strokeBorderWidth"] == 2
            assert r[s]["strokeBorderColor"] == py[s]["strokeBorderColor"] == "green"

    def test_group_draw_points_and_size(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyGroup(c("a","b"), drawPoints=TRUE, pointSize=4)
            cat(toJSON(strip_js(dg$x$attrs$series), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .group(["a", "b"], draw_points=True, point_size=4)
            .to_dict()["attrs"]["series"]
        )
        for s in ("a", "b"):
            assert r[s]["drawPoints"] == py[s]["drawPoints"] == True  # noqa: E712
            assert r[s]["pointSize"] == py[s]["pointSize"] == 4

    def test_group_stem_plot(self) -> None:
        """R stemPlot in group uses plotter JS; Python does the same."""
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyGroup(c("a","b"), stemPlot=TRUE)
            cat(toJSON(strip_js(dg$x$attrs$series$a$plotter), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col())
            .group(["a", "b"], stem_plot=True)
            .to_dict()["attrs"]["series"]["a"]["plotter"]
        )
        r_plotter = _normalise_value(r)
        py_plotter = _normalise_value(py)
        assert r_plotter[0] == "__JS__"
        assert py_plotter[0] == "__JS__"


# ---------------------------------------------------------------------------
# Unzoom plugin (trivial — just check plugin exists)
# ---------------------------------------------------------------------------


class TestUnzoomPlugin:
    def test_unzoom_adds_plugin(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyUnzoom()
            cat(toJSON(strip_js(names(dg$x$plugins)), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).unzoom().to_dict()["plugins"]
        assert "Unzoom" in r
        assert any(p["name"] == "Unzoom" for p in py)


# ---------------------------------------------------------------------------
# Constructor-level features (periodicity= override)
# ---------------------------------------------------------------------------


class TestPeriodicityOverride:
    """``dygraph(..., periodicity=)`` constructor override.

    R takes an ``xts::periodicity`` list with a ``$scale`` field; Python
    accepts the scale string directly. Compare the resulting ``x$scale``.
    """

    def test_periodicity_monthly_override(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts, periodicity=list(scale="monthly", label="month"))
            cat(toJSON(strip_js(dg$x$scale), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col(), periodicity="monthly").to_dict()["scale"]
        assert r == "monthly"
        assert py == "monthly"

    def test_periodicity_default_is_autodetected_daily(self) -> None:
        """Without an override, daily-spaced data lands on ``"daily"`` on both sides."""
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts)
            cat(toJSON(strip_js(dg$x$scale), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col()).to_dict()["scale"]
        assert r == "daily"
        assert py == "daily"


# ---------------------------------------------------------------------------
# dyCSS — file → x$css string
# ---------------------------------------------------------------------------


class TestDyCSS:
    def test_css_file_inlined_into_config(self, tmp_path) -> None:
        css_file = tmp_path / "chart.css"
        css_file.write_text(".dygraph-title { color: red; }")
        # Use raw string for the R path so backslashes survive on Windows-ish
        # paths and quotes inside the path are unlikely.
        r_path = str(css_file).replace("\\", "/")
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyCSS("{r_path}")
            cat(toJSON(strip_js(dg$x$css), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).css(css_file).to_dict()["css"]
        # Both should contain the rule contents (R may or may not strip the
        # trailing newline depending on readLines behaviour).
        assert ".dygraph-title" in r
        assert ".dygraph-title" in py


# ---------------------------------------------------------------------------
# dyDependency — manual external asset attachment
# ---------------------------------------------------------------------------


class TestDyDependency:
    """Compare R ``dyDependency(htmlDependency(...))`` with Python ``.dependency()``.

    R stores the htmlDependency object on ``x$dependencies``; Python stores
    a normalised dict with the same fields (``name``, ``version``, ``src``,
    ``script``, ``stylesheet``). The comparison is structural: both sides
    must report the same dependency name, version, and script file
    basename.
    """

    def test_dependency_name_and_version_round_trip(self, tmp_path) -> None:
        js_file = tmp_path / "myplugin.js"
        js_file.write_text("window.__myPlugin = 1;")
        r_dir = str(tmp_path).replace("\\", "/")
        r = _run_r(f"""
            {_R_TS_1COL}
            dep <- htmltools::htmlDependency(
                "MyPlugin", "1.5",
                src = "{r_dir}",
                script = "myplugin.js",
                all_files = FALSE
            )
            dg <- dygraph(ts) %>% dyDependency(dep)
            cat(toJSON(strip_js(list(
                name = dg$dependencies[[1]]$name,
                version = dg$dependencies[[1]]$version,
                script = dg$dependencies[[1]]$script
            )), auto_unbox=TRUE))
        """)
        py_deps = (
            Dygraph(_py_df_1col())
            .dependency("MyPlugin", version="1.5", src=tmp_path, script="myplugin.js")
            .to_dict()["dependencies"]
        )
        assert r["name"] == "MyPlugin"
        assert r["version"] == "1.5"
        assert r["script"] == "myplugin.js"
        assert py_deps[0]["name"] == "MyPlugin"
        assert py_deps[0]["version"] == "1.5"
        # Python stores fully-qualified paths; R stores just the basename
        # relative to src. Compare basenames for parity.
        import os

        assert os.path.basename(py_deps[0]["script"][0]) == "myplugin.js"


# ---------------------------------------------------------------------------
# Plotter family (dyBarChart / dyStackedBarChart / dyMultiColumn / dyCandlestick)
# ---------------------------------------------------------------------------


class TestPlotterFamily:
    """Verify each ``dyX`` plotter family member emits a plotter on both sides.

    Note: R stores the plotter NAME (e.g. ``"BarChart"``) in ``x$plotter``,
    while Python stores a ``Dygraph.Plotters.X`` namespace lookup as a JS
    expression (so the JS resolves it at render time). Both reach the same
    runtime function. The comparison here is structural — both sides must
    have a non-empty ``attrs.plotter`` (R) / ``attrs.plotter`` (Py).
    """

    def test_bar_chart_single_series(self) -> None:
        r = _run_r(f"""
            {_R_TS_1COL}
            dg <- dygraph(ts) %>% dyBarChart()
            cat(toJSON(strip_js(dg$x$attrs$plotter), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_1col()).bar_chart().to_dict()["attrs"].get("plotter")
        # R emits a name string; Python emits a JS namespace lookup.
        assert r and "BarChart" in str(r)
        assert py is not None
        assert "BarChart" in str(py)

    def test_bar_chart_multi_series_falls_back_to_multi_column(self) -> None:
        """R: dyBarChart() switches to MultiColumn when n>1. Python does too."""
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyBarChart()
            cat(toJSON(strip_js(dg$x$attrs$plotter), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col()).bar_chart().to_dict()["attrs"].get("plotter")
        assert "MultiColumn" in str(r)
        assert "MultiColumn" in str(py)

    def test_stacked_bar_chart(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyStackedBarChart()
            cat(toJSON(strip_js(dg$x$attrs$plotter), auto_unbox=TRUE))
        """)
        py = (
            Dygraph(_py_df_2col()).stacked_bar_chart().to_dict()["attrs"].get("plotter")
        )
        assert "StackedBarChart" in str(r)
        assert "StackedBarChart" in str(py)

    def test_multi_column(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% dyMultiColumn()
            cat(toJSON(strip_js(dg$x$attrs$plotter), auto_unbox=TRUE))
        """)
        py = Dygraph(_py_df_2col()).multi_column().to_dict()["attrs"].get("plotter")
        assert "MultiColumn" in str(r)
        assert "MultiColumn" in str(py)

    def test_candlestick(self) -> None:
        # Candlestick wants OHLC columns
        r = _run_r("""
            data <- data.frame(Date=as.Date("2020-01-01") + 0:4,
                               Open=c(1,2,3,4,5), High=c(2,3,4,5,6),
                               Low=c(0.5,1.5,2.5,3.5,4.5), Close=c(1.5,2.5,3.5,4.5,5.5))
            ts <- xts(data[,c("Open","High","Low","Close")], order.by=data$Date)
            dg <- dygraph(ts) %>% dyCandlestick()
            cat(toJSON(strip_js(dg$x$attrs$plotter), auto_unbox=TRUE))
        """)
        ohlc = pd.DataFrame(
            {
                "Open": [1, 2, 3, 4, 5],
                "High": [2, 3, 4, 5, 6],
                "Low": [0.5, 1.5, 2.5, 3.5, 4.5],
                "Close": [1.5, 2.5, 3.5, 4.5, 5.5],
            },
            index=_DATES,
        )
        py = Dygraph(ohlc).candlestick().to_dict()["attrs"].get("plotter")
        assert "Candlestick" in str(r)
        assert "Candlestick" in str(py)


# ---------------------------------------------------------------------------
# Series-level plotter family (dyBarSeries / dyStemSeries / dyShadow /
# dyFilledLine / dyErrorFill)
# ---------------------------------------------------------------------------


class TestSeriesPlotterFamily:
    """Each series-level plotter sets ``attrs$series$<name>$plotter``.

    R inlines the plotter JS source as the value; Python stores a short
    name reference and injects the JS source separately via ``extraJs``.
    The comparison is structural: assert the named series has a plotter
    set on both sides.
    """

    def _r_series_plotter_present(self, dy_func: str, series: str) -> bool:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>% {dy_func}("{series}")
            has <- !is.null(dg$x$attrs$series[["{series}"]]$plotter)
            cat(toJSON(has, auto_unbox=TRUE))
        """)
        return bool(r)

    def _py_series_plotter_present(self, method_name: str, series: str) -> bool:
        df = _py_df_2col()
        dg = getattr(Dygraph(df), method_name)(series)
        series_attrs = dg.to_dict()["attrs"].get("series", {})
        return "plotter" in series_attrs.get(series, {})

    def test_bar_series(self) -> None:
        assert self._r_series_plotter_present("dyBarSeries", "a")
        assert self._py_series_plotter_present("bar_series", "a")

    def test_stem_series(self) -> None:
        assert self._r_series_plotter_present("dyStemSeries", "a")
        assert self._py_series_plotter_present("stem_series", "a")

    def test_shadow(self) -> None:
        assert self._r_series_plotter_present("dyShadow", "a")
        assert self._py_series_plotter_present("shadow", "a")

    def test_filled_line(self) -> None:
        assert self._r_series_plotter_present("dyFilledLine", "a")
        assert self._py_series_plotter_present("filled_line", "a")

    def test_error_fill(self) -> None:
        assert self._r_series_plotter_present("dyErrorFill", "a")
        assert self._py_series_plotter_present("error_fill", "a")


# ---------------------------------------------------------------------------
# Strict full-JSON diff
# ---------------------------------------------------------------------------

# Known structural differences between R and Python that are intentional:
_STRICT_SKIP_TOP = {
    "scale",  # R emits "daily"/"monthly", Python doesn't (unused by JS)
    "fixedtz",  # R-only xts metadata
    "tzone",  # R-only xts metadata
}
_STRICT_SKIP_ATTRS = {
    "labels",  # labels[0] differs: R="day", Python="Date" (index name)
    "colors",  # R may reorder on series rename
    "mobileDisableYTouch",  # R always emits, Python only when non-default
    "highlightSeriesOpts",  # R emits [], Python omits
}


def _deep_normalise(obj: Any) -> Any:
    """Recursively normalise for comparison: strip whitespace in strings,
    convert JS markers, normalise date formats, sort dicts."""
    if isinstance(obj, str):
        s = obj.strip()
        if s.startswith("__JS__:"):
            return ("__JS__", s[7:])
        # Normalise ISO date format: remove .000 milliseconds
        if "T" in s and s.endswith("Z") and ".000Z" in s:
            s = s.replace(".000Z", "Z")
        return s
    if hasattr(obj, "code"):  # Python JS object
        return ("__JS__", obj.code)
    if isinstance(obj, dict):
        # Remove None values (Python emits "group": null, R omits it)
        return {k: _deep_normalise(v) for k, v in sorted(obj.items()) if v is not None}
    if isinstance(obj, list):
        return [_deep_normalise(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 10)
    return obj


def _diff_dicts(
    r_obj: Any, py_obj: Any, path: str = "", skip: set[str] | None = None
) -> list[str]:
    """Recursively diff two normalised structures, returning differences."""
    diffs: list[str] = []
    skip = skip or set()

    if isinstance(r_obj, dict) and isinstance(py_obj, dict):
        all_keys = set(r_obj) | set(py_obj)
        for key in sorted(all_keys):
            if key in skip:
                continue
            kpath = f"{path}.{key}" if path else key
            if key not in r_obj:
                diffs.append(f"{kpath}: PYTHON-ONLY (={py_obj[key]!r})")
            elif key not in py_obj:
                diffs.append(f"{kpath}: R-ONLY (={r_obj[key]!r})")
            else:
                diffs.extend(_diff_dicts(r_obj[key], py_obj[key], kpath))
    elif isinstance(r_obj, list) and isinstance(py_obj, list):
        if len(r_obj) != len(py_obj):
            diffs.append(f"{path}: len R={len(r_obj)} != Py={len(py_obj)}")
        for i, (rv, pv) in enumerate(zip(r_obj, py_obj, strict=False)):
            diffs.extend(_diff_dicts(rv, pv, f"{path}[{i}]"))
    elif r_obj != py_obj:
        diffs.append(f"{path}: R={r_obj!r} != Py={py_obj!r}")

    return diffs


class TestStrictJsonDiff:
    """Strict full-JSON comparison — flags ALL differences, not just
    cherry-picked keys. This catches unexpected extra/missing keys."""

    @staticmethod
    def _prepare(r_data: dict, py_data: dict) -> tuple[dict, dict]:
        """Apply standard normalisations and skip-list to both sides."""
        r_norm = _deep_normalise(r_data)
        py_norm = _deep_normalise(py_data)
        for key in _STRICT_SKIP_TOP:
            r_norm.pop(key, None)
        for key in _STRICT_SKIP_ATTRS:
            r_norm.get("attrs", {}).pop(key, None)
            py_norm.get("attrs", {}).pop(key, None)
        # Plugins have different container format (R: dict, Python: list)
        r_norm.pop("plugins", None)
        py_norm.pop("plugins", None)
        # Python-only keys
        py_norm.pop("extraJs", None)
        return r_norm, py_norm

    def test_strict_basic_chart(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts, main="Test")
            cat(toJSON(strip_js(dg$x), auto_unbox=TRUE))
        """)
        py = _python_config(Dygraph(_py_df_2col(), title="Test"))
        r_norm, py_norm = self._prepare(r, py)
        diffs = _diff_dicts(r_norm, py_norm)
        assert diffs == [], "Strict diff found differences:\n" + "\n".join(diffs)

    def test_strict_with_options(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts) %>%
                dyOptions(fillGraph=TRUE, strokeWidth=2, drawPoints=TRUE)
            cat(toJSON(strip_js(dg$x), auto_unbox=TRUE))
        """)
        py = _python_config(
            Dygraph(_py_df_2col()).options(
                fill_graph=True, stroke_width=2, draw_points=True
            )
        )
        r_norm, py_norm = self._prepare(r, py)
        diffs = _diff_dicts(r_norm, py_norm)
        assert diffs == [], "Strict diff found differences:\n" + "\n".join(diffs)

    def test_strict_full_pipeline(self) -> None:
        r = _run_r(f"""
            {_R_TS_2COL}
            dg <- dygraph(ts, main="Full") %>%
                dyOptions(fillGraph=TRUE, strokeWidth=2) %>%
                dySeries("b", strokePattern="dashed") %>%
                dyAxis("y", label="Y") %>%
                dyLegend(show="always", width=200) %>%
                dyHighlight(highlightCircleSize=4) %>%
                dyRoller(rollPeriod=2) %>%
                dyAnnotation("2020-01-03", text="X", tooltip="Note") %>%
                dyEvent("2020-01-02", label="E") %>%
                dyShading(from="2020-01-01", to="2020-01-02") %>%
                dyLimit(2.5, label="L")
            cat(toJSON(strip_js(dg$x), auto_unbox=TRUE))
        """)
        py = _python_config(
            Dygraph(_py_df_2col(), title="Full")
            .options(fill_graph=True, stroke_width=2)
            .series("b", stroke_pattern="dashed")
            .axis("y", label="Y")
            .legend(show="always", width=200)
            .highlight(circle_size=4)
            .roller(roll_period=2)
            .annotation("2020-01-03", text="X", tooltip="Note")
            .event("2020-01-02", label="E")
            .shading("2020-01-01", "2020-01-02")
            .limit(2.5, label="L")
        )
        r_norm, py_norm = self._prepare(r, py)
        diffs = _diff_dicts(r_norm, py_norm)
        assert diffs == [], "Strict diff found differences:\n" + "\n".join(diffs)
