from datetime import datetime, timedelta, timezone
from pathlib import Path

from blackbox.probe_types import ProbeResult
from blackbox.probes.arp import ArpEntry
from blackbox.status import get_system_status
from blackbox.store.db import create_engine, init_db
from blackbox.store.devices import upsert_devices
from blackbox.store.events import close_event, open_event
from blackbox.store.meta import meta_set
from blackbox.store.probes import insert_probes

BASE = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def _setup_engine(tmp_path: Path):
    engine = create_engine(tmp_path)
    init_db(engine)
    return engine


def test_status_empty(tmp_path: Path):
    engine = _setup_engine(tmp_path)
    status = get_system_status(engine)
    assert status.status == "unknown"
    assert status.status_text == "ยังไม่มีข้อมูล"
    assert status.open_events == []
    assert status.recent_events == []
    assert status.device_count == 0


def test_status_ok_when_probes_exist(tmp_path: Path):
    engine = _setup_engine(tmp_path)
    meta_set(engine, "last_interface", "Ethernet")
    meta_set(engine, "last_gateway", "192.168.1.1")
    meta_set(engine, "last_cycle", BASE.isoformat())
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="192.168.1.1", value=1.2, ok=True)],
        BASE,
    )
    upsert_devices(
        engine,
        [ArpEntry(ip="192.168.1.50", mac="AA:BB:CC:DD:EE:01", kind="dynamic")],
        BASE,
    )

    status = get_system_status(engine)
    assert status.status == "ok"
    assert status.status_text == "ปกติ"
    assert status.interface == "Ethernet"
    assert status.gateway == "192.168.1.1"
    assert status.device_count == 1
    assert status.open_events == []


def test_status_critical_on_high_severity_event(tmp_path: Path):
    engine = _setup_engine(tmp_path)
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="1.1.1.1", value=20.0, ok=True)],
        BASE,
    )
    open_event(
        engine,
        event_type="gateway_down",
        severity="high",
        title="เราเตอร์ไม่ตอบสนอง",
        details="ping ล้มเหลว",
        evidence={"gateway": "192.168.1.1", "failures": 3},
        ts=BASE,
    )

    status = get_system_status(engine)
    assert status.status == "critical"
    assert status.status_text == "วิกฤต"
    assert len(status.open_events) == 1
    assert "ไม่ตอบสนอง ping" in status.open_events[0]["narrative"]


def test_status_warning_on_medium_severity_event(tmp_path: Path):
    engine = _setup_engine(tmp_path)
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="1.1.1.1", value=20.0, ok=True)],
        BASE,
    )
    open_event(
        engine,
        event_type="wifi_drop",
        severity="medium",
        title="สัญญาณ Wi-Fi อ่อน",
        details="สัญญาณต่ำกว่า 30%",
        evidence={"signal_pct": 20},
        ts=BASE,
    )

    status = get_system_status(engine)
    assert status.status == "warning"
    assert status.status_text == "เตือน"
    assert len(status.open_events) == 1
    assert "อ่อนลงเหลือ 20%" in status.open_events[0]["narrative"]


def test_status_recovers_to_ok_when_events_closed(tmp_path: Path):
    engine = _setup_engine(tmp_path)
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="1.1.1.1", value=20.0, ok=True)],
        BASE,
    )
    ev_id = open_event(
        engine,
        event_type="internet_down",
        severity="high",
        title="อินเทอร์เน็ตหลุด",
        details="",
        evidence={"targets": ["1.1.1.1"], "failures": 3},
        ts=BASE - timedelta(minutes=5),
    )
    close_event(engine, ev_id, BASE)

    status = get_system_status(engine)
    assert status.status == "ok"
    assert status.status_text == "ปกติ"
    assert len(status.open_events) == 0
    assert len(status.recent_events) == 1
    assert "กลับมาใช้งานได้ตามปกติแล้ว" in status.recent_events[0]["narrative"]
