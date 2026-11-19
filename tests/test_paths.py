from pathlib import Path

from blackbox.paths import app_home, db_path, resolve_data_dir


def test_resolve_data_dir_override(tmp_path: Path):
    target = tmp_path / "data"
    assert resolve_data_dir(str(target)) == target
    assert target.is_dir()


def test_app_home_uses_appdata(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert app_home() == tmp_path / "BlackBox"


def test_db_path_is_inside_data_dir(tmp_path: Path):
    assert db_path(tmp_path) == tmp_path / "black_box.db"
