from pathlib import Path

from teaching_tools.core.launch import EDITOR_PRESETS, editor_argv, launch_editor, preset_for


def test_editor_argv_handles_spaces_and_missing_placeholder() -> None:
    f = Path("/tmp/My Lesson/while loops.py")
    assert editor_argv("open -a Thonny {file}", f) == ["open", "-a", "Thonny", str(f)]
    assert editor_argv("code", f) == ["code", str(f)]
    assert editor_argv("", f)[:3] == ["open", "-a", "Thonny"]


def test_presets_round_trip() -> None:
    for name, cmd in EDITOR_PRESETS.items():
        assert preset_for(cmd) == name
    assert preset_for("subl {file}") == "Custom"


def test_launch_editor_uses_runner() -> None:
    calls: list[list[str]] = []
    argv = launch_editor("open {file}", Path("/x/y.py"), lambda a: calls.append(list(a)))
    assert calls == [argv] == [["open", "/x/y.py"]]
