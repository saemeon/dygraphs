/* dygraphs shared renderer — framework-agnostic.
 *
 * Single entry point: window.dygraphs.render(container, config, options).
 *
 *   container       — DOM element that owns this chart. State lives on
 *                     ``container._dygraphInstance`` and group-sync flags.
 *                     The inner chart ``<div>`` Dygraph renders into is
 *                     built by ``options.scaffoldBuilder`` (or a plain
 *                     full-size div by default).
 *   config          — serialised ``Dygraph`` payload (``dg.to_js()``).
 *   options         — framework hooks, all optional:
 *       scaffoldBuilder(container) → chartDivEl
 *           Called once per render; must reset ``container``'s contents
 *           and return the element Dygraph should mount in. Dash uses
 *           this to inject the modebar HTML around the chart div.
 *           Default: replaces container HTML with a single
 *           ``<div style="width:100%;height:100%">`` child.
 *       cssUrl, jsUrl
 *           CDN URLs for dygraph.css / dygraph.min.js. When omitted the
 *           caller is responsible for loading the library before calling
 *           ``render`` (e.g. via a ``<script src>`` in the page head).
 *
 * The IIFE guard makes repeated inlines / imports idempotent — every
 * Dash per-chart callback and every Shiny custom-message handler inlines
 * this asset; only the first inline populates ``window.dygraphs``.
 *
 * Why it exists: Dash's ``dash_render.js`` and Shiny's inline handler
 * used to re-implement the same ~250 lines of rendering logic. Any fix
 * to one silently drifted from the other (tz normalisation,
 * ``Dygraph.Interaction.defaultModel`` compat shim, plotter-eval
 * ordering). Extracting the shared core into one asset kills the drift.
 */
(function (global) {
    if (global.dygraphs) return;

    // ---------------------------------------------------------------------
    // One-time CSS / JS loading
    // ---------------------------------------------------------------------

    function loadCssOnce(id, url) {
        if (document.getElementById(id)) return;
        var link = document.createElement('link');
        link.id = id;
        link.rel = 'stylesheet';
        link.href = url;
        document.head.appendChild(link);
    }

    function loadDygraphLibOnce(url, onReady) {
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
    // Charts sharing the same ``config.group`` keep their dateWindow and
    // hover row in lockstep via a global registry on ``window.__dyGroups``.
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
    // Resize observer — generic DOM concern, useful in any framework.
    // ---------------------------------------------------------------------

    function installResizeObserver(container) {
        if (container._resizeObserver) return;
        container._resizeObserver = new ResizeObserver(function () {
            if (container._dygraphInstance) {
                container._dygraphInstance.resize();
            }
        });
        container._resizeObserver.observe(container);
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
    // Default scaffold: plain chart div filling the container.
    // Dash overrides this to inject the modebar HTML around the chart.
    // ---------------------------------------------------------------------

    function defaultScaffoldBuilder(container) {
        var chartId = container.id + '-chart';
        container.innerHTML = '<div id="' + chartId
            + '" style="width:100%;height:100%"></div>';
        return document.getElementById(chartId);
    }

    // ---------------------------------------------------------------------
    // Main entry point
    // ---------------------------------------------------------------------

    function render(container, config, options) {
        if (!config || !container) return;
        options = options || {};
        var scaffoldBuilder = options.scaffoldBuilder || defaultScaffoldBuilder;
        var graphId = container.id;

        var rows = transposeData(config.data, config.format);

        // Clone attrs so the processJsMarkers eval walk doesn't
        // mutate the cached config.
        var opts = JSON.parse(JSON.stringify(config.attrs));

        // Compat shim: some Dygraph builds only expose
        // ``Dygraph.defaultInteractionModel`` at the top level and
        // leave ``Dygraph.Interaction.defaultModel`` undefined. The
        // shim populates the latter so ``__JS__`` markers like
        // ``JS("Dygraph.Interaction.defaultModel")`` (emitted by
        // ``.range_selector(keep_mouse_zoom=True)``) resolve. Must
        // run before ``processJsMarkers`` evaluates them.
        if (typeof Dygraph !== 'undefined' && Dygraph.Interaction
            && !Dygraph.Interaction.defaultModel
            && Dygraph.defaultInteractionModel) {
            Dygraph.Interaction.defaultModel = Dygraph.defaultInteractionModel;
        }

        // Inject plotter / plugin / data-handler JS BEFORE resolving
        // ``__JS__`` markers — ``.bar_chart()`` etc. emit
        // ``plotter: JS("Dygraph.Plotters.BarChart")`` which only
        // resolves once ``barchart.js`` has run its IIFE and
        // assigned ``Dygraph.Plotters.BarChart``. If markers were
        // evaluated first, the lookup returns ``undefined`` and
        // Dygraph silently falls back to the default line plotter.
        evalExtraJs(config);

        // Now resolve ``__JS__:code:__JS__`` markers into real JS
        // values — everything referenced is in scope: Dygraph core,
        // Dygraph.Plotters.*, Dygraph.DataHandlers.*, and any user-
        // supplied globals from extraJs.
        processJsMarkers(opts);

        // Normalise opts.dateWindow: the Python builder emits
        // ISO-8601 strings (e.g. "2024-01-10T00:00:00.000Z") for
        // date axes; the Dygraph constructor expects millisecond
        // numbers or Date objects. Without this, Dygraph.parse_
        // silently coerces to NaN and the initial window is ignored.
        if (opts.dateWindow && opts.dateWindow.length === 2) {
            opts.dateWindow = opts.dateWindow.map(function (v) {
                return typeof v === 'string' ? new Date(v).getTime() : v;
            });
        }

        // Group registry: drop any stale entry for this container
        // (we re-register after creating the dygraph below).
        var groups = ensureGroupRegistry();
        if (config.group) {
            if (!groups[config.group]) groups[config.group] = [];
            groups[config.group] = groups[config.group].filter(
                function (e) { return e.id !== graphId; }
            );
        }

        attachZoomSync(opts, container, graphId, config.group);
        attachHighlightSync(opts, container, graphId, config.group);

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

        var chartDiv = scaffoldBuilder(container);
        container._dygraphInstance = new Dygraph(chartDiv, rows, opts);
        var dygraph = container._dygraphInstance;

        // Re-register in group
        if (config.group && groups[config.group]) {
            groups[config.group].push({
                id: graphId, el: container, instance: dygraph
            });
        }

        installResizeObserver(container);

        applyAnnotations(config, dygraph);
        applyShadings(config, dygraph);
        applyEvents(config, dygraph);
        applyCustomCss(config, graphId);

        return dygraph;
    }

    global.dygraphs = {
        render: render,
        loadCssOnce: loadCssOnce,
        loadDygraphLibOnce: loadDygraphLibOnce
    };
})(window);
