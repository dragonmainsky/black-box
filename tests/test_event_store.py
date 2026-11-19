from datetime import datetime, timezone

from blackbox.store.db import create_engine, init_db
from blackbox.store.events import close_event, find_open_event, open_event

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def test_open_event_and_find_open(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    event_id = open_event(
        engine,
        "dns_fail",
        "high",
        "DNS ล่ม",
        "DNS resolver ตอบไม่ได้",
        {"resolvers": ["1.1.1.1"]},
        NOW,
    )
    found = find_open_event(engine, "dns_fail")
    assert found is not None
    assert found["id"] == event_id
    assert found["severity"] == "high"
    assert found["evidence"] == {"resolvers": ["1.1.1.1"]}


def test_close_event_removes_from_open(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    event_id = open_event(
        engine, "gateway_down", "high", "gateway ล่ม", "details", {}, NOW
    )
    close_event(engine, event_id, NOW)
    assert find_open_event(engine, "gateway_down") is None
