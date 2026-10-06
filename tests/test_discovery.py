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


def test_unknown_plugin() -> None:
    with pytest.raises(KeyError):
        get_plugin("nope")
