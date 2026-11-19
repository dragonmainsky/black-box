from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from blackbox.probes.arp import ArpEntry

from .tables import devices


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat()


def upsert_devices(
    engine: Engine, entries: Sequence[ArpEntry], seen_at: datetime
) -> list[str]:
    if not entries:
        return []
    now = _iso(seen_at)
    cleaned_entries: list[tuple[str, ArpEntry]] = []
    seen_macs: set[str] = set()
    for entry in entries:
        mac = entry.mac.lower().replace(":", "-")
        if mac not in seen_macs:
            seen_macs.add(mac)
            cleaned_entries.append((mac, entry))

    new_macs: list[str] = []
    with engine.begin() as conn:
        all_macs = [mac for mac, _ in cleaned_entries]
        existing = set(
            conn.execute(
                select(devices.c.mac).where(devices.c.mac.in_(all_macs))
            ).scalars().all()
        )
        for mac, entry in cleaned_entries:
            if mac not in existing:
                new_macs.append(mac)
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
    return new_macs
