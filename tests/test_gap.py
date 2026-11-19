from datetime import datetime, timedelta, timezone

from blackbox.events.gap import record_gap_if_needed
from blackbox.store.db import create_engine, init_db
from blackbox.store.events import recent_events

BASE = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def test_no_gap_when_within_two_intervals(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    assert record_gap_if_needed(engine, BASE, BASE + timedelta(seconds=59), 30) is None


def test_gap_creates_one_event(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    gap_id = record_gap_if_needed(engine, BASE, BASE + timedelta(minutes=10), 30)
    assert gap_id is not None
    events = recent_events(engine)
    assert len(events) == 1
    assert events[0]["type"] == "monitor_gap"
    assert events[0]["severity"] == "medium"


def test_repeated_gap_creates_separate_events(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    first = record_gap_if_needed(engine, BASE, BASE + timedelta(minutes=10), 30)
    second = record_gap_if_needed(
        engine, BASE + timedelta(minutes=10), BASE + timedelta(minutes=20), 30
    )
    assert first != second
    assert len(recent_events(engine)) == 2


def test_duplicate_gap_is_not_recorded_twice(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    first = record_gap_if_needed(engine, BASE, BASE + timedelta(minutes=10), 30)
    second = record_gap_if_needed(engine, BASE, BASE + timedelta(minutes=10), 30)
    assert first is not None
    assert second is None
    assert len(recent_events(engine)) == 1


def test_backward_clock_is_ignored(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    assert (
        record_gap_if_needed(
            engine, BASE, BASE - timedelta(minutes=1), 30
        )
        is None
    )
