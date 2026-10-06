"""Find tool plugins.

Tools are discovered with ``pkgutil`` over ``teaching_tools.tools`` rather than
entry points: this is a single repository with no third-party plugins, and a
new folder created by ``tt new`` should appear in ``tt list`` immediately
without reinstalling the package. Entry points would add packaging ceremony
and buy nothing here.
"""

from __future__ import annotations

import importlib
import pkgutil
from functools import cache
from types import ModuleType

from teaching_tools.core.log import get_logger
from teaching_tools.core.plugin import ToolPlugin

log = get_logger(__name__)
TOOLS_PACKAGE = "teaching_tools.tools"


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
    return plugin


@cache
def discover_plugins() -> tuple[ToolPlugin, ...]:
    """All loadable plugins, sorted by name. Broken tools are logged and
    skipped so one bad tool never takes the launcher down."""
    found: list[ToolPlugin] = []
    for name in iter_tool_module_names():
        try:
            found.append(load_plugin(name))
        except Exception:
            log.exception("skipping tool %r: failed to import", name)
    return tuple(found)


def get_plugin(name: str) -> ToolPlugin:
    for plugin in discover_plugins():
        if plugin.name == name:
            return plugin
    msg = f"no tool named {name!r}"
    raise KeyError(msg)
