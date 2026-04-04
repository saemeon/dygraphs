"""Smoke test: package imports and has a version."""

from __future__ import annotations


def test_import() -> None:
    import pydygraphs

    assert pydygraphs.__version__
