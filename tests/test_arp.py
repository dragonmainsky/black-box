from datetime import datetime, timezone
from pathlib import Path

from blackbox.probes.arp import parse_arp_table, probe_arp
from blackbox.store.db import create_engine, init_db
from blackbox.store.devices import upsert_devices

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_english_table():
    entries = parse_arp_table((FIXTURES / "arp_en.txt").read_text(encoding="utf-8"))
    assert entries[0].ip == "192.168.1.1"
    assert entries[0].mac == "aa-bb-cc-dd-ee-ff"


def test_parse_thai_table():
    entries = parse_arp_table((FIXTURES / "arp_th.txt").read_text(encoding="utf-8"))
    assert any(e.ip == "192.168.1.10" for e in entries)


def test_probe_summary_row():
    output = (FIXTURES / "arp_en.txt").read_text(encoding="utf-8")
    sweep = probe_arp(run_fn=lambda: (0, output, ""))
    assert sweep.result.probe == "arp"
    assert sweep.result.value == len(sweep.entries)
    assert sweep.result.ok is True


def test_upsert_devices_tracks_seen(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    ts = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
    output = (FIXTURES / "arp_en.txt").read_text(encoding="utf-8")
    entries = parse_arp_table(output)
    assert upsert_devices(engine, entries, ts) >= 1
    assert upsert_devices(engine, entries, ts) >= 0
