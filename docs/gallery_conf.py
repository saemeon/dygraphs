"""Base configuration for the mkdocs-gallery plugin.

This file is loaded via ``conf_script`` in ``mkdocs.yml`` and must
define a module-level ``conf`` dict. Values set here become the
plugin's defaults; anything set in ``mkdocs.yml`` overrides them.

We use this file (instead of a string path like
``"docs._mkdocs_gallery_scraper.dygraph_scraper"`` in ``mkdocs.yml``)
because mkdocs-gallery loads the scraper via module import, and the
``docs/`` directory isn't on ``sys.path`` at build time. Shipping the
scraper as a callable inside the conf dict bypasses the import step.
"""

from __future__ import annotations

from html import escape as html_escape
from typing import Any

# Per-script dedup state. Keyed by the script's source file path so
# charts created in one script don't affect dedup for another. We
# can't stash this on ``script.run_vars`` itself — ``ScriptRunVars``
# uses ``__slots__`` and rejects ad-hoc attributes.
_SEEN_BY_SCRIPT: dict[str, set[int]] = {}


def dygraph_scraper(block: tuple, script: Any, **_kwargs: Any) -> str:
    """Capture ``Dygraph`` objects from an example's top-level globals.

    mkdocs-gallery image-scraper contract: called once per code block
    with ``block = (label, content, lineno)`` and
    ``script = GalleryScript``. Return a Markdown snippet that will
    be inserted in place of the normal plot output. Empty string =
    no output (suppresses the default "no plot" placeholder).

    We embed each detected ``Dygraph`` as an ``<iframe srcdoc>`` so
    every chart gets its own JavaScript sandbox — gallery pages with
    multiple charts don't collide on ``window`` globals.
    """
    try:
        from dygraphs import Dygraph
    except ImportError:
        return ""

    globals_ = getattr(script.run_vars, "example_globals", {}) or {}
    charts: list[tuple[str, Dygraph]] = [
        (name, value) for name, value in globals_.items() if isinstance(value, Dygraph)
    ]
    if not charts:
        return ""

    # Dedupe charts already emitted by a previous block in the same
    # script. The matplotlib scraper achieves the same thing by
    # calling ``plt.close()`` after each block; dygraphs has no such
    # global figure queue, so we track by instance ``id()`` instead.
    script_key = str(getattr(script, "src_py_file", id(script)))
    seen = _SEEN_BY_SCRIPT.setdefault(script_key, set())
    fresh = [(name, c) for name, c in charts if id(c) not in seen]
    if not fresh:
        return ""
    for _, c in fresh:
        seen.add(id(c))

    blocks: list[str] = []
    for name, chart in fresh:
        html = chart.to_html()
        srcdoc = html_escape(html, quote=True)
        blocks.append(
            f'<iframe srcdoc="{srcdoc}" '
            f'title="{html_escape(name)}" '
            f'style="width:100%; height:340px; border:0; '
            f'border-radius:8px; box-shadow:0 1px 4px rgba(0,0,0,0.08);"'
            f"></iframe>"
        )
    return "\n\n".join(blocks) + "\n\n"


# mkdocs-gallery merges this dict into the plugin config.
# Anything set in mkdocs.yml wins over keys set here.
conf: dict[str, Any] = {
    "image_scrapers": [dygraph_scraper],
}
