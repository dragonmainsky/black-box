from datetime import datetime, timedelta, timezone

import pytest

from blackbox.config import Config
from blackbox.probe_types import ProbeResult
from blackbox.probes.runner import ProbeRunner, summarize_cycle
from blackbox.store.db import create_engine, init_db
from blackbox.store.events import find_open_event, recent_events
from blackbox.store.meta import meta_get, meta_set
from blackbox.store.probes import recent_probes

BASE = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def _runner(tmp_path, **overrides):
    engine = create_engine(tmp_path)
    init_db(engine)
    cfg = Config(data_dir=tmp_path)
    kwargs = dict(
        interface_fn=lambda: None,
        dns_servers_fn=lambda alias: ["1.1.1.1"],
        ping_sender=type("S", (), {"send": lambda self, t, ms: 10.0})(),
        dns_resolver_fn=lambda r, d, t: type(
            "A",
            (),
            {
                "resolver": r,
                "rcode": "NOERROR",
                "answers": ["1.2.3.4"],
                "latency_ms": 5.0,
            },
        )(),
        wifi_run_fn=lambda: (1, "", "no wifi"),
        arp_run_fn=lambda: (0, "", ""),
    )
    kwargs.update(overrides)
    return ProbeRunner(engine, cfg, **kwargs)


def test_run_once_writes_probe_rows(tmp_path):
    runner = _runner(tmp_path)
    results = runner.run_once(BASE)
    assert any(r.probe == "ping" for r in results)
    assert len(recent_probes(runner.engine, limit=100)) >= 3


def test_run_cycle_writes_gap_on_startup(tmp_path):
    runner = _runner(tmp_path)
    runner.run_cycle(BASE)
    runner.run_cycle(BASE + timedelta(minutes=10))
    types = [e["type"] for e in runner.recent_events()]
    assert "monitor_gap" in types


def test_run_once_stamps_interface(tmp_path):
    from blackbox.probes.netif import InterfaceInfo

    engine = create_engine(tmp_path)
    init_db(engine)
    cfg = Config(data_dir=tmp_path)
    runner = ProbeRunner(
        engine,
        cfg,
        interface_fn=lambda: InterfaceInfo("Ethernet", 5, "192.168.1.1", False),
        dns_servers_fn=lambda alias: ["1.1.1.1"],
        ping_sender=type("S", (), {"send": lambda self, t, ms: 10.0})(),
        dns_resolver_fn=lambda r, d, t: type(
            "A",
            (),
            {
                "resolver": r,
                "rcode": "NOERROR",
                "answers": ["1.2.3.4"],
                "latency_ms": 5.0,
            },
        )(),
        wifi_run_fn=lambda: (1, "", "no wifi"),
        arp_run_fn=lambda: (0, "", ""),
    )
    results = runner.run_once(BASE)
    assert results
    assert all(r.interface == "Ethernet" for r in results)


def test_run_once_skips_public_ip_by_default(tmp_path):
    runner = _runner(tmp_path)
    results = runner.run_once(BASE)
    assert all(r.probe != "public_ip" for r in results)


def test_run_once_does_not_update_last_cycle(tmp_path):
    runner = _runner(tmp_path)
    runner.run_once(BASE)
    assert meta_get(runner.engine, "last_cycle") is None


def test_run_forever_loops_until_keyboard_interrupt(tmp_path):
    runner = _runner(tmp_path)
    runner._maybe_maintenance = lambda now: None
    calls = []

    def fake_cycle(now):
        calls.append(now)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return []

    runner.run_cycle = fake_cycle
    sleeps = []
    runner.sleep_fn = lambda seconds: sleeps.append(seconds)
    with pytest.raises(KeyboardInterrupt):
        runner.run_forever()
    assert len(calls) == 2
    assert len(sleeps) == 1


def test_maintenance_runs_on_startup_and_not_again(tmp_path, monkeypatch):
    runner = _runner(tmp_path)
    calls = []

    def fake(engine, now, **kwargs):
        calls.append(now)
        meta_set(engine, "last_maintenance", now.isoformat())
        return {}

    monkeypatch.setattr("blackbox.probes.runner.run_maintenance", fake)
    runner._maybe_maintenance(BASE)
    runner._maybe_maintenance(BASE + timedelta(hours=1))
    assert len(calls) == 1
    runner._maybe_maintenance(BASE + timedelta(hours=7))
    assert len(calls) == 2


def test_run_once_includes_wifi_when_monitored(tmp_path):
    from pathlib import Path

    from blackbox.probes.netif import InterfaceInfo

    output = (Path(__file__).parent / "fixtures" / "netsh_wifi_en.txt").read_text(
        encoding="utf-8"
    )
    runner = _runner(
        tmp_path,
        interface_fn=lambda: InterfaceInfo("Wi-Fi", 19, "192.168.1.1", True),
        wifi_run_fn=lambda: (0, output, ""),
    )
    results = runner.run_once(BASE)
    assert any(result.probe == "wifi" for result in results)


def test_run_once_opens_gateway_down_event(tmp_path):
    from blackbox.probes.netif import InterfaceInfo

    class GatewayDown:
        def send(self, target, timeout_ms):
            return None if target == "192.168.1.1" else 10.0

    runner = _runner(
        tmp_path,
        interface_fn=lambda: InterfaceInfo("Ethernet", 5, "192.168.1.1", False),
        ping_sender=GatewayDown(),
    )
    for _ in range(3):
        runner.run_once(BASE)
    event = find_open_event(runner.engine, "gateway_down")
    assert event is not None
    assert event["severity"] == "high"


def test_run_once_closes_gateway_down_event(tmp_path):
    from blackbox.probes.netif import InterfaceInfo

    class Toggle:
        fail = True

        def send(self, target, timeout_ms):
            if target == "192.168.1.1" and self.fail:
                return None
            return 10.0

    sender = Toggle()
    runner = _runner(
        tmp_path,
        interface_fn=lambda: InterfaceInfo("Ethernet", 5, "192.168.1.1", False),
        ping_sender=sender,
    )
    for _ in range(3):
        runner.run_once(BASE)
    assert find_open_event(runner.engine, "gateway_down") is not None

    sender.fail = False
    runner.run_once(BASE)
    assert find_open_event(runner.engine, "gateway_down") is None
    assert any(
        event["type"] == "gateway_down" and event["ts_end"]
        for event in recent_events(runner.engine)
    )


def test_run_once_opens_dns_fail_event(tmp_path):
    def broken(resolver, domain, timeout_s):
        raise OSError("dns down")

    runner = _runner(tmp_path, dns_resolver_fn=broken)
    for _ in range(2):
        runner.run_once(BASE)
    assert find_open_event(runner.engine, "dns_fail") is not None


def test_run_once_opens_packet_loss_event(tmp_path):
    from blackbox.probes.netif import InterfaceInfo

    class InternetLoss:
        def send(self, target, timeout_ms):
            return 10.0 if target == "192.168.1.1" else None

    runner = _runner(
        tmp_path,
        interface_fn=lambda: InterfaceInfo("Ethernet", 5, "192.168.1.1", False),
        ping_sender=InternetLoss(),
    )
    for _ in range(10):
        runner.run_once(BASE)
    assert find_open_event(runner.engine, "packet_loss") is not None


def test_summarize_cycle_counts():
    results = [
        ProbeResult(probe="ping", target="1.1.1.1", ok=True),
        ProbeResult(
            probe="dns", target="1.1.1.1", ok=False, error_kind="network"
        ),
    ]
    text = summarize_cycle(results)
    assert "ping 1" in text
    assert "dns 1" in text
    assert "fail 1" in text
    assert "network" in text


def test_run_forever_prints_start_and_cycle(tmp_path, capsys):
    runner = _runner(tmp_path)
    runner._maybe_maintenance = lambda now: None
    calls = []

    def fake_cycle(now):
        calls.append(now)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return [ProbeResult(probe="ping", target="1.1.1.1", value=10.0, ok=True)]

    runner.run_cycle = fake_cycle
    runner.sleep_fn = lambda seconds: None
    with pytest.raises(KeyboardInterrupt):
        runner.run_forever()
    out = capsys.readouterr().out
    assert "เริ่มเฝ้าระวัง" in out
    assert "ping 1" in out
