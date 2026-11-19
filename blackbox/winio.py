from __future__ import annotations


def decode_console(data: bytes) -> str:
    """ถอดข้อความจาก console ของ Windows

    ลำดับ: UTF-8 (PowerShell 7 / ไฟล์), CP874 (Windows ไทย), OEM (ค่าเริ่มต้นของ console)
    """
    for encoding in ("utf-8", "cp874", "oem"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("oem", errors="replace")
