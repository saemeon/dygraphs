/* dygraphs Dash adapter — clientside renderer.
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
 * The IIFE wrapper guards against double-init: if the asset is inlined
 * by multiple Dash clientside callbacks (one per chart), only the first
 * one populates window.dygraphsDash; subsequent inlines are no-ops.
 */
(function (global) {
    if (global.dygraphsDash) return;

    // ---------------------------------------------------------------------
    // One-time CSS / JS loading
    // ---------------------------------------------------------------------

    function loadCssOnce(url) {
        if (document.getElementById('dygraph-css')) return;
        var link = document.createElement('link');
        link.id = 'dygraph-css';
        link.rel = 'stylesheet';
        link.href = url;
        document.head.appendChild(link);
    }

    function loadModebarCssOnce(css) {
        if (document.getElementById('dy-modebar-css')) return;
        var style = document.createElement('style');
        style.id = 'dy-modebar-css';
        style.textContent = css;
        document.head.appendChild(style);
    }

    function loadDygraphJsOnce(url, onReady) {
        if (typeof Dygraph !== 'undefined') {
            onReady();
            return;
        }
        var s = document.createElement('script');
        s.src = url;
        s.onload = onReady;
        document.head.appendChild(s);
    }

    // ---------------------------------------------------------------------
    // __JS__:<code>:__JS__ marker resolution (recursive)
    //
    // The Python serialiser wraps JS callback strings as
    //   "__JS__:<code>:__JS__"
    // Walk the option tree and replace every such string with the eval'd
    // value. Failures are logged but non-fatal.
    // ---------------------------------------------------------------------

    function processJsMarkers(obj) {
        if (!obj || typeof obj !== 'object') return obj;
        for (var key in obj) {
            var val = obj[key];
            if (typeof val === 'string' && val.indexOf('__JS__:') === 0) {
                var code = val.slice(7, -7);
                try {
                    obj[key] = eval('(' + code + ')');
                } catch (e) {
                    console.warn('dygraphs: eval failed for "' + key + '":', e);
                }
            } else if (typeof val === 'object') {
                processJsMarkers(val);
            }
        }
        return obj;
    }

    // ---------------------------------------------------------------------
    // Group sync (zoom + highlight)
    //
    // Charts sharing the same `config.group` keep their dateWindow and
    // hover row in lockstep via a global registry on window.__dyGroups.
    // ---------------------------------------------------------------------

    function ensureGroupRegistry() {
        if (!global.__dyGroups) global.__dyGroups = {};
        return global.__dyGroups;
    }

    function attachZoomSync(opts, container, graphId, group) {
        var groups = ensureGroupRegistry();

        function broadcastZoom(dw) {
            if (container._suppressZoom) {
                container._suppressZoom = false;
                container._lastBroadcastDW = dw;
                return;
            }
            var prev = container._lastBroadcastDW;
            if (prev && prev[0] === dw[0] && prev[1] === dw[1]) return;
            clearTimeout(container._zoomDebounce);
            container._zoomDebounce = setTimeout(function () {
                container._lastBroadcastDW = dw;
                if (!group || !groups[group]) return;
                groups[group].forEach(function (peer) {
                    if (peer.id === graphId) return;
                    peer.el._suppressZoom = true;
                    peer.el._lastBroadcastDW = dw;
                    if (peer.instance) {
                        peer.instance.updateOptions({dateWindow: dw});
                    } else if (peer.setDateWindow) {
                        peer.setDateWindow(dw);
                    }
                });
            }, 30);
        }

        opts.zoomCallback = function (a, b) {
            broadcastZoom([a, b]);
        };

        var userDrawCb = opts.drawCallback;
        opts.drawCallback = function (g, isInitial) {
            if (userDrawCb) userDrawCb(g, isInitial);
            if (isInitial) return;
            var dw = g.xAxisRange();
            broadcastZoom([dw[0], dw[1]]);
        };
    }

    function attachHighlightSync(opts, container, graphId, group) {
        if (!group) return;
        var groups = ensureGroupRegistry();

        var userHighlightCb = opts.highlightCallback;
        opts.highlightCallback = function (event, x, points, row, seriesName) {
            if (userHighlightCb) {
                userHighlightCb(event, x, points, row, seriesName);
            }
            if (container._suppressHighlight) return;
            groups[group].forEach(function (peer) {
                if (peer.id === graphId || !peer.instance) return;
                peer.el._suppressHighlight = true;
                peer.instance.setSelection(row);
                peer.el._suppressHighlight = false;
            });
        };

        var userUnhighlightCb = opts.unhighlightCallback;
        opts.unhighlightCallback = function (event) {
            if (userUnhighlightCb) userUnhighlightCb(event);
            if (container._suppressHighlight) return;
            groups[group].forEach(function (peer) {
                if (peer.id === graphId || !peer.instance) return;
                peer.el._suppressHighlight = true;
                peer.instance.clearSelection();
                peer.el._suppressHighlight = false;
            });
        };
    }

    // ---------------------------------------------------------------------
    // Plugins, point shapes, extra JS
    // ---------------------------------------------------------------------

    function instantiatePlugins(config, opts) {
        if (!config.plugins) return;
        var plugs = [];
        for (var p = 0; p < config.plugins.length; p++) {
            var pl = config.plugins[p];
            if (Dygraph.Plugins && Dygraph.Plugins[pl.name]) {
                plugs.push(new Dygraph.Plugins[pl.name](pl.options));
            }
        }
        if (plugs.length > 0) opts.plugins = plugs;
    }

    function applyPointShapes(config, opts) {
        if (!config.pointShape) return;
        var shapes = config.pointShape;
        if (shapes.__global__) {
            var g = Dygraph.Circles[shapes.__global__.toUpperCase()];
            opts.drawPointCallback = g;
            opts.drawHighlightPointCallback = g;
        }
        if (opts.series) {
            for (var sn in shapes) {
                if (sn === '__global__') continue;
                if (!opts.series[sn]) opts.series[sn] = {};
                var fn = Dygraph.Circles[shapes[sn].toUpperCase()];
                opts.series[sn].drawPointCallback = fn;
                opts.series[sn].drawHighlightPointCallback = fn;
            }
        }
    }

    function evalExtraJs(config) {
        if (!config.extraJs) return;
        for (var i = 0; i < config.extraJs.length; i++) {
            try {
                eval(config.extraJs[i]);
            } catch (e) {
                console.warn('dygraphs: failed to eval extraJs:', e);
            }
        }
    }

    // ---------------------------------------------------------------------
    // Annotations / shadings / events / custom CSS
    // ---------------------------------------------------------------------

    function applyAnnotations(config, dygraph) {
        if (!config.annotations || config.annotations.length === 0) return;
        var anns = config.annotations.map(function (a) {
            var ann = {
                series: a.series,
                x: config.format === 'date' ? new Date(a.x).getTime() : a.x,
                shortText: a.shortText,
                text: a.text || '',
                attachAtBottom: a.attachAtBottom || false
            };
            if (a.width) ann.width = a.width;
            if (a.height) ann.height = a.height;
            if (a.cssClass) ann.cssClass = a.cssClass;
            if (a.tickHeight) ann.tickHeight = a.tickHeight;
            return ann;
        });
        dygraph.setAnnotations(anns);
    }

    function applyShadings(config, dygraph) {
        if (!config.shadings || config.shadings.length === 0) return;
        var shadingCb = function (canvas, area, dyg) {
            for (var s = 0; s < config.shadings.length; s++) {
                var sh = config.shadings[s];
                canvas.fillStyle = sh.color;
                if (sh.axis === 'x') {
                    var from = config.format === 'date'
                        ? new Date(sh.from).getTime() : sh.from;
                    var to = config.format === 'date'
                        ? new Date(sh.to).getTime() : sh.to;
                    var xl = dyg.toDomXCoord(from);
                    var xr = dyg.toDomXCoord(to);
                    canvas.fillRect(xl, area.y, xr - xl, area.h);
                } else {
                    var yl = dyg.toDomYCoord(sh.from);
                    var yr = dyg.toDomYCoord(sh.to);
                    canvas.fillRect(
                        area.x, Math.min(yl, yr), area.w, Math.abs(yr - yl)
                    );
                }
            }
        };
        dygraph.updateOptions({underlayCallback: shadingCb});
    }

    function applyEvents(config, dygraph) {
        if (!config.events || config.events.length === 0) return;
        var prevUl = dygraph.getOption('underlayCallback');
        var eventCb = function (canvas, area, dyg) {
            if (prevUl) prevUl(canvas, area, dyg);
            for (var e = 0; e < config.events.length; e++) {
                var ev = config.events[e];
                canvas.strokeStyle = ev.color || 'black';
                canvas.lineWidth = 1;
                if (ev.strokePattern) canvas.setLineDash(ev.strokePattern);
                canvas.beginPath();
                var xp;
                if (ev.axis === 'x') {
                    var pos = config.format === 'date'
                        ? new Date(ev.pos).getTime() : ev.pos;
                    xp = dyg.toDomXCoord(pos);
                    canvas.moveTo(xp, area.y);
                    canvas.lineTo(xp, area.y + area.h);
                } else {
                    var yp = dyg.toDomYCoord(ev.pos);
                    canvas.moveTo(area.x, yp);
                    canvas.lineTo(area.x + area.w, yp);
                }
                canvas.stroke();
                canvas.setLineDash([]);
                if (ev.label) {
                    canvas.fillStyle = ev.color || 'black';
                    canvas.font = '12px sans-serif';
                    if (ev.axis === 'x') {
                        canvas.fillText(
                            ev.label,
                            xp + 4,
                            ev.labelLoc === 'bottom'
                                ? area.y + area.h - 4
                                : area.y + 14
                        );
                    } else {
                        var llx = ev.labelLoc === 'right'
                            ? area.x + area.w
                                - canvas.measureText(ev.label).width - 4
                            : area.x + 4;
                        canvas.fillText(ev.label, llx, yp - 4);
                    }
                }
            }
        };
        dygraph.updateOptions({underlayCallback: eventCb});
    }

    function applyCustomCss(config, containerId) {
        if (!config.css) return;
        var styleId = 'dygraph-css-' + containerId;
        var existing = document.getElementById(styleId);
        if (existing) existing.remove();
        var style = document.createElement('style');
        style.id = styleId;
        style.textContent = config.css;
        document.head.appendChild(style);
    }

    // ---------------------------------------------------------------------
    // Modebar & resize observer (one-time setup per container)
    // ---------------------------------------------------------------------

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

    function installResizeObserver(container) {
        if (container._resizeObserver) return;
        container._resizeObserver = new ResizeObserver(function () {
            if (container._dygraphInstance) {
                container._dygraphInstance.resize();
            }
        });
        container._resizeObserver.observe(container);
    }

    function buildChartScaffold(setup) {
        var html = '<div class="dy-modebar-wrap" style="position:relative">'
            + '<div id="' + setup.chartDivId
            + '" style="width:100%;height:' + setup.height + 'px"></div>'
            + (setup.modebar ? setup.modebarHtml : '')
            + '</div>';
        return html;
    }

    // ---------------------------------------------------------------------
    // Data marshalling: column-oriented → row-oriented; date coercion
    // ---------------------------------------------------------------------

    function transposeData(data, format) {
        var nRows = data[0].length;
        var nCols = data.length;
        var rows = [];
        for (var i = 0; i < nRows; i++) {
            var row = [];
            for (var j = 0; j < nCols; j++) {
                var val = data[j][i];
                if (j === 0 && format === 'date' && typeof val === 'string') {
                    val = new Date(val);
                }
                row.push(val);
            }
            rows.push(row);
        }
        return rows;
    }

    // ---------------------------------------------------------------------
    // Main entry point
    // ---------------------------------------------------------------------

    function render(setup, config) {
        if (!config) return;

        loadCssOnce(setup.cdnCssUrl);
        if (setup.modebar) loadModebarCssOnce(setup.modebarCss);

        function doRender() {
            var container = document.getElementById(setup.containerId);
            if (!container) return;

            var rows = transposeData(config.data, config.format);

            // Clone attrs so the processJsMarkers eval walk doesn't mutate
            // the cached config. Single pass, single easy-to-audit eval
            // site for the marker protocol.
            var opts = JSON.parse(JSON.stringify(config.attrs));
            processJsMarkers(opts);

            // Group registry: drop any stale entry for this container
            // (we re-register after creating the dygraph below).
            var groups = ensureGroupRegistry();
            if (config.group) {
                if (!groups[config.group]) groups[config.group] = [];
                groups[config.group] = groups[config.group].filter(
                    function (e) { return e.id !== setup.graphId; }
                );
            }

            attachZoomSync(opts, container, setup.graphId, config.group);
            attachHighlightSync(opts, container, setup.graphId, config.group);

            evalExtraJs(config);
            instantiatePlugins(config, opts);
            applyPointShapes(config, opts);

            // Always destroy + recreate (R/htmlwidgets model).
            // One update path — no "did I forget to invalidate X" bugs.
            var ex = container._dygraphInstance;
            if (ex) {
                // Optionally preserve the user's zoom across data updates.
                // Default is false (matches R's retainDateWindow = FALSE).
                // The Python builder puts it under config.attrs.
                if (opts.retainDateWindow) {
                    var prevRange = ex.xAxisRange();
                    if (prevRange) {
                        opts.dateWindow = prevRange;
                    }
                }
                ex.destroy();
                container._dygraphInstance = null;
            }
            container.innerHTML = buildChartScaffold(setup);
            container._dygraphInstance = new Dygraph(
                document.getElementById(setup.chartDivId), rows, opts
            );
            var dygraph = container._dygraphInstance;

            // Re-register in group
            if (config.group && groups[config.group]) {
                groups[config.group].push({
                    id: setup.graphId, el: container, instance: dygraph
                });
            }

            installResizeObserver(container);
            installCaptureFn(setup);
            installResetFn(setup, container);

            applyAnnotations(config, dygraph);
            applyShadings(config, dygraph);
            applyEvents(config, dygraph);
            applyCustomCss(config, setup.containerId);
        }

        loadDygraphJsOnce(setup.cdnJsUrl, doRender);
    }

    global.dygraphsDash = {render: render};
})(window);
