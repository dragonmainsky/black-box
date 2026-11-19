from __future__ import annotations

import ctypes
import socket
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import pystray
import uvicorn
from PIL import Image, ImageDraw

from blackbox.api import create_app, load_or_create_token
from blackbox.config import Config
from blackbox.paths import resolve_data_dir
from blackbox.probes.runner import ProbeRunner
from blackbox.store.db import create_engine, init_db

_MUTEX_HANDLE: Any = None


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_health(port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            url = f"http://127.0.0.1:{port}/health"
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def desktop_url(port: int, token: str) -> str:
    return f"http://127.0.0.1:{port}/?token={token}"


def create_icon() -> Image.Image:
    image = Image.new("RGB", (64, 64), "#0f1115")
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill="#2ecc71")
    return image


def _single_instance() -> bool:
    """กันเปิดแอปซ้ำด้วย named mutex ของ Windows"""
    global _MUTEX_HANDLE
    if not hasattr(ctypes, "windll"):
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_bool,
        ctypes.c_wchar_p,
    ]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _MUTEX_HANDLE = kernel32.CreateMutexW(
        None, False, "Local\\HomeNetworkBlackBox"
    )
    if not _MUTEX_HANDLE:
        return True
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def run_desktop(
    data_dir: str | Path | None = None,
    port: int | None = None,
    open_browser: bool = True,
) -> None:
    if not _single_instance():
        print("Home Network Black Box กำลังทำงานอยู่แล้ว")
        return

    data = resolve_data_dir(str(data_dir) if data_dir else None)
    engine = create_engine(data)
    init_db(engine)
    config = Config(data_dir=data)
    config.validate()

    runner = ProbeRunner(engine, config)
    threading.Thread(target=runner.run_forever, daemon=True).start()

    token = load_or_create_token(data)
    app = create_app(engine, token=token, data_dir=data)
    port = port or free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()

    if not wait_for_health(port):
        server.should_exit = True
        print("API ไม่ตอบสนอง — ยกเลิก")
        return

    url = desktop_url(port, token)
    print(f"UI: http://127.0.0.1:{port} (เปิดในเบราว์เซอร์)")
    if open_browser:
        webbrowser.open(url)

    def open_window(icon=None, item=None) -> None:
        webbrowser.open(url)

    def quit_app(icon, item=None) -> None:
        server.should_exit = True
        icon.stop()

    icon = pystray.Icon(
        "blackbox",
        create_icon(),
        "Home Network Black Box",
        menu=pystray.Menu(
            pystray.MenuItem("เปิดหน้าต่าง", open_window, default=True),
            pystray.MenuItem("ออก", quit_app),
        ),
    )
    icon.run()
