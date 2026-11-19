from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine

from blackbox.paths import db_path


def create_engine(data_dir: Path) -> Engine:
    engine = sa_create_engine(f"sqlite:///{db_path(data_dir)}")

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    from .migrate import run_migrations

    run_migrations(engine)
