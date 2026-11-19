from pathlib import Path

from blackbox.cli import main


def test_db_init_creates_database(tmp_path: Path):
    assert main(["db", "init", "--data-dir", str(tmp_path)]) == 0
    assert (tmp_path / "black_box.db").is_file()


def test_show_recent_empty(tmp_path: Path, capsys):
    main(["db", "init", "--data-dir", str(tmp_path)])
    assert main(["show", "recent", "--data-dir", str(tmp_path)]) == 0
    assert "ยังไม่มี" in capsys.readouterr().out


def test_probe_once_returns_zero(tmp_path: Path, monkeypatch):
    calls = {"n": 0}

    class FakeRunner:
        def __init__(self, engine, config):
            pass

        def run_once(self, now=None):
            calls["n"] += 1
            return []

    monkeypatch.setattr("blackbox.cli.ProbeRunner", FakeRunner)
    assert main(["probe", "once", "--data-dir", str(tmp_path)]) == 0
    assert calls["n"] == 1
