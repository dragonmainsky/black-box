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


def test_with_base_interval_derives_cadences(tmp_path):
    cfg = Config(data_dir=tmp_path).with_base_interval(120)
    assert cfg.base_interval_s == 120
    assert cfg.dns_interval_s == 240
    assert cfg.wifi_interval_s == 1200
    assert cfg.arp_interval_s == 1200
    assert cfg.public_ip_interval_s == 900
    cfg.validate()


def test_with_base_interval_10(tmp_path):
    cfg = Config(data_dir=tmp_path).with_base_interval(10)
    assert cfg.dns_interval_s == 20
    assert cfg.wifi_interval_s == 300
    assert cfg.arp_interval_s == 300
    assert cfg.public_ip_interval_s == 900
    cfg.validate()


def test_with_base_interval_300(tmp_path):
    cfg = Config(data_dir=tmp_path).with_base_interval(300)
    assert cfg.dns_interval_s == 600
    assert cfg.wifi_interval_s == 3000
    assert cfg.arp_interval_s == 3000
    assert cfg.public_ip_interval_s == 900
    cfg.validate()
