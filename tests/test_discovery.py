import pytest

from staffroom.core.discovery import (
    WORKFLOW_ORDER,
    discover_plugins,
    get_plugin,
    iter_tool_module_names,
    sort_key,
    visible_plugins,
)
from staffroom.core.plugin import DEFAULT_ORDER, ToolPlugin, plugin_hidden, plugin_order


class _Stub:
    """A minimal third-party-looking plugin: no ``order``, no ``hidden``."""

    description = "x"
    version = "0"

    def __init__(self, name: str, **attrs: object) -> None:
        self.name = name
        for key, value in attrs.items():
            setattr(self, key, value)

    def register_cli(self, app: object) -> None:
        pass

    def panel_spec(self) -> None:
        return None

    def run(self, inputs: object, ctx: object) -> None:
        pass


def test_hello_is_discovered() -> None:
    assert "hello" in iter_tool_module_names()
    plugin = get_plugin("hello")
    assert isinstance(plugin, ToolPlugin)
    assert plugin.name == "hello"
    assert plugin.panel_spec().title == "Hello"


def test_plugins_unique_and_in_workflow_order() -> None:
    """The shipped tools come out in the order a teacher meets them, not A-Z;
    hello (hidden, unordered) is still discovered and lands after them."""
    names = [p.name for p in discover_plugins()]
    assert len(names) == len(set(names))
    shipped = [n for n in names if n in WORKFLOW_ORDER]
    assert shipped == list(WORKFLOW_ORDER)
    assert names.index("hello") > names.index("pseudocode")


def test_visible_plugins_skip_hidden_but_keep_the_order() -> None:
    visible = [p.name for p in visible_plugins()]
    assert "hello" not in visible
    assert visible[0] == "classroom"
    assert visible == [p.name for p in discover_plugins() if not plugin_hidden(p)]
    assert plugin_hidden(get_plugin("hello"))


def test_order_and_hidden_default_so_other_tools_need_no_change() -> None:
    plain = _Stub("plain")
    assert plugin_order(plain) == DEFAULT_ORDER  # type: ignore[arg-type]
    assert plugin_hidden(plain) is False  # type: ignore[arg-type]
    assert plugin_order(_Stub("o", order=True)) == DEFAULT_ORDER  # type: ignore[arg-type]
    assert plugin_order(_Stub("o", order="3")) == DEFAULT_ORDER  # type: ignore[arg-type]
    assert plugin_order(_Stub("o", order=3)) == 3  # type: ignore[arg-type]
    assert plugin_hidden(_Stub("h", hidden=True)) is True  # type: ignore[arg-type]


def test_sort_key_declared_order_then_workflow_then_alphabetical() -> None:
    """A declared order wins; the workflow list places shipped tools that
    declare none; anything else goes after both, A-Z."""
    first = _Stub("zzz", order=-1)
    marks = _Stub("marks")  # shipped, no order: workflow position
    third_party = [_Stub("beta"), _Stub("alpha")]
    ordered = sorted([*third_party, marks, first], key=sort_key)  # type: ignore[arg-type]
    assert [p.name for p in ordered] == ["zzz", "marks", "alpha", "beta"]
    assert sort_key(_Stub("marks", order=0))[0] == 0  # type: ignore[arg-type]
    assert sort_key(_Stub("alpha"))[0] == DEFAULT_ORDER  # type: ignore[arg-type]


def test_invalid_panel_spec_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool whose panel_spec() raises is skipped at discovery, not fatal."""
    import types

    from staffroom.core.discovery import load_plugin

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

    module = types.ModuleType("staffroom.tools.broken")
    module.plugin = Broken()  # type: ignore[attr-defined]
    monkeypatch.setitem(__import__("sys").modules, "staffroom.tools.broken", module)
    with pytest.raises(ValueError, match="panel_spec\\(\\) is invalid"):
        load_plugin("broken")


def test_unknown_plugin() -> None:
    with pytest.raises(KeyError):
        get_plugin("nope")
