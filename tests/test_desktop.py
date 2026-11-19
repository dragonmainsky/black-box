import pytest

pytest.importorskip("webview")
pytest.importorskip("pystray")

from blackbox.desktop import create_icon, free_port


def test_free_port_returns_port():
    port = free_port()
    assert isinstance(port, int)
    assert 1024 < port < 65536


def test_icon_is_64px():
    assert create_icon().size == (64, 64)
