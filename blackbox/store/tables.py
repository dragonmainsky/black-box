from __future__ import annotations

from sqlalchemy import Column, Float, Index, Integer, MetaData, Table, Text

metadata = MetaData()

probes = Table(
    "probes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ts", Text, nullable=False),
    Column("probe", Text, nullable=False),
    Column("target", Text),
    Column("value", Float),
    Column("unit", Text),
    Column("ok", Integer, nullable=False),
    Column("interface", Text),
    Column("text_value", Text),
    Column("detail", Text),
    Column("error_kind", Text),
)
Index("idx_probes_probe_time", probes.c.probe, probes.c.ts)
Index("idx_probes_time", probes.c.ts)

events = Table(
    "events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("ts_start", Text, nullable=False),
    Column("ts_end", Text),
    Column("type", Text, nullable=False),
    Column("severity", Text, nullable=False, server_default="info"),
    Column("title", Text, nullable=False),
    Column("details", Text),
    Column("evidence", Text),
)
Index("idx_events_time_sev", events.c.ts_start, events.c.severity)
Index("idx_events_type", events.c.type)

devices = Table(
    "devices",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("mac", Text, nullable=False, unique=True),
    Column("ip", Text),
    Column("vendor", Text),
    Column("name", Text),
    Column("first_seen", Text, nullable=False),
    Column("last_seen", Text, nullable=False),
)

probe_rollup = Table(
    "probe_rollup",
    metadata,
    Column("hour", Text, primary_key=True),
    Column("probe", Text, primary_key=True),
    Column("target", Text, primary_key=True, nullable=False),
    Column("avg_value", Float),
    Column("min_value", Float),
    Column("max_value", Float),
    Column("loss_pct", Float),
    Column("samples", Integer, nullable=False),
)

reports = Table(
    "reports",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("created_at", Text, nullable=False),
    Column("period_start", Text, nullable=False),
    Column("period_end", Text, nullable=False),
    Column("path", Text, nullable=False),
)

meta = Table(
    "meta",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=False),
)
