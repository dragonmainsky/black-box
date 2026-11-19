from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from blackbox.probes.arp import ArpEntry

from .tables import devices


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def upsert_devices(
    engine: Engine, entries: Sequence[ArpEntry], seen_at: datetime
) -> int:
    if not entries:
        return 0
    now = _iso(seen_at)
    count = 0
    with engine.begin() as conn:
        for entry in entries:
            mac = entry.mac.lower().replace(":", "-")
            stmt = sqlite_insert(devices).values(
                mac=mac,
                ip=entry.ip,
                vendor=None,
                name=None,
                first_seen=now,
                last_seen=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[devices.c.mac],
                set_={"ip": entry.ip, "last_seen": now},
            )
            conn.execute(stmt)
            count += 1
    return count
