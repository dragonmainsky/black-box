from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy.engine import Engine

from blackbox.config import Config
from blackbox.store.meta import meta_get, meta_set

_PREFIX = "settings."


@dataclass(frozen=True)
class Settings:
    base_interval_s: int = 30
    retention_days: int = 30
    public_ip_enabled: bool = False

    def validate(self) -> None:
        if not 10 <= self.base_interval_s <= 3600:
            raise ValueError("base_interval_s ต้องอยู่ระหว่าง 10–3600")
        if not 1 <= self.retention_days <= 3650:
            raise ValueError("retention_days ต้องอยู่ระหว่าง 1–3650")

    def to_dict(self) -> dict:
        return asdict(self)


def _read_int(engine: Engine, key: str, default: int) -> int:
    raw = meta_get(engine, _PREFIX + key)
    if raw in (None, ""):
        return default
    return int(raw)


def _read_bool(engine: Engine, key: str, default: bool) -> bool:
    raw = meta_get(engine, _PREFIX + key)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def load_settings(engine: Engine) -> Settings:
    settings = Settings(
        base_interval_s=_read_int(engine, "base_interval_s", 30),
        retention_days=_read_int(engine, "retention_days", 30),
        public_ip_enabled=_read_bool(engine, "public_ip_enabled", False),
    )
    try:
        settings.validate()
    except (TypeError, ValueError):
        return Settings()
    return settings


def save_settings(engine: Engine, settings: Settings) -> None:
    settings.validate()
    meta_set(engine, _PREFIX + "base_interval_s", str(settings.base_interval_s))
    meta_set(engine, _PREFIX + "retention_days", str(settings.retention_days))
    meta_set(
        engine,
        _PREFIX + "public_ip_enabled",
        "1" if settings.public_ip_enabled else "0",
    )


def config_from_settings(data_dir: Path, settings: Settings) -> Config:
    settings.validate()
    config = Config(
        data_dir=data_dir,
        base_interval_s=settings.base_interval_s,
        retention_days=settings.retention_days,
        public_ip_enabled=settings.public_ip_enabled,
    )
    config = config.with_base_interval(settings.base_interval_s)
    config.validate()
    return config
