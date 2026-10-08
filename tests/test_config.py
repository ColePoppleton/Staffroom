from pathlib import Path

from staffroom.core import paths
from staffroom.core.config import load_config


def test_defaults_when_missing(isolated_home: Path) -> None:
    cfg = load_config()
    assert cfg.general.theme == "dark"
    assert cfg.path == isolated_home / "config.toml"
    assert not cfg.path.exists()


def test_save_and_reload(isolated_home: Path) -> None:
    cfg = load_config()
    cfg.general.theme = "light"
    cfg.tool("hello")["greeting"] = "hi"
    cfg.save()
    again = load_config()
    assert again.general.theme == "light"
    assert again.tool("hello") == {"greeting": "hi"}
    assert again.tool("unknown") == {}


def test_read_only_config_never_writes(isolated_home: Path) -> None:
    cfg = load_config()
    cfg.read_only = True
    cfg.general.theme = "light"
    cfg.save()
    assert not cfg.path.exists()


def test_unknown_general_keys_ignored(isolated_home: Path) -> None:
    paths.config_file().parent.mkdir(parents=True)
    paths.config_file().write_text('[general]\ntheme = "light"\nbogus = 1\n')
    assert load_config().general.theme == "light"


def test_default_output_dir(tmp_path: Path) -> None:
    assert paths.default_output_dir(tmp_path / "in.csv", "") == tmp_path
    assert paths.default_output_dir(None, str(tmp_path)) == tmp_path


def test_outputs_never_land_in_the_resources_folder(tmp_path: Path) -> None:
    root = tmp_path / "Resources"
    (root / "Python").mkdir(parents=True)
    inside = root / "Python" / "9a.py"
    inside.write_text("x = 1\n")
    out = paths.default_output_dir(inside, "", resources_root=str(root))
    assert out == paths.sessions_root("") / "outputs"
    assert not str(out).startswith(str(root))
    elsewhere = tmp_path / "other.py"
    assert paths.default_output_dir(elsewhere, "", resources_root=str(root)) == tmp_path
    assert (
        paths.default_output_dir(inside, str(tmp_path / "o"), resources_root=str(root))
        == tmp_path / "o"
    )
