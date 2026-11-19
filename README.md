# Home Network Black Box

ตัวบันทึกสุขภาพอินเทอร์เน็ตในบ้าน — เฝ้า ping / DNS / Wi-Fi / ARP แล้วเก็บหลักฐานไว้ดูย้อนหลัง

> **สถานะ:** Phase 2 บางส่วน — probes + rules + CLI + API + tray/window เบื้องต้น; ยังไม่มี notification/settings

## เริ่มใช้งานใน VS Code

1. รัน `.\setup.bat` ครั้งแรก — สร้าง `.venv` และติดตั้ง dependencies
2. เปิดโฟลเดอร์ `black-box` ใน VS Code
3. เลือก interpreter: `.venv\Scripts\python.exe`
4. กด **F5** แล้วเลือก:
   - `Black Box: probe loop` — เฝ้าต่อเนื่อง
   - `Black Box: probe once` — ตรวจครั้งเดียว
   - `Black Box: show recent` — ดูข้อมูลล่าสุด
   - `Black Box: tests` — รันเทสต์

## คำสั่งแบบสั้น

```powershell
.\blackbox.bat desktop
.\blackbox.bat db init
.\blackbox.bat probe once
.\blackbox.bat probe loop
.\blackbox.bat show status
.\blackbox.bat show recent
.\blackbox.bat serve-api
.\blackbox.bat db maintenance
.\run-tests.bat
```

> `desktop` เปิดหน้าต่าง + tray; ปิดหน้าต่าง = ซ่อนลง tray, ออกที่เมนู tray
> ใช้ `--data-dir .\data` สำหรับเดโม/ทดสอบ

ถ้าไม่ระบุ `--data-dir` จะใช้ `%APPDATA%\BlackBox`
สำหรับเดโม/ทดสอบใช้ `.\blackbox.bat probe once --data-dir .\data`

## CLI (แบบเต็ม)

```powershell
.\.venv\Scripts\python.exe main.py db init --data-dir .\data
.\.venv\Scripts\python.exe main.py probe once --data-dir .\data
.\.venv\Scripts\python.exe main.py probe loop --data-dir .\data
.\.venv\Scripts\python.exe main.py show status --data-dir .\data
.\.venv\Scripts\python.exe main.py show recent --data-dir .\data
.\.venv\Scripts\python.exe main.py serve-api --data-dir .\data
.\.venv\Scripts\python.exe main.py desktop --data-dir .\data
.\.venv\Scripts\python.exe main.py db maintenance --data-dir .\data
```

- `--data-dir` ไม่ระบุ → ใช้ `%APPDATA%\BlackBox`
- `probe once` คืน exit code `2` ถ้ามี probe ที่ล้มเหลว
- `probe loop` พิมพ์สรุปทุกครั้งที่วัดเสร็จ; หยุดด้วย `Ctrl+C`
- `probe loop --interval 60` เปลี่ยน cadence ของ ping และคำนวณ DNS/Wi-Fi/ARP ให้อัตโนมัติ
- `serve-api` เปิด Local API บน `127.0.0.1:8765` พร้อม token; ใช้ `--port` เพื่อเปลี่ยนพอร์ต
- `desktop` เปิด tray + หน้าต่าง pywebview; ปิดหน้าต่าง = ซ่อนลง tray

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

- Unit tests: **87 passed**
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

## Phase 1 (เสร็จแล้ว)

- `blackbox/events/rules.py` — gateway_down, internet_down, dns_fail, dns_slow, wifi_drop, latency_spike, packet_loss, new_device, public_ip_change, interface_change
- `blackbox/store/events.py` — open/close/find open event
- **เชื่อม `runner.py` แล้ว** — ประเมิน rules หลังจบแต่ละรอบและเปิด/ปิด event
- `packet_loss` window 5 นาที (≥30 packets) — เชื่อม runner แล้ว
- `show recent` แสดง event ที่เปิด/ปิดแล้ว
- `new_device` — ตรวจจับ MAC ใหม่จากการ sweep ARP passive และเปิด event
- `public_ip_change` — บันทึก Public IP ใน meta และเปิด event เมื่อ IP เปลี่ยน
- `interface_change` — ตรวจจับการเปลี่ยน gateway/interface และเปิด event
- `blackbox/events/narrator.py` — สรุปเหตุการณ์เป็นภาษาคนจาก event + evidence (104 tests passed)

## Phase 2 (กำลังดำเนินการ)

- **CLI narrator + status** (เสร็จแล้ว):
  - `show recent` แสดงคำอธิบายภาษาคน (`narrate_event()`) ใต้แต่ละแถว event
  - เพิ่ม `show status` สรุปสถานะเครือข่ายปัจจุบัน (ปกติ/เตือน/วิกฤต), interface, gateway, public IP, จำนวนอุปกรณ์, เหตุการณ์ที่กำลังเกิด (open events) และเหตุการณ์ล่าสุด
  - `blackbox/status.py` สำหรับคำนวณและสรุปสถานะระบบ (พร้อมรองรับ Local API ต่อไป)

- **Local API — FastAPI** (เสร็จแล้ว):
  - `blackbox/api.py` — FastAPI + SecurityMiddleware
  - bind `127.0.0.1` เท่านั้น; ห้ามใช้ `0.0.0.0`
  - Token สุ่ม 32-byte URL-safe; บันทึกใน `<data-dir>/api.token` (chmod 600)
  - ตรวจ Host header (DNS-rebinding defense), Origin, Referer
  - ไม่เปิด CORS
  - `/health` — liveness probe (ไม่ต้อง token)
  - `/api/status` — สถานะระบบ + open events + recent events พร้อม narrative
  - `/api/events?limit=50&type=...&open_only=true` — รายการ event พร้อม narrative
  - `/api/probes?limit=50&probe=...` — รายการ probe ล่าสุด
  - `CLI: blackbox serve-api [--port 8765] [--token ...]`
  - 24 unit tests (137 tests ทั้งหมด)

## เอกสาร

- Design: `docs/superpowers/specs/2026-11-19-black-box-mvp-design.md`
- Plan: `docs/superpowers/plans/2026-11-19-phase-0.md`
