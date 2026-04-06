"""Smoke test: package imports and has a version."""

from __future__ import annotations


def test_import() -> None:
    import dygraphs

    assert dygraphs.__version__
