import pytest

from blackbox.config import Config


def test_config_defaults(tmp_path):
    cfg = Config(data_dir=tmp_path)
    assert cfg.base_interval_s == 30
    assert cfg.public_ip_enabled is False
    assert cfg.targets == ("1.1.1.1", "8.8.8.8")


def test_config_rejects_short_interval(tmp_path):
    with pytest.raises(ValueError):
        Config(data_dir=tmp_path, base_interval_s=5).validate()


def test_config_rejects_retention_out_of_range(tmp_path):
    with pytest.raises(ValueError):
        Config(data_dir=tmp_path, retention_days=0).validate()
    with pytest.raises(ValueError):
        Config(data_dir=tmp_path, rollup_retention_days=4000).validate()


def test_config_rejects_unknown_target(tmp_path):
    with pytest.raises(ValueError):
        Config(data_dir=tmp_path, targets=("9.9.9.9",)).validate()
