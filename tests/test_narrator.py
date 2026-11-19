import json
from datetime import datetime, timezone
import pytest

from blackbox.events.narrator import narrate_event, narrate_events
from blackbox.events.rules import EventAction

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def test_narrate_gateway_down():
    # Open
    event_open = {
        "type": "gateway_down",
        "severity": "high",
        "title": "เน็ตหลุดที่ gateway",
        "details": "เราเตอร์ไม่ตอบ ping ต่อเนื่อง",
        "evidence": {"gateway": "192.168.1.1", "failures": 3},
        "ts_start": NOW.isoformat(),
        "ts_end": None,
    }
    msg = narrate_event(event_open)
    assert "192.168.1.1" in msg
    assert "3 ครั้ง" in msg or "ไม่ตอบสนอง" in msg

    # Recovered (ts_end present)
    event_close = dict(event_open, ts_end=NOW.isoformat(), evidence={"gateway": "192.168.1.1", "recovered": True})
    msg_close = narrate_event(event_close)
    assert "กลับมา" in msg_close
    assert "192.168.1.1" in msg_close


def test_narrate_internet_down():
    action = EventAction(
        action="open",
        type="internet_down",
        severity="high",
        title="อินเทอร์เน็ตหลุด",
        details="gateway ตอบ แต่ปลายทางอินเทอร์เน็ตไม่ตอบ",
        evidence={"targets": ["1.1.1.1", "8.8.8.8"], "failures": 3},
        ts=NOW,
    )
    msg = narrate_event(action)
    assert "อินเทอร์เน็ตหลุด" in msg
    assert "1.1.1.1" in msg

    action_close = EventAction(
        action="close",
        type="internet_down",
        severity="high",
        title="อินเทอร์เน็ตหลุด",
        details="",
        evidence={"recovered": True, "targets": ["1.1.1.1"]},
        ts=NOW,
    )
    msg_close = narrate_event(action_close)
    assert "กลับมา" in msg_close or "ปกติ" in msg_close


def test_narrate_dns_fail_and_slow():
    fail_event = {
        "type": "dns_fail",
        "evidence": {"resolvers": ["1.1.1.1", "8.8.8.8"]},
    }
    assert "1.1.1.1" in narrate_event(fail_event)

    slow_event = {
        "type": "dns_slow",
        "evidence": {"resolvers": ["1.1.1.1"], "latency_ms": 1250.0},
    }
    slow_msg = narrate_event(slow_event)
    assert "1250" in slow_msg
    assert "ช้า" in slow_msg


def test_narrate_wifi_drop():
    event_disconn = {
        "type": "wifi_drop",
        "evidence": {"state": "disconnected", "signal_pct": None},
    }
    assert "หลุด" in narrate_event(event_disconn)

    event_low = {
        "type": "wifi_drop",
        "evidence": {"state": "connected", "signal_pct": 25.0},
    }
    assert "25" in narrate_event(event_low)


def test_narrate_latency_spike():
    event = {
        "type": "latency_spike",
        "evidence": {"current_ms": 75.5, "baseline_ms": 15.0},
    }
    msg = narrate_event(event)
    assert "75.5" in msg
    assert "15.0" in msg


def test_narrate_packet_loss():
    event = {
        "type": "packet_loss",
        "evidence": {"loss_pct": 12.5, "samples": 40},
    }
    msg = narrate_event(event)
    assert "12.5%" in msg
    assert "40" in msg


def test_narrate_new_device():
    event = {
        "type": "new_device",
        "evidence": {"mac": "aa-bb-cc-dd-ee-ff", "ip": "192.168.1.50"},
    }
    msg = narrate_event(event)
    assert "aa-bb-cc-dd-ee-ff" in msg
    assert "192.168.1.50" in msg

    event_no_ip = {
        "type": "new_device",
        "evidence": json.dumps({"mac": "11-22-33-44-55-66"}),  # JSON string evidence test
    }
    msg_no_ip = narrate_event(event_no_ip)
    assert "11-22-33-44-55-66" in msg_no_ip


def test_narrate_public_ip_change():
    event = {
        "type": "public_ip_change",
        "evidence": {"old_ip": "203.0.113.1", "new_ip": "203.0.113.99"},
    }
    msg = narrate_event(event)
    assert "203.0.113.1" in msg
    assert "203.0.113.99" in msg


def test_narrate_interface_change():
    event = {
        "type": "interface_change",
        "evidence": {
            "old_interface": "Ethernet",
            "new_interface": "Wi-Fi",
            "old_gateway": "192.168.1.1",
            "new_gateway": "192.168.2.1",
        },
    }
    msg = narrate_event(event)
    assert "Ethernet" in msg
    assert "Wi-Fi" in msg


def test_narrate_monitor_gap():
    event = {
        "type": "monitor_gap",
        "evidence": {"gap_seconds": 120.0, "last_ts": "2026-11-19T12:00:00Z"},
    }
    msg = narrate_event(event)
    assert "120" in msg


def test_narrate_unknown_fallback():
    event = {
        "type": "custom_event",
        "title": "เหตุการณ์พิเศษ",
        "details": "รายละเอียดเพิ่มเติม",
        "evidence": {},
    }
    msg = narrate_event(event)
    assert "เหตุการณ์พิเศษ" in msg or "custom_event" in msg


def test_narrate_events_list():
    events = [
        {"type": "new_device", "evidence": {"mac": "aa-bb-cc-dd-ee-ff"}},
        {"type": "public_ip_change", "evidence": {"old_ip": "1.1.1.1", "new_ip": "2.2.2.2"}},
    ]
    lines = narrate_events(events)
    assert len(lines) == 2
    assert "aa-bb-cc-dd-ee-ff" in lines[0]
    assert "2.2.2.2" in lines[1]
