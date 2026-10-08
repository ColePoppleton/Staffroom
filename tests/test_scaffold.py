"""``staff new`` must produce a tool that imports, satisfies the protocol and
passes its own generated test."""

import importlib
from pathlib import Path

import pytest

from staffroom.core.plugin import ToolPlugin
from staffroom.core.scaffold import class_name_for, scaffold_tool, validate_tool_name


def test_names() -> None:
    assert class_name_for("grade_boundaries") == "GradeBoundariesPlugin"
    for bad in ("Bad", "1x", "a-b", "class"):
        with pytest.raises(ValueError, match="not a valid tool name"):
            validate_tool_name(bad)


def test_scaffold_produces_working_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Build a throwaway namespace package 'staffroom.tools' lookalike under tmp.
    pkg_root = tmp_path / "scaffolded"
    tools_dir = pkg_root / "staffroom" / "tools"
    tools_dir.mkdir(parents=True)
    written = scaffold_tool("demo_tool", tools_dir)
    assert {p.name for p in written} >= {"__init__.py", "logic.py", "panel.py", "cli.py"}

    # Import it as a real tool by extending the tools package path.
    import staffroom.tools as tools_pkg

    monkeypatch.setattr(tools_pkg, "__path__", [*tools_pkg.__path__, str(tools_dir)])
    module = importlib.import_module("staffroom.tools.demo_tool")
    plugin = module.plugin
    assert isinstance(plugin, ToolPlugin)
    assert plugin.name == "demo_tool"
    spec = plugin.panel_spec()
    assert spec.title == "Demo tool"
    assert "source" in spec.input_keys()
    # Neither optional attribute is set, so it sorts after the shipped tools and shows.
    from staffroom.core.plugin import DEFAULT_ORDER, plugin_hidden, plugin_order

    assert plugin_order(plugin) == DEFAULT_ORDER and plugin_hidden(plugin) is False
    assert "order = " in (tools_dir / "demo_tool" / "__init__.py").read_text()

    with pytest.raises(FileExistsError):
        scaffold_tool("demo_tool", tools_dir)

    # The generated test passes.
    generated = importlib.import_module("staffroom.tools.demo_tool.tests.test_logic")
    generated.test_process_returns_table()
