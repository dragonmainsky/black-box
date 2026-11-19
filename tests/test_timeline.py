from datetime import datetime, timedelta, timezone

from blackbox.timeline import build_buckets

BASE = datetime(2026, 11, 19, 0, 0, tzinfo=timezone.utc)


def _event(ts, severity, event_type):
    return {
        "ts_start": ts.isoformat(),
        "ts_end": (ts + timedelta(minutes=5)).isoformat(),
        "severity": severity,
        "type": event_type,
    }


def test_day_buckets_include_empty_days():
    events = [
        _event(BASE + timedelta(hours=1), "high", "dns_fail"),
        _event(BASE + timedelta(days=1, hours=2), "medium", "wifi_drop"),
    ]
    buckets = build_buckets(events, BASE, BASE + timedelta(days=2), "day")
    assert len(buckets) == 2
    assert buckets[0]["event_count"] == 1
    assert buckets[0]["max_severity"] == "high"
    assert buckets[1]["max_severity"] == "medium"


def test_hour_buckets():
    events = [_event(BASE + timedelta(hours=3, minutes=10), "low", "new_device")]
    buckets = build_buckets(events, BASE, BASE + timedelta(hours=4), "hour")
    assert len(buckets) == 4
    assert buckets[3]["event_count"] == 1
    assert buckets[3]["max_severity"] == "low"


def test_month_buckets():
    events = [_event(BASE, "high", "dns_fail")]
    buckets = build_buckets(events, BASE, BASE + timedelta(days=60), "month")
    assert len(buckets) == 3
    assert buckets[0]["max_severity"] == "high"
