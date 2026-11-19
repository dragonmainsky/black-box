import pytest

pytest.importorskip("pystray")

from blackbox.desktop import (
    create_icon,
    desktop_url,
    free_port,
    read_runtime,
    remove_runtime,
    wait_for_stop,
    write_runtime,
)


def test_free_port_returns_port():
    port = free_port()
    assert isinstance(port, int)
    assert 1024 < port < 65536


def test_icon_is_64px():
    assert create_icon().size == (64, 64)


def test_desktop_url_contains_token():
    assert desktop_url(8765, "abc") == "http://127.0.0.1:8765/?token=abc"


def test_wait_for_stop_handles_keyboard_interrupt():
    class InterruptingEvent:
        def wait(self, timeout):
            raise KeyboardInterrupt

    wait_for_stop(InterruptingEvent())


def test_runtime_roundtrip(tmp_path):
    write_runtime(tmp_path, 8888)
    runtime = read_runtime(tmp_path)
    assert runtime["port"] == 8888
    assert isinstance(runtime["pid"], int)
    remove_runtime(tmp_path)
    assert read_runtime(tmp_path) is None
