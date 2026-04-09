"""Tests for plugins (unzoom, crosshair, ribbon, rebase)."""

from __future__ import annotations

import pandas as pd

from dygraphs import Dygraph


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


class TestDependency:
    """Tests for ``dependency()`` — the Python port of R ``dyDependency``."""

    def test_dependency_without_files(self) -> None:
        """Name+version only should still register a bookkeeping entry."""
        d = Dygraph(_df()).dependency("MyDep", version="2.0")
        cfg = d.to_dict()
        assert cfg["dependencies"][0] == {
            "name": "MyDep",
            "version": "2.0",
            "src": None,
            "script": [],
            "stylesheet": [],
        }

    def test_dependency_script_inlined_in_to_html(self, tmp_path) -> None:
        js = tmp_path / "my-plugin.js"
        js.write_text("window.__myPluginLoaded = true;")
        d = Dygraph(_df()).dependency("MyDep", script=str(js))
        html = d.to_html()
        assert "window.__myPluginLoaded = true;" in html
        assert f"<script>{js.read_text()}</script>" in html

    def test_dependency_stylesheet_inlined_in_to_html(self, tmp_path) -> None:
        css = tmp_path / "my-dep.css"
        css.write_text(".my-dep-class { color: tomato; }")
        d = Dygraph(_df()).dependency("MyDep", stylesheet=str(css))
        html = d.to_html()
        assert ".my-dep-class { color: tomato; }" in html
        assert f"<style>{css.read_text()}</style>" in html

    def test_dependency_src_resolves_relative_paths(self, tmp_path) -> None:
        (tmp_path / "a.js").write_text("var a=1;")
        (tmp_path / "b.css").write_text(".b{color:red}")
        d = Dygraph(_df()).dependency(
            "MyDep", src=tmp_path, script="a.js", stylesheet="b.css"
        )
        html = d.to_html()
        assert "var a=1;" in html
        assert ".b{color:red}" in html

    def test_dependency_accepts_list_of_scripts(self, tmp_path) -> None:
        (tmp_path / "a.js").write_text("var a=1;")
        (tmp_path / "b.js").write_text("var b=2;")
        d = Dygraph(_df()).dependency("MyDep", src=tmp_path, script=["a.js", "b.js"])
        html = d.to_html()
        assert "var a=1;" in html
        assert "var b=2;" in html

    def test_dependency_stylesheet_emitted_before_script(self, tmp_path) -> None:
        """CSS must appear before JS so scripts can reference stylesheet classes."""
        (tmp_path / "a.js").write_text("var a=1;")
        (tmp_path / "b.css").write_text(".b{}")
        d = Dygraph(_df()).dependency(
            "MyDep", src=tmp_path, script="a.js", stylesheet="b.css"
        )
        html = d.to_html()
        assert html.index(".b{}") < html.index("var a=1;")

    def test_dependencies_field_absent_when_empty(self) -> None:
        """No dependencies -> to_dict omits the key (matches plugins behaviour)."""
        cfg = Dygraph(_df()).to_dict()
        assert "dependencies" not in cfg

    def test_dependency_chains(self) -> None:
        """Multiple calls accumulate."""
        d = Dygraph(_df()).dependency("A").dependency("B", version="3.0")
        deps = d.to_dict()["dependencies"]
        assert [x["name"] for x in deps] == ["A", "B"]
        assert deps[1]["version"] == "3.0"
