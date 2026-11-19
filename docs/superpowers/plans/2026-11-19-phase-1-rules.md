# Phase 1 — Event Rules Engine (slice 1)

**Goal:** แปลงผล probe ของแต่ละรอบเป็น event open/close actions สำหรับ gateway_down, internet_down, dns_fail, dns_slow, wifi_drop, latency_spike

**Spec:** `docs/superpowers/specs/2026-11-19-black-box-mvp-design.md` (Event rules)

**Scope:** `blackbox/events/rules.py` + `blackbox/store/events.py` + tests
**Out of scope (รอ concurrent work):** การเรียกจาก `runner.py` / `cli.py`; packet_loss window; new_device; public_ip_change; interface_change; narrator

## Tasks

1. `EventAction` model + `RuleEngine` skeleton + gateway/internet rules
2. DNS rules (`dns_fail`, `dns_slow`)
3. Wi-Fi + latency rules
4. `store/events.py`: `open_event`, `close_event`, `find_open_event`
5. Tests + full suite
6. Integrate into runner (deferred)

## Rules

| Type | เงื่อนไข | Severity |
|---|---|---|
| gateway_down | gateway ping fail 3 รอบติด | high |
| internet_down | internet targets fail 3 รอบติด ขณะ gateway ตอบ | high |
| dns_fail | DNS fail 2 รอบติด (resolver ใดก็ได้) | high |
| dns_slow | DNS latency > 1000ms 3 รอบติด | medium |
| wifi_drop | Wi-Fi disconnect หรือ signal < 30% 2 รอบติด | medium |
| latency_spike | avg RTT > 3× median ของ baseline (≥ 10 samples) | medium |

- Engine เป็น stateful ต่อ process; `open_types` ใช้กัน open ซ้ำ
- Close event เมื่อเงื่อนไขกลับปกติ
- ไม่เปิด `internet_down` ขณะ `gateway_down`
- Wi-Fi rule ทำงานเฉพาะเมื่อ `wifi_monitored=True`
