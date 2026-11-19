# HANDOFF — Home Network Black Box (Phase 1)

> สำหรับ AI/agent ที่มารับงานต่อ: อ่านไฟล์นี้ก่อน แล้วค่อยแก้โค้ด
> เปิดโฟลเดอร์นี้เป็น workspace: `C:\Users\User\Documents\router_for_testing\black-box`

## Snapshot

- Branch: `phase-0`
- HEAD: `b6ee481`
- Remote: ไม่มี (local only)
- Tests: **104 passed** (2026-11-19)
- Python: `.venv\Scripts\python.exe` (3.14.10)

## อ่านตามลำดับ

1. `README.md`
2. `docs/superpowers/specs/2026-11-19-black-box-mvp-design.md`
3. `docs/superpowers/plans/2026-11-19-phase-1-rules.md`
4. `git log --oneline -10` และ `git status --short`

## สิ่งที่เสร็จแล้ว

- Phase 0: probes + SQLite + Alembic + CLI + retention/rollup + `monitor_gap`
- Phase 1: rules engine + runner integration + event store
  - `gateway_down`, `internet_down`, `dns_fail`, `dns_slow`,
    `wifi_drop`, `latency_spike`, `packet_loss`
  - `new_device`: `upsert_devices` คืน MAC ใหม่ และ runner เปิด event `new_device`
  - `public_ip_change`: เก็บ baseline IP ใน `meta` และเปิด event เมื่อ IP เปลี่ยน
  - `interface_change`: เปิด event เมื่อ interface หรือ gateway เปลี่ยน โดยอิงจาก meta/probes
  - `narrator`: `blackbox/events/narrator.py` สรุปเหตุการณ์เป็นภาษาคนจาก event + evidence
- Event store: open/close/find; `show recent` เป็น merged timeline
- Windows console decoding: UTF-8 → CP874 → OEM
- Default route: `RouteMetric + InterfaceMetric`, filter `0.0.0.0`
- Tests: 104 passed

## งานถัดไป (Phase 2)

1. **CLI / Timeline สรุปภาษาคน**
   - นำ `narrator` ไปใช้แสดงผลใน `blackbox show recent` หรือ command สรุปสถานะ
2. **UI Launcher / Tray (Phase 2)**
   - System tray icon และหน้าต่างสรุปสถานะ
3. **ISP Evidence Pack / Report (Phase 3)**
   - สร้างรายงานสรุปประวัติสำหรับส่งแจ้ง ISP

## ข้อจำกัดสำคัญ

- SQLite เท่านั้น; SQLAlchemy Core เท่านั้น
- read-only ต่อ router: ห้าม Save/Apply/Reboot
- passive ARP เท่านั้น; active sweep เป็น opt-in Phase 4
- public IP default off
- UI ภาษาไทย ตรงไปตรงมา
- เวลาเก็บ UTC ISO-8601
- อย่าแตะ `router-watch/`

## คำสั่ง

```powershell
.\run-tests.bat
.\blackbox.bat probe once
.\blackbox.bat probe loop
.\blackbox.bat show recent
.\blackbox.bat db maintenance
```

VS Code: เปิดโฟลเดอร์นี้ → เลือก `.venv\Scripts\python.exe` → F5 หรือ Run Task

## Concurrency warning

มีงานจากอีก agent ที่ต้องเก็บไว้ ห้าม revert:

- `07c33fb`, `2e94571`, `0524a7b` — Thai date formatting
- `a465329` — probe loop startup/per-cycle summary

ก่อนแก้ `cli.py` / `runner.py` ให้เช็ก `git log --oneline -5` และ `git status --short` ก่อน
ถ้ามี agent อีกตัวกำลังทำงาน ให้เริ่มไฟล์ใหม่หรือประสานก่อน

## Definition of done

- `.\run-tests.bat` ผ่านทั้งหมด
- มี test ใหม่ครอบ behavior ที่เพิ่ม
- commit บน `phase-0`
- อัปเดต README + skill
- รายงานเป็นภาษาไทย พร้อมคำสั่งและผลเทสต์จริง
