"""Tests targeting coverage gaps identified during R-parity audit.

Covers: axis options, options branches, group options, annotation fields,
range selector edge cases, CSS, to_html variants, point shape serialization,
JSON edge cases, and ribbon plugin options.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from dygraphs import Dygraph
from dygraphs.utils import JS


def _df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    return pd.DataFrame({"a": [1, 2, 3, 4, 5], "b": [5, 4, 3, 2, 1]}, index=idx)


def _num_df() -> dict[str, list[int]]:
    return {"x": [1, 2, 3, 4, 5], "y": [10, 20, 30, 40, 50]}


# ---------------------------------------------------------------------------
# Point shape serialization (Fix 1 from audit)
# ---------------------------------------------------------------------------


class TestPointShapeSerialization:
    def test_global_shape_is_string(self) -> None:
        d = Dygraph(_df()).options(point_shape="triangle")
        assert d.to_dict()["pointShape"] == "triangle"

    def test_per_series_shape_is_dict(self) -> None:
        d = Dygraph(_df()).series("a", point_shape="star")
        ps = d.to_dict()["pointShape"]
        assert isinstance(ps, dict)
        assert ps["a"] == "star"

    def test_global_plus_per_series_drops_global(self) -> None:
        d = (
            Dygraph(_df())
            .options(point_shape="triangle")
            .series("a", point_shape="star")
        )
        ps = d.to_dict()["pointShape"]
        assert isinstance(ps, dict)
        assert "__global__" not in ps
        assert ps["a"] == "star"

    def test_no_shapes_omits_key(self) -> None:
        d = Dygraph(_df())
        assert "pointShape" not in d.to_dict()


# ---------------------------------------------------------------------------
# Axis options (uncovered branches)
# ---------------------------------------------------------------------------


class TestAxisOptionsBranches:
    def test_logscale_x_axis(self) -> None:
        d = Dygraph(_num_df()).axis("x", logscale=True)
        assert d.to_dict()["attrs"]["axes"]["x"]["logscale"] is True

    def test_logscale_y_axis(self) -> None:
        d = Dygraph(_num_df()).axis("y", logscale=True)
        assert d.to_dict()["attrs"]["logscale"] is True

    def test_ticker(self) -> None:
        d = Dygraph(_df()).axis("x", ticker="function(){return [];}")
        t = d.to_dict()["attrs"]["axes"]["x"]["ticker"]
        assert isinstance(t, JS)

    def test_range_pad(self) -> None:
        d = Dygraph(_df()).axis("y", range_pad=20)
        assert d.to_dict()["attrs"]["yRangePad"] == 20

    def test_label_width_and_height(self) -> None:
        d = Dygraph(_df()).axis("x", label_width=100, label_height=30)
        cfg = d.to_dict()["attrs"]
        assert cfg["xLabelWidth"] == 100
        assert cfg["xLabelHeight"] == 30

    def test_axis_line_color_and_width(self) -> None:
        d = Dygraph(_df()).axis("y", axis_line_color="red", axis_line_width=2.0)
        ax = d.to_dict()["attrs"]["axes"]["y"]
        assert ax["axisLineColor"] == "red"
        assert ax["axisLineWidth"] == 2.0

    def test_axis_label_color_font_size_width(self) -> None:
        d = Dygraph(_df()).axis(
            "y", axis_label_color="blue", axis_label_font_size=16, axis_label_width=80
        )
        ax = d.to_dict()["attrs"]["axes"]["y"]
        assert ax["axisLabelColor"] == "blue"
        assert ax["axisLabelFontSize"] == 16
        assert ax["axisLabelWidth"] == 80

    def test_axis_label_formatter(self) -> None:
        d = Dygraph(_df()).axis("x", axis_label_formatter="function(v){return v;}")
        f = d.to_dict()["attrs"]["axes"]["x"]["axisLabelFormatter"]
        assert isinstance(f, JS)

    def test_value_formatter(self) -> None:
        d = Dygraph(_df()).axis(
            "y", value_formatter="function(v){return v.toFixed(1);}"
        )
        f = d.to_dict()["attrs"]["axes"]["y"]["valueFormatter"]
        assert isinstance(f, JS)

    def test_grid_line_color_and_width(self) -> None:
        d = Dygraph(_df()).axis("y", grid_line_color="#ccc", grid_line_width=0.5)
        ax = d.to_dict()["attrs"]["axes"]["y"]
        assert ax["gridLineColor"] == "#ccc"
        assert ax["gridLineWidth"] == 0.5


# ---------------------------------------------------------------------------
# Options branches (uncovered)
# ---------------------------------------------------------------------------


class TestOptionsBranches:
    def test_error_bars(self) -> None:
        d = Dygraph(_num_df()).options(error_bars=True)
        assert d.to_dict()["attrs"]["errorBars"] is True

    def test_custom_bars(self) -> None:
        d = Dygraph(_num_df()).options(custom_bars=True)
        assert d.to_dict()["attrs"]["customBars"] is True

    def test_sigma(self) -> None:
        d = Dygraph(_num_df()).options(sigma=2.0)
        assert d.to_dict()["attrs"]["sigma"] == 2.0

    def test_fractions_and_wilson_interval(self) -> None:
        d = Dygraph(_num_df()).options(fractions=True, wilson_interval=False)
        cfg = d.to_dict()["attrs"]
        assert cfg["fractions"] is True
        assert cfg["wilsonInterval"] is False

    def test_visibility(self) -> None:
        d = Dygraph(_df()).options(visibility=[True, False])
        assert d.to_dict()["attrs"]["visibility"] == [True, False]

    def test_legend_formatter(self) -> None:
        d = Dygraph(_df()).options(legend_formatter="function(data){return '';}")
        f = d.to_dict()["attrs"]["legendFormatter"]
        assert isinstance(f, JS)

    def test_range_selector_styling(self) -> None:
        d = Dygraph(_df()).options(
            range_selector_plot_line_width=2.0,
            range_selector_plot_fill_gradient_color="#abc",
            range_selector_background_line_width=1.5,
            range_selector_background_stroke_color="#def",
            range_selector_foreground_stroke_color="#123",
            range_selector_foreground_line_width=3.0,
            range_selector_alpha=0.8,
        )
        cfg = d.to_dict()["attrs"]
        assert cfg["rangeSelectorPlotLineWidth"] == 2.0
        assert cfg["rangeSelectorPlotFillGradientColor"] == "#abc"
        assert cfg["rangeSelectorBackgroundLineWidth"] == 1.5
        assert cfg["rangeSelectorBackgroundStrokeColor"] == "#def"
        assert cfg["rangeSelectorForegroundStrokeColor"] == "#123"
        assert cfg["rangeSelectorForegroundLineWidth"] == 3.0
        assert cfg["rangeSelectorAlpha"] == 0.8

    def test_grid_line_pattern(self) -> None:
        d = Dygraph(_df()).options(grid_line_pattern=[5, 5])
        assert d.to_dict()["attrs"]["gridLinePattern"] == [5, 5]

    def test_resizable(self) -> None:
        d = Dygraph(_df()).options(resizable="both")
        assert d.to_dict()["attrs"]["resizable"] == "both"

    def test_pixel_ratio(self) -> None:
        d = Dygraph(_df()).options(pixel_ratio=2.0)
        assert d.to_dict()["attrs"]["pixelRatio"] == 2.0

    def test_stacked_graph_nan_fill(self) -> None:
        d = Dygraph(_df()).options(stacked_graph_nan_fill="none")
        assert d.to_dict()["attrs"]["stackedGraphNaNFill"] == "none"

    def test_animate_background_fade_false(self) -> None:
        d = Dygraph(_df()).options(animate_background_fade=False)
        assert d.to_dict()["attrs"]["animateBackgroundFade"] is False

    def test_x_label_height(self) -> None:
        d = Dygraph(_df()).options(x_label_height=25)
        assert d.to_dict()["attrs"]["xLabelHeight"] == 25

    def test_y_label_width(self) -> None:
        d = Dygraph(_df()).options(y_label_width=60)
        assert d.to_dict()["attrs"]["yLabelWidth"] == 60

    def test_legend_follow_offsets(self) -> None:
        d = Dygraph(_df()).options(legend_follow_offset_x=10, legend_follow_offset_y=20)
        cfg = d.to_dict()["attrs"]
        assert cfg["legendFollowOffsetX"] == 10
        assert cfg["legendFollowOffsetY"] == 20

    def test_range_selector_veil_colour(self) -> None:
        d = Dygraph(_df()).options(range_selector_veil_colour="rgba(0,0,0,0.3)")
        assert d.to_dict()["attrs"]["rangeSelectorVeilColour"] == "rgba(0,0,0,0.3)"

    def test_delimiter(self) -> None:
        d = Dygraph(_df()).options(delimiter="\t")
        assert d.to_dict()["attrs"]["delimiter"] == "\t"

    def test_x_value_parser(self) -> None:
        d = Dygraph(_df()).options(x_value_parser="function(x){return parseFloat(x);}")
        assert isinstance(d.to_dict()["attrs"]["xValueParser"], JS)

    def test_display_annotations(self) -> None:
        d = Dygraph(_df()).options(display_annotations=True)
        assert d.to_dict()["attrs"]["displayAnnotations"] is True

    def test_data_handler_option(self) -> None:
        d = Dygraph(_df()).options(data_handler="function(){}")
        assert isinstance(d.to_dict()["attrs"]["dataHandler"], JS)

    def test_title_height(self) -> None:
        d = Dygraph(_df()).options(title_height=30)
        assert d.to_dict()["attrs"]["titleHeight"] == 30

    def test_sig_figs(self) -> None:
        d = Dygraph(_df()).options(sig_figs=4)
        assert d.to_dict()["attrs"]["sigFigs"] == 4

    def test_pan_edge_fraction(self) -> None:
        d = Dygraph(_df()).options(pan_edge_fraction=0.1)
        assert d.to_dict()["attrs"]["panEdgeFraction"] == 0.1

    def test_stroke_border_width(self) -> None:
        d = Dygraph(_df()).options(stroke_border_width=2.0)
        assert d.to_dict()["attrs"]["strokeBorderWidth"] == 2.0


# ---------------------------------------------------------------------------
# Group options (uncovered branches)
# ---------------------------------------------------------------------------


class TestGroupOptionsBranches:
    def test_group_with_colors(self) -> None:
        d = Dygraph(_df()).group(["a", "b"], color=["red", "blue"])
        cfg = d.to_dict()["attrs"]
        assert cfg["colors"][0] == "red"
        assert cfg["colors"][1] == "blue"

    def test_group_with_point_shapes(self) -> None:
        d = Dygraph(_df()).group(["a", "b"], point_shape=["star", "triangle"])
        ps = d.to_dict()["pointShape"]
        assert ps["a"] == "star"
        assert ps["b"] == "triangle"

    def test_group_step_plot(self) -> None:
        d = Dygraph(_df()).group(["a", "b"], step_plot=True)
        cfg = d.to_dict()["attrs"]
        assert cfg["series"]["a"]["stepPlot"] is True
        assert cfg["series"]["b"]["stepPlot"] is True

    def test_group_fill_graph(self) -> None:
        d = Dygraph(_df()).group(["a", "b"], fill_graph=True)
        assert d.to_dict()["attrs"]["series"]["a"]["fillGraph"] is True

    def test_group_draw_points(self) -> None:
        d = Dygraph(_df()).group(["a", "b"], draw_points=True, point_size=3.0)
        s = d.to_dict()["attrs"]["series"]["a"]
        assert s["drawPoints"] is True
        assert s["pointSize"] == 3.0

    def test_group_stroke_options(self) -> None:
        d = Dygraph(_df()).group(
            ["a", "b"],
            stroke_width=2.0,
            stroke_pattern="dotted",
            stroke_border_width=1.0,
            stroke_border_color="gray",
        )
        s = d.to_dict()["attrs"]["series"]["a"]
        assert s["strokeWidth"] == 2.0
        assert s["strokePattern"] == [2, 2]
        assert s["strokeBorderWidth"] == 1.0
        assert s["strokeBorderColor"] == "gray"

    def test_group_single_series_delegates(self) -> None:
        d = Dygraph(_df()).group(["a"], color=["red"])
        cfg = d.to_dict()["attrs"]
        assert cfg["colors"][0] == "red"

    def test_group_invalid_series(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            Dygraph(_df()).group(["a", "nonexistent"])


# ---------------------------------------------------------------------------
# Annotation optional fields (uncovered)
# ---------------------------------------------------------------------------


class TestAnnotationFields:
    def test_annotation_width_height(self) -> None:
        d = Dygraph(_df()).annotation("2020-01-03", "A", width=30, height=20)
        ann = d.to_dict()["annotations"][0]
        assert ann["width"] == 30
        assert ann["height"] == 20

    def test_annotation_css_class(self) -> None:
        d = Dygraph(_df()).annotation("2020-01-03", "A", css_class="my-ann")
        assert d.to_dict()["annotations"][0]["cssClass"] == "my-ann"

    def test_annotation_tick_options(self) -> None:
        d = Dygraph(_df()).annotation(
            "2020-01-03", "A", tick_height=20, tick_color="red", tick_width=3
        )
        ann = d.to_dict()["annotations"][0]
        assert ann["tickHeight"] == 20
        assert ann["tickColor"] == "red"
        assert ann["tickWidth"] == 3

    def test_annotation_icon(self) -> None:
        d = Dygraph(_df()).annotation("2020-01-03", "A", icon="icon.png")
        assert d.to_dict()["annotations"][0]["icon"] == "icon.png"

    def test_annotation_handlers(self) -> None:
        d = Dygraph(_df()).annotation(
            "2020-01-03",
            "A",
            click_handler="function(){}",
            mouse_over_handler="function(){}",
            mouse_out_handler="function(){}",
            dbl_click_handler="function(){}",
        )
        ann = d.to_dict()["annotations"][0]
        assert isinstance(ann["clickHandler"], JS)
        assert isinstance(ann["mouseOverHandler"], JS)
        assert isinstance(ann["mouseOutHandler"], JS)
        assert isinstance(ann["dblClickHandler"], JS)


# ---------------------------------------------------------------------------
# Range selector edge cases
# ---------------------------------------------------------------------------


class TestRangeSelectorEdgeCases:
    def test_date_window_numeric(self) -> None:
        d = Dygraph(_num_df()).range_selector(date_window=(1, 4))
        dw = d.to_dict()["attrs"]["dateWindow"]
        assert dw == [1, 4]

    def test_retain_date_window(self) -> None:
        d = Dygraph(_df()).range_selector(retain_date_window=True)
        assert d.to_dict()["attrs"]["retainDateWindow"] is True

    def test_date_window_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot convert"):
            Dygraph(_df()).range_selector(date_window=("not-a-date", "also-bad"))


# ---------------------------------------------------------------------------
# CSS loading
# ---------------------------------------------------------------------------


class TestCssLoading:
    def test_css_file(self, tmp_path: Path) -> None:
        css_file = tmp_path / "custom.css"
        css_file.write_text(".dygraph-legend { font-size: 14px; }")
        d = Dygraph(_df()).css(css_file)
        cfg = d.to_dict()
        assert cfg["css"] == ".dygraph-legend { font-size: 14px; }"

    def test_css_in_html(self, tmp_path: Path) -> None:
        css_file = tmp_path / "custom.css"
        css_file.write_text(".dygraph-legend { color: red; }")
        html = Dygraph(_df()).css(css_file).to_html()
        assert "config.css" in html or ".dygraph-legend" in html


# ---------------------------------------------------------------------------
# to_html variants
# ---------------------------------------------------------------------------


class TestToHtmlVariants:
    def test_shapes_js_injected(self) -> None:
        html = Dygraph(_df()).options(point_shape="star").to_html()
        assert "Dygraph.Circles" in html

    def test_extra_js_injected(self) -> None:
        html = Dygraph(_df()).bar_chart().to_html()
        # Should have extra <script> blocks for the plotter JS
        assert html.count("<script>") >= 2

    def test_mobile_touch_in_html(self) -> None:
        html = Dygraph(_df()).to_html()
        assert "mobileDisableYTouch" in html

    def test_date_normalization_in_html(self) -> None:
        html = Dygraph(_df()).to_html()
        assert "normalizeDateValue" in html or "getTimezoneOffset" in html

    def test_disable_zoom_in_html(self) -> None:
        html = Dygraph(_df()).options(disable_zoom=True).to_html()
        assert "nonInteractiveModel" in html

    def test_legend_auto_in_html(self) -> None:
        html = Dygraph(_df()).to_html()
        assert "legend === 'auto'" in html

    def test_group_sync_in_html(self) -> None:
        html = Dygraph(_df(), group="grp1").to_html()
        assert "__dyGroups" in html
        assert "blockRedraw" in html

    def test_no_group_no_sync(self) -> None:
        html = Dygraph(_df()).to_html()
        # Group sync JS is still in the template but conditional
        assert "config.group" in html

    def test_plugins_in_html(self) -> None:
        html = Dygraph(_df()).unzoom().to_html()
        assert "Dygraph.Plugins" in html

    def test_css_injection_in_html(self, tmp_path: Path) -> None:
        css_file = tmp_path / "test.css"
        css_file.write_text("body { margin: 0; }")
        html = Dygraph(_df()).css(css_file).to_html()
        assert "config.css" in html


# ---------------------------------------------------------------------------
# Ribbon plugin with parser
# ---------------------------------------------------------------------------


class TestRibbonWithParser:
    def test_ribbon_with_parser(self) -> None:
        d = Dygraph(_df()).ribbon(parser="function(v){return v;}")
        p = d.to_dict()["plugins"][0]
        assert p["name"] == "Ribbon"
        assert isinstance(p["options"]["parser"], JS)


# ---------------------------------------------------------------------------
# to_dict / to_json edge cases
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_extra_js_deduplication(self) -> None:
        d = Dygraph(_df())
        d._extra_js = ["var x=1;", "var x=1;", "var y=2;"]
        cfg = d.to_dict()
        assert cfg["extraJs"] == ["var x=1;", "var y=2;"]

    def test_to_json_produces_valid_json_without_js(self) -> None:
        d = Dygraph(_num_df())
        raw = d.to_json()
        parsed = json.loads(raw)
        assert "attrs" in parsed
        assert "data" in parsed

    def test_to_json_unwraps_js_markers(self) -> None:
        d = Dygraph(_df()).callbacks(click="function(e){}")
        raw = d.to_json()
        # JS markers should be unwrapped: no __JS__ in output
        assert "__JS__" not in raw
        assert "function(e){}" in raw

    def test_to_json_non_serializable_raises(self) -> None:
        d = Dygraph(_num_df())
        d._attrs["bad"] = object()
        with pytest.raises(TypeError, match="not JSON serializable"):
            d.to_json()

    def test_css_omitted_when_none(self) -> None:
        d = Dygraph(_df())
        assert "css" not in d.to_dict()


# ---------------------------------------------------------------------------
# Series options (uncovered branches)
# ---------------------------------------------------------------------------


class TestSeriesOptionsBranches:
    def test_series_fill_graph(self) -> None:
        d = Dygraph(_df()).series("a", fill_graph=True)
        assert d.to_dict()["attrs"]["series"]["a"]["fillGraph"] is True

    def test_series_draw_points(self) -> None:
        d = Dygraph(_df()).series("a", draw_points=True, point_size=4.0)
        s = d.to_dict()["attrs"]["series"]["a"]
        assert s["drawPoints"] is True
        assert s["pointSize"] == 4.0

    def test_series_stroke_border(self) -> None:
        d = Dygraph(_df()).series(
            "a", stroke_border_width=2.0, stroke_border_color="gray"
        )
        s = d.to_dict()["attrs"]["series"]["a"]
        assert s["strokeBorderWidth"] == 2.0
        assert s["strokeBorderColor"] == "gray"

    def test_series_highlight_circle_size(self) -> None:
        d = Dygraph(_df()).series("a", highlight_circle_size=8)
        assert d.to_dict()["attrs"]["series"]["a"]["highlightCircleSize"] == 8

    def test_series_show_in_range_selector(self) -> None:
        d = Dygraph(_df()).series("a", show_in_range_selector=True)
        assert d.to_dict()["attrs"]["series"]["a"]["showInRangeSelector"] is True

    def test_series_stem_plot(self) -> None:
        d = Dygraph(_df()).series("a", stem_plot=True)
        s = d.to_dict()["attrs"]["series"]["a"]
        assert isinstance(s["plotter"], JS)
        assert "stemPlotter" in s["plotter"].code

    def test_series_stem_plot_conflicts_with_plotter(self) -> None:
        with pytest.raises(ValueError, match="stem_plot"):
            Dygraph(_df()).series("a", stem_plot=True, plotter="function(){}")


# ---------------------------------------------------------------------------
# Legend option: "never" (special handling)
# ---------------------------------------------------------------------------


class TestLegendNever:
    def test_legend_never_disables_labels(self) -> None:
        d = Dygraph(_df()).legend(show="never")
        cfg = d.to_dict()["attrs"]
        assert cfg["showLabelsOnHighlight"] is False


# ---------------------------------------------------------------------------
# Highlight options
# ---------------------------------------------------------------------------


class TestHighlightOptions:
    def test_highlight_background_color(self) -> None:
        d = Dygraph(_df()).highlight(series_background_color="yellow")
        assert d.to_dict()["attrs"]["highlightSeriesBackgroundColor"] == "yellow"

    def test_highlight_series_opts(self) -> None:
        d = Dygraph(_df()).highlight(series_opts={"strokeWidth": 3})
        assert d.to_dict()["attrs"]["highlightSeriesOpts"] == {"strokeWidth": 3}


# ---------------------------------------------------------------------------
# Callbacks (remaining types)
# ---------------------------------------------------------------------------


class TestCallbacksBranches:
    def test_all_callback_types(self) -> None:
        d = Dygraph(_df()).callbacks(
            click="function(){}",
            draw="function(){}",
            highlight="function(){}",
            point_click="function(){}",
            underlay="function(){}",
            unhighlight="function(){}",
            zoom="function(){}",
            draw_highlight_point="function(){}",
            draw_point="function(){}",
            annotation_click="function(){}",
            annotation_mouse_over="function(){}",
            annotation_mouse_out="function(){}",
            annotation_dbl_click="function(){}",
        )
        cfg = d.to_dict()["attrs"]
        assert isinstance(cfg["clickCallback"], JS)
        assert isinstance(cfg["drawCallback"], JS)
        assert isinstance(cfg["highlightCallback"], JS)
        assert isinstance(cfg["pointClickCallback"], JS)
        assert isinstance(cfg["underlayCallback"], JS)
        assert isinstance(cfg["unhighlightCallback"], JS)
        assert isinstance(cfg["zoomCallback"], JS)
        assert isinstance(cfg["drawHighlightPointCallback"], JS)
        assert isinstance(cfg["drawPointCallback"], JS)
        assert isinstance(cfg["annotationClickHandler"], JS)
        assert isinstance(cfg["annotationMouseOverHandler"], JS)
        assert isinstance(cfg["annotationMouseOutHandler"], JS)
        assert isinstance(cfg["annotationDblClickHandler"], JS)
