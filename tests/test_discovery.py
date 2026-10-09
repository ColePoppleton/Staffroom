import pytest

from staffroom.core.discovery import (
    WORKFLOW_ORDER,
    discover_plugins,
    get_plugin,
    group_key,
    grouped,
    iter_tool_module_names,
    sort_key,
    visible_plugins,
)
from staffroom.core.plugin import (
    DEFAULT_ORDER,
    GROUPS,
    OTHER_GROUP,
    ToolPlugin,
    plugin_glyph,
    plugin_group,
    plugin_hidden,
    plugin_order,
)


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
    """The shipped tools come out group by group, in the order of a teacher's
    week, not A-Z; hello (hidden, no group) is still discovered and lands in
    Other, after them."""
    names = [p.name for p in discover_plugins()]
    assert len(names) == len(set(names))
    shipped = [n for n in names if n in WORKFLOW_ORDER]
    assert shipped == list(WORKFLOW_ORDER)
    assert names.index("hello") > names.index("marks")


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


def test_sort_key_group_then_declared_order_then_workflow_then_alphabetical() -> None:
    """Groups first; within one, a declared order wins, the workflow list
    places shipped tools that declare none, anything else goes after, A-Z."""
    first = _Stub("zzz", order=-1, group="From a program")
    trace = _Stub("trace", group="From a program")  # shipped, no order: workflow position
    third_party = [_Stub("beta", group="From a program"), _Stub("alpha", group="From a program")]
    lesson = _Stub("zebra", group="Lessons")
    ungrouped = _Stub("aardvark")
    ordered = sorted(
        [ungrouped, *third_party, trace, first, lesson],
        key=sort_key,  # type: ignore[arg-type]
    )
    assert [p.name for p in ordered] == ["zebra", "zzz", "trace", "alpha", "beta", "aardvark"]
    assert sort_key(_Stub("marks", order=0))[2] == 0  # type: ignore[arg-type]
    assert sort_key(_Stub("alpha"))[2] == DEFAULT_ORDER  # type: ignore[arg-type]


def test_group_and_glyph_default_so_other_tools_need_no_change() -> None:
    plain = _Stub("plain")
    assert plugin_group(plain) == OTHER_GROUP  # type: ignore[arg-type]
    assert plugin_glyph(plain) == ""  # type: ignore[arg-type]
    assert plugin_group(_Stub("g", group="  ")) == OTHER_GROUP  # type: ignore[arg-type]
    assert plugin_group(_Stub("g", group=3)) == OTHER_GROUP  # type: ignore[arg-type]
    assert plugin_group(_Stub("g", group="After a test")) == "After a test"  # type: ignore[arg-type]
    assert plugin_glyph(_Stub("g", glyph="chart")) == "chart"  # type: ignore[arg-type]
    assert plugin_glyph(_Stub("g", glyph=None)) == ""  # type: ignore[arg-type]


def test_groups_in_week_order_then_made_up_ones_then_other() -> None:
    assert [group_key(g)[0] for g in GROUPS] == [0, 1, 2, 3]
    assert group_key("Admin") < group_key("Zoo") < group_key(OTHER_GROUP)
    assert group_key("After a test") < group_key("Admin")
    stubs = [
        _Stub("x"),
        _Stub("y", group="Zoo"),
        _Stub("m", group="After a test"),
        _Stub("c", group="Lessons"),
    ]
    sections = grouped(tuple(stubs))  # type: ignore[arg-type]
    assert [(g, [p.name for p in tools]) for g, tools in sections] == [
        ("Lessons", ["c"]),
        ("After a test", ["m"]),
        ("Zoo", ["y"]),
        (OTHER_GROUP, ["x"]),
    ]


def test_every_shipped_tool_declares_a_known_group_and_a_glyph() -> None:
    sections = grouped(visible_plugins())
    assert [(g, [p.name for p in tools]) for g, tools in sections] == [
        ("Lessons", ["classroom"]),
        ("Sheets & quizzes", ["worksheet", "quiz"]),
        ("From a program", ["parsons", "trace", "bugs", "fade", "pseudocode"]),
        ("After a test", ["marks"]),
    ]
    assert all(plugin_glyph(p) for p in visible_plugins())


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
