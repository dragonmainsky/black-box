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

## คำสั่งแบบสั้น

```powershell
.\blackbox.bat db init
.\blackbox.bat probe once
.\blackbox.bat probe loop
.\blackbox.bat show recent
.\blackbox.bat db maintenance
.\run-tests.bat
```

ถ้าไม่ระบุ `--data-dir` จะใช้ `%APPDATA%\BlackBox`
สำหรับเดโม/ทดสอบใช้ `.\blackbox.bat probe once --data-dir .\data`

## CLI (แบบเต็ม)

```powershell
.\.venv\Scripts\python.exe main.py db init --data-dir .\data
.\.venv\Scripts\python.exe main.py probe once --data-dir .\data
.\.venv\Scripts\python.exe main.py probe loop --data-dir .\data
.\.venv\Scripts\python.exe main.py show recent --data-dir .\data
.\.venv\Scripts\python.exe main.py db maintenance --data-dir .\data
```

- `--data-dir` ไม่ระบุ → ใช้ `%APPDATA%\BlackBox`
- `probe once` คืน exit code `2` ถ้ามี probe ที่ล้มเหลว
- `probe loop` พิมพ์สรุปทุกครั้งที่วัดเสร็จ; หยุดด้วย `Ctrl+C`
- `probe loop --interval 60` เปลี่ยน cadence ของ ping และคำนวณ DNS/Wi-Fi/ARP ให้อัตโนมัติ

## สิ่งที่วัด

| Probe | ค่าเริ่มต้น |
|---|---|
| gateway + internet ping (1.1.1.1, 8.8.8.8) | ทุก 30 วิ, 3 echo ต่อเป้า |
| DNS (system resolver + 1.1.1.1 + 8.8.8.8) | ทุก 60 วิ |
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

## ผลทดสอบ Phase 0 (2026-11-19)

- Unit tests: **81 passed**
- probe จริงผ่าน: gateway, 1.1.1.1, 8.8.8.8, DNS, Wi-Fi, ARP
- 10-minute loop (ก่อนแก้ตาม review): **117 probe rows**, 0 error, 0 gap event
  - ping 63, dns 33, wifi 18, arp 3
- หลังแก้: 45-second loop smoke — 31 rows, 0 error, maintenance tick ทำงาน
- สิ่งที่แก้หลัง review:
  - ถอด console output เป็น UTF-8 → CP874 → OEM (รองรับ Windows ไทย)
  - เลือก default route จาก `RouteMetric + InterfaceMetric` และตัด `0.0.0.0`
  - กัน `monitor_gap` ซ้ำ, ใช้ monotonic deadline, maintenance ทุก 6 ชม.
  - คำนวณ cadence จาก `--interval`, DNS `NoNameservers` → `network`
  - `show recent` เป็น timeline เดียวและแสดง `text_value`
- ข้อจำกัดที่พบ:
  - บาง driver ไม่ส่ง BSSID — probe จะข้าม field ที่หายไป
  - ARP เป็น passive: อุปกรณ์ที่ไม่คุยกับเครื่องนี้จะไม่ปรากฏ
  - ถ้า ICMP ถูกบล็อกจะบันทึกเป็น `network`; การ fallback TCP/DNS เป็นงาน Phase 1
  - หน้าจอ/tray เป็น Phase 2

## Phase 1 (กำลังทำ)

- `blackbox/events/rules.py` — gateway_down, internet_down, dns_fail, dns_slow, wifi_drop, latency_spike
- `blackbox/store/events.py` — open/close/find open event
- **เชื่อม `runner.py` แล้ว** — ประเมิน rules หลังจบแต่ละรอบและเปิด/ปิด event
- `show recent` แสดง event ที่เปิด/ปิดแล้ว
- เหลือ: packet_loss window 5 นาที, new_device, public_ip_change, interface_change, narrator

## เอกสาร

- Design: `docs/superpowers/specs/2026-11-19-black-box-mvp-design.md`
- Plan: `docs/superpowers/plans/2026-11-19-phase-0.md`
