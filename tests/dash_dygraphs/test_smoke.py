"""Smoke test: package imports and has a version."""

from __future__ import annotations


def test_import() -> None:
    import dash_dygraphs

    assert dash_dygraphs.__version__
