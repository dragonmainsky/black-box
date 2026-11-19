from __future__ import annotations

import os
from pathlib import Path


def app_home() -> Path:
    """คืนโฟลเดอร์ข้อมูลของผู้ใช้ (%APPDATA%\\BlackBox)"""
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    path = root / "BlackBox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_data_dir(value: str | None) -> Path:
    """เลือก data dir จาก --data-dir หรือค่าเริ่มต้นของผู้ใช้"""
    path = Path(value).expanduser().resolve() if value else app_home()
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path(data_dir: Path) -> Path:
    return data_dir / "black_box.db"


def db_url(data_dir: Path) -> str:
    return f"sqlite:///{db_path(data_dir)}"
