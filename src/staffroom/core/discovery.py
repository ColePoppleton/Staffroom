"""Find tool plugins.

Tools are discovered with ``pkgutil`` over ``staffroom.tools`` rather than
entry points: this is a single repository with no third-party plugins, and a
new folder created by ``staff new`` should appear in ``staff list`` immediately
without reinstalling the package. Entry points would add packaging ceremony
and buy nothing here.
"""

from __future__ import annotations

import importlib
import pkgutil
from functools import cache
from types import ModuleType

from staffroom.core.log import get_logger
from staffroom.core.plugin import (
    DEFAULT_ORDER,
    GROUPS,
    OTHER_GROUP,
    ToolPlugin,
    plugin_group,
    plugin_hidden,
    plugin_order,
)

log = get_logger(__name__)
TOOLS_PACKAGE = "staffroom.tools"

WORKFLOW_ORDER: tuple[str, ...] = (
    "classroom",
    "worksheet",
    "quiz",
    "parsons",
    "trace",
    "bugs",
    "fade",
    "pseudocode",
    "marks",
)
"""The shipped tools in sidebar order, which follows the groups of a
teacher's week (:data:`~staffroom.core.plugin.GROUPS`): open a resource for
class; sheets and quizzes; the five tools made from a program; marks after a
test. Within its group a plugin's declared ``order`` overrides its place
here; a tool not listed and without an ``order`` comes after these, A-Z.
"""


def iter_tool_module_names(package: str = TOOLS_PACKAGE) -> list[str]:
    pkg: ModuleType = importlib.import_module(package)
    names = [
        info.name
        for info in pkgutil.iter_modules(pkg.__path__)
        if info.ispkg and not info.name.startswith("_")
    ]
    return sorted(names)


def load_plugin(name: str, package: str = TOOLS_PACKAGE) -> ToolPlugin:
    module = importlib.import_module(f"{package}.{name}")
    plugin = getattr(module, "plugin", None)
    if plugin is None:
        msg = f"{package}.{name} has no module-level 'plugin' object"
        raise TypeError(msg)
    if not isinstance(plugin, ToolPlugin):
        msg = f"{package}.{name}.plugin does not satisfy the ToolPlugin protocol"
        raise TypeError(msg)
    if plugin.name != name:
        msg = f"plugin in package {name!r} calls itself {plugin.name!r}; they must match"
        raise ValueError(msg)
    try:
        plugin.panel_spec()
    except Exception as exc:
        msg = f"{name}: panel_spec() is invalid: {exc}"
        raise ValueError(msg) from exc
    return plugin


def group_key(group: str) -> tuple[int, str]:
    """Where ``group`` sits in the sidebar: the named :data:`GROUPS` in their
    order, then any group a plugin made up (A-Z), then :data:`OTHER_GROUP`."""
    if group in GROUPS:
        return GROUPS.index(group), ""
    if group == OTHER_GROUP:
        return len(GROUPS) + 1, ""
    return len(GROUPS), group.casefold()


def sort_key(plugin: ToolPlugin) -> tuple[int, str, int, str]:
    """``(group rank, group, order, name)``: by group first (:func:`group_key`),
    then within it a declared ``order``, else the workflow position, else
    :data:`DEFAULT_ORDER`, ties by name."""
    order = plugin_order(plugin)
    if order == DEFAULT_ORDER and plugin.name in WORKFLOW_ORDER:
        order = WORKFLOW_ORDER.index(plugin.name) * 10
    rank, group = group_key(plugin_group(plugin))
    return rank, group, order, plugin.name


def grouped(plugins: tuple[ToolPlugin, ...]) -> list[tuple[str, tuple[ToolPlugin, ...]]]:
    """``plugins`` as sidebar groups, ``[(group, tools), ...]``, both in
    sidebar order (:func:`sort_key`). Empty groups are left out."""
    groups: dict[str, list[ToolPlugin]] = {}
    for plugin in sorted(plugins, key=sort_key):
        groups.setdefault(plugin_group(plugin), []).append(plugin)
    return [(name, tuple(tools)) for name, tools in groups.items()]


@cache
def discover_plugins() -> tuple[ToolPlugin, ...]:
    """All loadable plugins, hidden ones included, in sidebar order
    (:func:`sort_key`). Broken tools are logged and skipped so one bad tool
    never takes the launcher down."""
    found: list[ToolPlugin] = []
    for name in iter_tool_module_names():
        try:
            found.append(load_plugin(name))
        except Exception:
            log.exception("skipping tool %r: failed to load", name)
    return tuple(sorted(found, key=sort_key))


def visible_plugins(plugins: tuple[ToolPlugin, ...] | None = None) -> tuple[ToolPlugin, ...]:
    """The plugins a teacher should see: ``plugins`` (default: everything
    discovered) without the ones that declare ``hidden = True``."""
    source = discover_plugins() if plugins is None else plugins
    return tuple(p for p in source if not plugin_hidden(p))


def get_plugin(name: str) -> ToolPlugin:
    for plugin in discover_plugins():
        if plugin.name == name:
            return plugin
    msg = f"no tool named {name!r}"
    raise KeyError(msg)
