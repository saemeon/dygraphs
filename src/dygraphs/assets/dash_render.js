/* dygraphs Dash adapter — Dash-specific shim.
 *
 * Single entry point: window.dygraphsDash.render(setup, config).
 *
 *   setup = {
 *       containerId, chartDivId, graphId, height, modebar,
 *       cdnCssUrl, cdnJsUrl, modebarCss, modebarHtml,
 *       captureJs   // raw JS source for the multi-canvas merge IIFE
 *   }
 *   config = serialised dygraph config from the chart's dcc.Store
 *
 * This file is *thin*: all actual chart-rendering logic lives in
 * ``render_core.js`` (``window.dygraphs``). This shim only handles the
 * Dash-specific layer:
 *
 *   - lazy-load dygraph.css / dygraph.min.js from the CDN
 *   - build the chart scaffold with the Plotly-style hover modebar
 *   - install the PNG-capture and reset-zoom button handlers
 *
 * The IIFE wrapper guards against double-init: multiple Dash per-chart
 * callbacks inline this asset; only the first populates
 * ``window.dygraphsDash``.
 */
(function (global) {
    if (global.dygraphsDash) return;

    function loadModebarCssOnce(css) {
        if (document.getElementById('dy-modebar-css')) return;
        var style = document.createElement('style');
        style.id = 'dy-modebar-css';
        style.textContent = css;
        document.head.appendChild(style);
    }

    function safeJsId(s) {
        return s.replace(/-/g, '_').replace(/\./g, '_');
    }

    function installCaptureFn(setup) {
        var jsId = safeJsId(setup.graphId);
        // Build the multi-canvas capture IIFE from the source string passed
        // in via setup.captureJs (defined Python-side as
        // dygraphs.dash.capture.MULTI_CANVAS_CAPTURE_JS, the same source
        // used by the dash-capture wizard strategy).
        var captureFn = eval('(' + setup.captureJs + ')');
        global['__dyCap_' + jsId] = function () {
            var chartEl = document.getElementById(setup.chartDivId);
            if (!chartEl) return;
            var dataUri = captureFn(chartEl, 'png', true, false);
            var a = document.createElement('a');
            a.download = setup.graphId + '.png';
            a.href = dataUri;
            a.click();
        };
    }

    function installResetFn(setup, container) {
        var jsId = safeJsId(setup.graphId);
        global['__dyReset_' + jsId] = function () {
            if (container._dygraphInstance) {
                container._dygraphInstance.resetZoom();
            }
        };
    }

    function buildDashScaffold(setup) {
        // Scaffold builder passed into window.dygraphs.render: wraps the
        // chart ``<div>`` in a hover-enabled modebar container and
        // injects the per-chart modebar HTML (camera + reset buttons).
        return function (container) {
            container.innerHTML =
                '<div class="dy-modebar-wrap" style="position:relative">'
                + '<div id="' + setup.chartDivId
                + '" style="width:100%;height:' + setup.height + 'px"></div>'
                + (setup.modebar ? setup.modebarHtml : '')
                + '</div>';
            return document.getElementById(setup.chartDivId);
        };
    }

    function render(setup, config) {
        if (!config) return;

        global.dygraphs.loadCssOnce('dygraph-css', setup.cdnCssUrl);
        if (setup.modebar) loadModebarCssOnce(setup.modebarCss);

        global.dygraphs.loadDygraphLibOnce(setup.cdnJsUrl, function () {
            var container = document.getElementById(setup.containerId);
            if (!container) return;

            global.dygraphs.render(container, config, {
                scaffoldBuilder: buildDashScaffold(setup)
            });

            installCaptureFn(setup);
            installResetFn(setup, container);
        });
    }

    global.dygraphsDash = {render: render};
})(window);
