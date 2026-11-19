from datetime import datetime, timedelta, timezone

from blackbox.config import Config
from blackbox.probes.runner import ProbeRunner
from blackbox.store.db import create_engine, init_db
from blackbox.store.probes import recent_probes

BASE = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def _runner(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    cfg = Config(data_dir=tmp_path)
    return ProbeRunner(
        engine,
        cfg,
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
