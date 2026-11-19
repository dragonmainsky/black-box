from datetime import timedelta, timezone

from blackbox.cli import format_range, format_ts

TZ7 = timezone(timedelta(hours=7))

def test_format_ts_uses_local_timezone():
    assert format_ts("2026-11-19T11:42:29+00:00", TZ7) == "19 พ.ย. 2026 18:42:29"

def test_format_range_includes_duration():
    text = format_range(
        "2026-11-19T11:42:29+00:00",
        "2026-11-19T11:43:47+00:00",
        TZ7,
    )
    assert text == "19 พ.ย. 2026 18:42:29–18:43:47 (1 นาที 18 วิ)"