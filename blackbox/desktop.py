from __future__ import annotations

import ctypes
import json
import os
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
from blackbox.paths import resolve_data_dir
from blackbox.probes.runner import ProbeRunner
from blackbox.settings import config_from_settings, load_settings
from blackbox.store.db import create_engine, init_db

_MUTEX_HANDLE: Any = None
_CONSOLE_HANDLER: Any = None


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


def wait_for_stop(stop_event: threading.Event, interval: float = 0.5) -> None:
    """รอจนกว่า stop_event จะถูก set; Ctrl+C ต้องหยุดได้"""
    try:
        while not stop_event.wait(interval):
            pass
    except KeyboardInterrupt:
        pass


def install_console_handler(stop_event: threading.Event) -> None:
    """รับ Ctrl+C / Ctrl+Break จาก Windows console แล้วสั่งหยุด"""
    global _CONSOLE_HANDLER
    if not hasattr(ctypes, "windll"):
        return

    handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)
    stop_events = {0, 1, 2, 5, 6}  # C, BREAK, CLOSE, LOGOFF, SHUTDOWN

    def handler(event: int) -> bool:
        if event in stop_events:
            stop_event.set()
            return True
        return False

    _CONSOLE_HANDLER = handler_type(handler)
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleCtrlHandler.argtypes = [handler_type, ctypes.c_bool]
    kernel32.SetConsoleCtrlHandler.restype = ctypes.c_bool
    kernel32.SetConsoleCtrlHandler(_CONSOLE_HANDLER, True)


def runtime_path(data_dir: Path) -> Path:
    return data_dir / "runtime.json"


def read_runtime(data_dir: Path) -> dict | None:
    path = runtime_path(data_dir)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_runtime(data_dir: Path, port: int) -> None:
    runtime_path(data_dir).write_text(
        json.dumps({"pid": os.getpid(), "port": port}),
        encoding="utf-8",
    )


def remove_runtime(data_dir: Path) -> None:
    try:
        runtime_path(data_dir).unlink()
    except FileNotFoundError:
        pass


def run_desktop(
    data_dir: str | Path | None = None,
    port: int | None = None,
    open_browser: bool = True,
) -> None:
    data = resolve_data_dir(str(data_dir) if data_dir else None)

    if not _single_instance():
        existing = read_runtime(data)
        port_existing = existing.get("port") if existing else None
        if isinstance(port_existing, int) and wait_for_health(port_existing, timeout=1.5):
            token_existing = load_or_create_token(data)
            url_existing = desktop_url(port_existing, token_existing)
            print(f"เปิดหน้าต่างที่มีอยู่แล้ว: {url_existing}")
            if open_browser:
                webbrowser.open(url_existing)
        else:
            print(
                "มี Home Network Black Box ค้างอยู่ — "
                "ปิดจาก tray หรือ Task Manager ก่อน"
            )
        return

    engine = create_engine(data)
    init_db(engine)
    settings = load_settings(engine)
    config = config_from_settings(data, settings)

    runner = ProbeRunner(engine, config)

    def apply_settings(new_settings) -> None:
        runner.update_config(config_from_settings(data, new_settings))

    stop_event = threading.Event()
    install_console_handler(stop_event)

    def request_quit() -> None:
        threading.Timer(0.2, stop_event.set).start()

    token = load_or_create_token(data)
    app = create_app(
        engine,
        token=token,
        data_dir=data,
        on_settings_changed=apply_settings,
        on_quit=request_quit,
    )
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
    write_runtime(data, port)
    print(f"UI: http://127.0.0.1:{port} (เปิดในเบราว์เซอร์)")
    if open_browser:
        webbrowser.open(url)

    def open_window(icon=None, item=None) -> None:
        webbrowser.open(url)

    def quit_app(icon, item=None) -> None:
        stop_event.set()
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

    def notify_event(action) -> None:
        if action.action == "open" and action.severity == "high":
            icon.notify(
                f"{action.title}: {action.details}",
                "Home Network Black Box",
            )

    runner.on_event = notify_event

    def start_runner(icon) -> None:
        threading.Thread(target=runner.run_forever, daemon=True).start()

    def run_icon() -> None:
        try:
            icon.run(setup=start_runner)
        except Exception as exc:
            print(f"tray error: {exc}")
            stop_event.set()

    threading.Thread(target=run_icon, daemon=True).start()
    try:
        wait_for_stop(stop_event)
    finally:
        remove_runtime(data)
        server.should_exit = True
        icon.stop()
