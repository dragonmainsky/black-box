from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from .tables import meta


def meta_get(engine: Engine, key: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(select(meta.c.value).where(meta.c.key == key)).first()
        return row[0] if row else None


def meta_set(engine: Engine, key: str, value: str) -> None:
    with engine.begin() as conn:
        stmt = sqlite_insert(meta).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(index_elements=[meta.c.key], set_={"value": value})
        conn.execute(stmt)
