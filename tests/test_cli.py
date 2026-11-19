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


def test_show_recent_displays_narrative(tmp_path: Path, capsys):
    from datetime import datetime, timezone

    from blackbox.store.db import create_engine
    from blackbox.store.events import open_event

    base = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    main(["db", "init", "--data-dir", str(tmp_path)])
    engine = create_engine(tmp_path)
    open_event(
        engine,
        event_type="gateway_down",
        severity="high",
        title="เน็ตหลุดที่ gateway",
        details="เราเตอร์ไม่ตอบ ping",
        evidence={"gateway": "192.168.1.1", "failures": 3},
        ts=base,
    )

    assert main(["show", "recent", "--data-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "gateway_down" in out
    assert "เราเตอร์ (gateway 192.168.1.1) ไม่ตอบสนอง ping" in out


def test_show_status_empty(tmp_path: Path, capsys):
    main(["db", "init", "--data-dir", str(tmp_path)])
    assert main(["show", "status", "--data-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "ยังไม่มีข้อมูล" in out


def test_show_status_healthy(tmp_path: Path, capsys):
    from datetime import datetime, timezone

    from blackbox.probe_types import ProbeResult
    from blackbox.store.db import create_engine
    from blackbox.store.meta import meta_set
    from blackbox.store.probes import insert_probes

    base = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    main(["db", "init", "--data-dir", str(tmp_path)])
    engine = create_engine(tmp_path)
    meta_set(engine, "last_interface", "Wi-Fi")
    meta_set(engine, "last_gateway", "192.168.1.1")
    meta_set(engine, "last_cycle", base.isoformat())
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="192.168.1.1", value=2.5, ok=True)],
        base,
    )

    assert main(["show", "status", "--data-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "สถานะเครือข่าย: ปกติ" in out
    assert "Interface : Wi-Fi" in out
    assert "Gateway   : 192.168.1.1" in out
    assert "ไม่มี (เครือข่ายปกติ)" in out


def test_show_status_with_active_and_recent_events(tmp_path: Path, capsys):
    from datetime import datetime, timedelta, timezone

    from blackbox.probe_types import ProbeResult
    from blackbox.store.db import create_engine
    from blackbox.store.events import close_event, open_event
    from blackbox.store.probes import insert_probes

    base = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    main(["db", "init", "--data-dir", str(tmp_path)])
    engine = create_engine(tmp_path)
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="1.1.1.1", value=15.0, ok=True)],
        base,
    )
    # Closed event in history
    ev_id = open_event(
        engine,
        event_type="dns_slow",
        severity="medium",
        title="DNS ตอบสนองช้า",
        details="",
        evidence={"latency_ms": 1200, "resolvers": ["1.1.1.1"]},
        ts=base - timedelta(minutes=10),
    )
    close_event(engine, ev_id, base - timedelta(minutes=8))

    # Active open event
    open_event(
        engine,
        event_type="gateway_down",
        severity="high",
        title="เราเตอร์ไม่ตอบสนอง",
        details="",
        evidence={"gateway": "192.168.1.1", "failures": 3},
        ts=base,
    )

    assert main(["show", "status", "--data-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "สถานะเครือข่าย: วิกฤต" in out
    assert "gateway_down" in out
    assert "เราเตอร์ (gateway 192.168.1.1) ไม่ตอบสนอง ping" in out
    assert "dns_slow" in out
    assert "DNS" in out
