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


def test_probe_loop_accepts_interval_above_60(tmp_path: Path, monkeypatch):
    seen = {}

    class FakeRunner:
        def __init__(self, engine, config):
            seen["config"] = config

        def run_forever(self):
            return None

    monkeypatch.setattr("blackbox.cli.ProbeRunner", FakeRunner)
    assert (
        main(
            [
                "probe",
                "loop",
                "--interval",
                "120",
                "--data-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    assert seen["config"].base_interval_s == 120
    assert seen["config"].dns_interval_s == 240


def test_show_recent_merges_timeline(tmp_path: Path, capsys):
    from datetime import datetime, timedelta, timezone

    from blackbox.probe_types import ProbeResult
    from blackbox.store.db import create_engine
    from blackbox.store.events import insert_gap
    from blackbox.store.probes import insert_probes

    base = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    main(["db", "init", "--data-dir", str(tmp_path)])
    engine = create_engine(tmp_path)
    insert_probes(
        engine,
        [ProbeResult(probe="wifi", target="ssid", text_value="HomeNet", ok=True)],
        base,
    )
    insert_gap(
        engine, base - timedelta(minutes=5), base - timedelta(minutes=1), 240
    )

    assert main(["show", "recent", "--data-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "HomeNet" in out
    assert "monitor_gap" in out
    assert out.index("HomeNet") < out.index("monitor_gap")


def test_probe_once_returns_two_on_failure(tmp_path: Path, monkeypatch):
    from blackbox.probe_types import ProbeResult

    class FakeRunner:
        def __init__(self, engine, config):
            pass

        def run_once(self, now=None):
            return [
                ProbeResult(
                    probe="ping", target="1.1.1.1", ok=False, error_kind="network"
                )
            ]

    monkeypatch.setattr("blackbox.cli.ProbeRunner", FakeRunner)
    assert main(["probe", "once", "--data-dir", str(tmp_path)]) == 2
