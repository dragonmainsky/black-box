from datetime import datetime, timedelta, timezone

from blackbox.probe_types import ProbeResult
from blackbox.store.db import create_engine, init_db
from blackbox.store.events import events_between, open_event
from blackbox.store.probes import insert_probes, probes_between

BASE = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def test_events_between_filters_by_time_and_type(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    open_event(engine, "dns_fail", "high", "DNS ล่ม", "", {}, BASE)
    open_event(engine, "wifi_drop", "medium", "Wi-Fi", "", {}, BASE + timedelta(hours=1))
    open_event(engine, "dns_fail", "high", "DNS ล่ม", "", {}, BASE - timedelta(days=1))

    events = events_between(
        engine, BASE - timedelta(minutes=1), BASE + timedelta(hours=2)
    )
    assert len(events) == 2
    assert events[0]["type"] == "dns_fail"

    filtered = events_between(
        engine,
        BASE - timedelta(minutes=1),
        BASE + timedelta(hours=2),
        event_type="wifi_drop",
    )
    assert len(filtered) == 1
    assert filtered[0]["type"] == "wifi_drop"


def test_probes_between_filters_by_time_and_probe(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    insert_probes(
        engine,
        [
            ProbeResult(probe="ping", target="1.1.1.1", value=10.0, ok=True),
            ProbeResult(probe="dns", target="1.1.1.1", value=20.0, ok=True),
        ],
        BASE,
    )
    insert_probes(
        engine,
        [ProbeResult(probe="ping", target="1.1.1.1", value=30.0, ok=True)],
        BASE - timedelta(days=1),
    )

    rows = probes_between(
        engine, BASE - timedelta(minutes=1), BASE + timedelta(minutes=1)
    )
    assert len(rows) == 2

    pings = probes_between(
        engine,
        BASE - timedelta(minutes=1),
        BASE + timedelta(minutes=1),
        probe="ping",
    )
    assert len(pings) == 1
    assert pings[0]["value"] == 10.0
