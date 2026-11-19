from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.engine import Engine

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def run_migrations(engine: Engine) -> None:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.attributes["connection"] = engine
    command.upgrade(cfg, "head")
