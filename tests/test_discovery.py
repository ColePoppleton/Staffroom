import pytest

from teaching_tools.core.discovery import discover_plugins, get_plugin, iter_tool_module_names
from teaching_tools.core.plugin import ToolPlugin


def test_hello_is_discovered() -> None:
    assert "hello" in iter_tool_module_names()
    plugin = get_plugin("hello")
    assert isinstance(plugin, ToolPlugin)
    assert plugin.name == "hello"
    assert plugin.panel_spec().title == "Hello"


def test_plugins_sorted_and_unique() -> None:
    names = [p.name for p in discover_plugins()]
    assert names == sorted(set(names))


def test_invalid_panel_spec_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool whose panel_spec() raises is skipped at discovery, not fatal."""
    import types

    from teaching_tools.core.discovery import load_plugin

    class Broken:
        name = "broken"
        description = "x"
        version = "0"

        def register_cli(self, app: object) -> None:
            pass

        def panel_spec(self) -> None:
            raise ValueError("duplicate widget keys")

        def run(self, inputs: object, ctx: object) -> None:
            pass

    module = types.ModuleType("teaching_tools.tools.broken")
    module.plugin = Broken()  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "teaching_tools.tools.broken", module)
    with pytest.raises(ValueError, match="panel_spec\\(\\) is invalid"):
        load_plugin("broken")


def test_unknown_plugin() -> None:
    with pytest.raises(KeyError):
        get_plugin("nope")
