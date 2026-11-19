"""baseline schema — Phase 0

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "probes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.Text(), nullable=False),
        sa.Column("probe", sa.Text(), nullable=False),
        sa.Column("target", sa.Text()),
        sa.Column("value", sa.Float()),
        sa.Column("unit", sa.Text()),
        sa.Column("ok", sa.Integer(), nullable=False),
        sa.Column("interface", sa.Text()),
        sa.Column("text_value", sa.Text()),
        sa.Column("detail", sa.Text()),
        sa.Column("error_kind", sa.Text()),
    )
    op.create_index("idx_probes_probe_time", "probes", ["probe", "ts"])
    op.create_index("idx_probes_time", "probes", ["ts"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts_start", sa.Text(), nullable=False),
        sa.Column("ts_end", sa.Text()),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default="info"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("evidence", sa.Text()),
    )
    op.create_index("idx_events_time_sev", "events", ["ts_start", "severity"])
    op.create_index("idx_events_type", "events", ["type"])

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mac", sa.Text(), nullable=False, unique=True),
        sa.Column("ip", sa.Text()),
        sa.Column("vendor", sa.Text()),
        sa.Column("name", sa.Text()),
        sa.Column("first_seen", sa.Text(), nullable=False),
        sa.Column("last_seen", sa.Text(), nullable=False),
    )

    op.create_table(
        "probe_rollup",
        sa.Column("hour", sa.Text(), primary_key=True),
        sa.Column("probe", sa.Text(), primary_key=True),
        sa.Column("target", sa.Text(), primary_key=True, nullable=False),
        sa.Column("avg_value", sa.Float()),
        sa.Column("min_value", sa.Float()),
        sa.Column("max_value", sa.Float()),
        sa.Column("loss_pct", sa.Float()),
        sa.Column("samples", sa.Integer(), nullable=False),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("period_start", sa.Text(), nullable=False),
        sa.Column("period_end", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
    )

    op.create_table(
        "meta",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("meta")
    op.drop_table("reports")
    op.drop_table("probe_rollup")
    op.drop_table("devices")
    op.drop_table("events")
    op.drop_table("probes")
