from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

_SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}
_RANK_SEVERITY = {rank: name for name, rank in _SEVERITY_RANK.items()}


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def _floor(ts: datetime, bucket: str) -> datetime:
    if bucket == "hour":
        return ts.replace(minute=0, second=0, microsecond=0)
    if bucket == "day":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    if bucket == "month":
        return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError("bucket ต้องเป็น hour, day หรือ month")


def _next(ts: datetime, bucket: str) -> datetime:
    if bucket == "hour":
        return ts + timedelta(hours=1)
    if bucket == "day":
        return ts + timedelta(days=1)
    if ts.month == 12:
        return ts.replace(year=ts.year + 1, month=1)
    return ts.replace(month=ts.month + 1)


def build_buckets(
    events: Sequence[dict],
    start: datetime,
    end: datetime,
    bucket: str = "day",
) -> list[dict]:
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    cursor = _floor(start, bucket)

    buckets: list[dict] = []
    index: dict[str, dict] = {}
    while cursor < end:
        following = _next(cursor, bucket)
        item = {
            "start": cursor.isoformat(),
            "end": following.isoformat(),
            "event_count": 0,
            "max_severity": None,
            "types": [],
        }
        buckets.append(item)
        index[cursor.isoformat()] = item
        cursor = following

    for event in events:
        ts = _parse(event["ts_start"])
        target = index.get(_floor(ts, bucket).isoformat())
        if target is None:
            continue
        target["event_count"] += 1

        severity = event.get("severity", "info")
        rank = _SEVERITY_RANK.get(severity, 0)
        current_rank = _SEVERITY_RANK.get(target["max_severity"], -1)
        if rank > current_rank:
            target["max_severity"] = _RANK_SEVERITY[rank]

        event_type = event.get("type")
        if event_type and event_type not in target["types"]:
            target["types"].append(event_type)

    return buckets
