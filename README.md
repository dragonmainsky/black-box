# Home Network Black Box

ตัวบันทึกสุขภาพอินเทอร์เน็ตในบ้าน — เฝ้า ping / DNS / Wi-Fi / ARP แล้วเก็บหลักฐานไว้ดูย้อนหลัง

> **สถานะ:** Phase 0 (เครื่องวัด + SQLite + CLI) — ยังไม่มีหน้าจอ/tray

## เริ่มใช้งานใน VS Code

1. เปิดโฟลเดอร์ `black-box` ใน VS Code
2. เลือก interpreter: `.venv\Scripts\python.exe`
3. กด **F5** แล้วเลือก:
   - `Black Box: probe loop` — เฝ้าต่อเนื่อง
   - `Black Box: probe once` — ตรวจครั้งเดียว
   - `Black Box: show recent` — ดูข้อมูลล่าสุด
   - `Black Box: tests` — รันเทสต์

## CLI

```powershell
.\.venv\Scripts\python.exe main.py db init --data-dir .\data
.\.venv\Scripts\python.exe main.py probe once --data-dir .\data
.\.venv\Scripts\python.exe main.py probe loop --data-dir .\data
.\.venv\Scripts\python.exe main.py show recent --data-dir .\data
.\.venv\Scripts\python.exe main.py db maintenance --data-dir .\data
```

- `--data-dir` ไม่ระบุ → ใช้ `%APPDATA%\BlackBox`
- `probe once` คืน exit code `2` ถ้ามี probe ที่ล้มเหลว
- `probe loop --interval 60` เปลี่ยน cadence ของ ping

## สิ่งที่วัด

| Probe | ค่าเริ่มต้น |
|---|---|
| gateway + internet ping (1.1.1.1, 8.8.8.8) | ทุก 30 วิ, 3 echo ต่อเป้า |
| DNS (system resolver + 1.1.1.1) | ทุก 60 วิ |
| Wi-Fi (netsh) | ทุก 5 นาที |
| ARP passive (`arp -a`) | ทุก 5 นาที |
| public IP (ipify) | ปิดโดยค่าเริ่มต้น |

## ข้อมูลและความเป็นส่วนตัว

- ฐานข้อมูล: `<data-dir>\black_box.db` (SQLite, WAL)
- เก็บรายละเอียด 30 วัน, rollup รายชั่วโมง 365 วัน
- ไม่ดัก payload, ไม่สแกนพอร์ต, ไม่ต้องรหัส router
- ไม่ส่งข้อมูลขึ้น cloud

## เทสต์

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

## เอกสาร

- Design: `docs/superpowers/specs/2026-11-19-black-box-mvp-design.md`
- Plan: `docs/superpowers/plans/2026-11-19-phase-0.md`
