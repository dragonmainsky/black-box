import pytest

from blackbox.settings import Settings, config_from_settings, load_settings, save_settings
from blackbox.store.db import create_engine, init_db


def test_settings_defaults(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    settings = load_settings(engine)
    assert settings.base_interval_s == 30
    assert settings.retention_days == 30
    assert settings.public_ip_enabled is False


def test_settings_save_and_load(tmp_path):
    engine = create_engine(tmp_path)
    init_db(engine)
    save_settings(
        engine,
        Settings(
            base_interval_s=60,
            retention_days=90,
            public_ip_enabled=True,
        ),
    )
    loaded = load_settings(engine)
    assert loaded.base_interval_s == 60
    assert loaded.retention_days == 90
    assert loaded.public_ip_enabled is True


def test_settings_validation(tmp_path):
    with pytest.raises(ValueError):
        Settings(base_interval_s=5).validate()
    with pytest.raises(ValueError):
        Settings(retention_days=0).validate()
    with pytest.raises(ValueError):
        Settings(retention_days=4000).validate()


def test_config_from_settings(tmp_path):
    settings = Settings(
        base_interval_s=120,
        retention_days=60,
        public_ip_enabled=True,
    )
    config = config_from_settings(tmp_path, settings)
    assert config.base_interval_s == 120
    assert config.dns_interval_s == 240
    assert config.retention_days == 60
    assert config.public_ip_enabled is True
    config.validate()
