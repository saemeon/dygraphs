"""Tests for plugins (unzoom, crosshair, ribbon, rebase)."""

from __future__ import annotations

import pandas as pd

from dash_dygraphs import Dygraph


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {"y": range(5)},
        index=pd.date_range("2020-01-01", periods=5, freq="D"),
    )


class TestPlugins:
    def test_unzoom(self) -> None:
        d = Dygraph(_df()).unzoom()
        plugins = d.to_dict()["plugins"]
        assert len(plugins) == 1
        assert plugins[0]["name"] == "Unzoom"

    def test_crosshair(self) -> None:
        d = Dygraph(_df()).crosshair(direction="vertical")
        plugins = d.to_dict()["plugins"]
        assert plugins[0]["name"] == "Crosshair"
        assert plugins[0]["options"]["direction"] == "vertical"

    def test_ribbon(self) -> None:
        d = Dygraph(_df()).ribbon(
            data=[0, 0.5, 1, 0.5, 0],
            palette=["red", "green"],
            top=0.1,
            bottom=0.02,
        )
        plugins = d.to_dict()["plugins"]
        assert plugins[0]["name"] == "Ribbon"
        assert plugins[0]["options"]["data"] == [0, 0.5, 1, 0.5, 0]

    def test_rebase_value(self) -> None:
        d = Dygraph(_df()).rebase(value=100)
        plugins = d.to_dict()["plugins"]
        assert plugins[0]["name"] == "Rebase"
        assert plugins[0]["options"] == 100

    def test_rebase_percent(self) -> None:
        d = Dygraph(_df()).rebase(percent=True)
        plugins = d.to_dict()["plugins"]
        assert plugins[0]["options"] == "percent"
