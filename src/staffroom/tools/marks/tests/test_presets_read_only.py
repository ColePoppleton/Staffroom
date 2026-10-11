"""Saving a boundary preset under a read-only config home (#74): a message
for the teacher (``ToolError``), not a bug traceback, and the preset is still
there for the rest of the session."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from staffroom.core.config import Config, load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.core.table import Table
from staffroom.tools.marks import plugin, presets

pytestmark = pytest.mark.skipif(os.geteuid() == 0, reason="root is not bound by file modes")


@pytest.fixture
def locked_config(isolated_home: Path) -> Iterator[Config]:
    """``config.toml`` at ``0o400`` in a ``0o500`` home, restored on teardown."""
    config = load_config()
    config.save()
    config.path.chmod(0o400)
    isolated_home.chmod(0o500)
    try:
        yield config
    finally:
        isolated_home.chmod(0o700)
        config.path.chmod(0o600)


def test_saving_a_preset_under_a_locked_home_is_a_tool_error(
    locked_config: Config, tmp_path: Path
) -> None:
    ctx = RunContext(config=locked_config, output_dir=tmp_path)
    custom = Table(["Grade", "Minimum"], [["Pass", 50.0], ["Fail", 0.0]])
    with pytest.raises(ToolError) as caught:
        plugin.act("save_preset", {"name": "Mock Nov", "table": custom}, ctx)
    assert str(caught.value) == (
        f"Preset 'Mock Nov' could not be saved: {locked_config.path} is read-only. "
        "You can use it until you quit."
    )
    # In memory for the session, not on disk.
    assert presets.all_presets(locked_config)["Mock Nov"] == (("Pass", 50.0), ("Fail", 0.0))
    assert "Mock Nov" not in presets.all_presets(load_config())
