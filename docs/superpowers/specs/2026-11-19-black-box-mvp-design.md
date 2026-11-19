# Home Network Black Box — Design (MVP)

วันที่: 2026-11-19
สถานะ: ทิศทางล็อกแล้ว (2026-11-19) — พร้อมเขียนแผน Phase 0

## Intent

ตอบคำถามของคนทั่วไปว่า **"ที่ผ่านมาเน็ตบ้านเป็นอะไร"** ไม่ใช่แค่ "ตอนนี้เป็นยังไง"

ตัวอย่างผลลัพธ์:

> เมื่อคืน 20:00–21:00 เน็ตหลุด
> router reboot 20:03 → WAN IP เปลี่ยน → DNS ล่ม 20:05–20:40 → packet loss 18%
> สรุป: ปัญหาอยู่ที่ฝั่ง ISP ไม่ใช่ Wi-Fi ในบ้าน
> หลักฐาน: กราฟ, ค่า probe, traceroute, เวลา → export ให้ ISP

## Goals

- เฝ้าระวังต่อเนื่องแบบไม่รบกวนผู้ใช้ (tray)
- เก็บหลักฐานที่อธิบายเหตุการณ์ย้อนหลังได้
- บอกสาเหตุเป็นภาษาคน + หลักฐานประกอบ
- ทำงาน local-only ไม่ต้องใช้รหัส router
- ติดตั้งง่าย: exe เดียว ไม่ต้องมี Python/Node/Docker

## Non-goals (MVP)

- AI อธิบายเหตุการณ์
- per-device bandwidth
- packet capture / payload inspection
- mobile app
- cloud sync
- heatmap / สถิติเชิงลึก

## Anti-goals

- เป็น packet sniffer
- สแกนพอร์ตหรือโจมตีอุปกรณ์ในบ้าน
- เก็บข้อมูลส่วนตัวเกินจำเป็น
- ต้องมีรหัส router จึงจะทำงาน

## Constraints

- Windows-first (Windows 10/11)
- SQLite เท่านั้น — ไม่มี MySQL
- SQLAlchemy 2.x **Core** เท่านั้น (ไม่มี ORM/Session)
- เวลาเก็บเป็น UTC ISO-8601
- ไม่ต้องสิทธิ์ admin สำหรับ MVP
- UI ภาษาไทย ตรงไปตรงมา
- ข้อมูลอยู่ที่ `%APPDATA%\BlackBox\black_box.db`
- Docker ใช้เฉพาะเดโม ไม่ใช่ชุดแจกจ่าย
- dependency ใหม่ที่อนุญาต: `dnspython` (DNS query ตรง) — นอกนั้นใช้ stdlib

## Network path ที่เฝ้า

- ค่าเริ่มต้น `monitor_interface = auto`: ใช้ interface ที่ถือ IPv4 default route (ไม่ใช่ loopback)
  และ re-detect ทุก 5 นาที
- บันทึก `interface` ลงทุกแถวของ `probes` เพื่อให้ย้อนหลังรู้ว่า probe วิ่งผ่าน path ไหน
- ผู้ใช้ override ได้ใน config เช่น `monitor_interface = "Wi-Fi"` หรือ `"Ethernet"`
- ถ้า Wi-Fi ไม่ใช่ monitored link → **ไม่ประเมิน `wifi_drop`** (ยังเก็บ Wi-Fi stats ได้ถ้ามี adapter)
- VPN / Hyper-V / WSL adapter: MVP เฝ้า default route ตามจริง
  ถ้า VPN เปิดอยู่ หลักฐานจะสะท้อน path ของ VPN — ต้องแสดง interface ใน evidence ให้ชัด
- ถ้า default route เปลี่ยนกลางทาง → บันทึก event `interface_change` (Phase 1)

## Approaches ที่พิจารณา

| แบบ | ลักษณะ | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **A. เฝ้าตลอดเวลา (เลือก)** | gateway/internet ทุก 30 วิ, Wi-Fi/ARP ทุก 5 นาที | เห็น outage สั้นๆ, หลักฐานละเอียด | DB โตเร็ว ต้องมี retention |
| B. ตรวจเป็นรอบ | ทุก 5 นาที | เบาเครื่อง | พลาดปัญหาสั้นกว่า 5 นาที |
| C. Hybrid | ปกติ 60 วิ, ผิดปกติถี่ขึ้น | สมดุล | logic ซับซ้อนกว่า |

**เลือก A** เพราะจุดขายคือการอธิบายเหตุการณ์ย้อนหลัง — probe ห่างเกินไปจะตอบไม่ได้
ต้นทุน storage ต่ำมากเมื่อเทียบกับข้อมูลที่ได้ (ประเมิน ~350k แถวใน 30 วัน)

## Architecture

```text
black-box/
  main.py              # entry point: VS Code / CLI
  .vscode/
    launch.json        # F5: probe loop / once / show recent / tests
    settings.json      # interpreter .venv + PYTHONUTF8
  requirements.txt
  requirements-dev.txt
  blackbox/
    probes/
      ping.py          # gateway + internet (IcmpSendEcho ผ่าน ctypes)
      dns.py           # query ตรงไป resolver (dnspython) — ไม่ผ่าน cache
      wifi.py          # netsh wlan show interfaces
      arp.py           # arp -a (passive) + vendor lookup
      public_ip.py     # optional, default off
      netif.py         # gateway/interface detection
      runner.py        # probe cycle + scheduling + maintenance tick
    events/
      rules.py         # threshold/state machine
      correlate.py     # รวม event ที่เกี่ยวข้อง
      narrator.py      # (Phase 1) สรุปภาษาคน
    store/
      db.py            # engine + PRAGMA + Alembic bootstrap
      tables.py        # SQLAlchemy Core tables
      probes.py        # batch insert / query
      events.py        # event CRUD
      retention.py     # rollup + delete เก่า
      migrations/      # Alembic baseline
    cli.py             # probe once / loop / show
    config.py          # interval, retention, paths
    paths.py           # %APPDATA%\BlackBox
  tests/
    fixtures/          # ping/netsh/arp outputs (en/th)
    test_*.py
  docs/
    superpowers/specs/ # เอกสารนี้
```

Phase 0 ทำเฉพาะ `probes/`, `store/` (รวม rollup/retention), `cli.py`, `config.py`,
`paths.py`, tests + event `monitor_gap` เท่านั้น
ยังไม่ทำ rules/correlate/narrator อื่นๆ (Phase 1), UI/tray (Phase 2), report (Phase 3)

## Probe schedule

| Probe | ทุก | ต่อรอบ | timeout | หมายเหตุ |
|---|---|---|---|---|
| gateway ping | 30 วิ | 3 echo | 2 วิ | `IcmpSendEcho` (ctypes) — ไม่ต้อง admin |
| internet ping 1.1.1.1 | 30 วิ | 3 echo | 2 วิ | |
| internet ping 8.8.8.8 | 30 วิ | 3 echo | 2 วิ | |
| DNS system resolver | 60 วิ | 1 query | 3 วิ | query ตรง — ไม่ผ่าน Windows cache |
| DNS 1.1.1.1 | 60 วิ | 1 query | 3 วิ | |
| Wi-Fi | 5 นาที | 1 | 5 วิ | เฉพาะเมื่อ Wi-Fi เป็น monitored link |
| ARP (passive) | 5 นาที | 1 | 5 วิ | `arp -a` เฉพาะ subnet ตัวเอง |
| public IP | 15 นาที | 1 | 5 วิ | optional, default **off** |

- 3 echo ต่อ target ต่อรอบ → ในหน้าต่าง 5 นาทีมี 30 packets ต่อ target
  (1 lost = 3.3%) — `packet_loss` ที่ 5% ต้องเสียอย่างน้อย 2 packets
- 1.1.1.1 และ 8.8.8.8 probe **ทั้งคู่ทุกรอบ** (ไม่สลับ) เพื่อเทียบเส้นทาง
  และให้ event ใช้ค่าที่ดีที่สุดของ internet targets
- ใช้ monotonic clock สำหรับ interval, wall clock สำหรับ timestamp
- jitter ±10% เพื่อไม่ให้ probe ตรงกันเป๊ะทุกครั้ง
- `--interval` เปลี่ยนเฉพาะ cadence ของ ping; DNS = 2× base;
  Wi-Fi/ARP = max(5 นาที, 10× base); public IP = 15 นาที
- ถ้า probe ใช้เวลาเกิน slot: ข้าม tick ที่ missed (ไม่รันซ้อน) และ log ไว้
- หลัง sleep/hibernate หรือไม่มีรอบที่สำเร็จเกิน **2× base interval (default 60 วิ)**:
  บันทึก `monitor_gap` event
- probe cycle เดียวรันใน thread เดียว (single writer) — probe ที่บล็อกได้ต้องมี timeout

## Data model

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE probes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT NOT NULL,
  probe       TEXT NOT NULL,
  target      TEXT,
  value       REAL,
  unit        TEXT,
  ok          INTEGER NOT NULL CHECK (ok IN (0,1)),
  interface   TEXT,
  text_value  TEXT,
  detail      TEXT,   -- JSON: sent/recv/loss/rtts/rcode ฯลฯ
  error_kind  TEXT    -- network|timeout|probe_error|parse_error
);
CREATE INDEX idx_probes_probe_time ON probes(probe, ts);
CREATE INDEX idx_probes_time ON probes(ts);

CREATE TABLE events (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_start TEXT NOT NULL,
  ts_end   TEXT,
  type     TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'info'
           CHECK (severity IN ('info','low','medium','high')),
  title    TEXT NOT NULL,
  details  TEXT,
  evidence TEXT
);
CREATE INDEX idx_events_time_sev ON events(ts_start, severity);
CREATE INDEX idx_events_type ON events(type);

CREATE TABLE devices (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  mac        TEXT NOT NULL UNIQUE,
  ip         TEXT,
  vendor     TEXT,
  name       TEXT,
  first_seen TEXT NOT NULL,
  last_seen  TEXT NOT NULL
);

CREATE TABLE probe_rollup (
  hour      TEXT NOT NULL,
  probe     TEXT NOT NULL,
  target    TEXT,
  avg_value REAL,
  min_value REAL,
  max_value REAL,
  loss_pct  REAL,
  samples   INTEGER NOT NULL,
  PRIMARY KEY (hour, probe, target)
);

CREATE TABLE reports (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at   TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end   TEXT NOT NULL,
  path         TEXT NOT NULL
);

CREATE TABLE meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

### Probe result encoding

| Probe | แถวที่เขียน | value | text/detail |
|---|---|---|---|
| gateway/internet ping | 1 แถวต่อ target ต่อรอบ | avg RTT (ms) | detail: `{sent, recv, loss_pct, rtts_ms}` |
| DNS | 1 แถวต่อ resolver ต่อ query | latency (ms) | detail: `{rcode, answers, resolver}`; ok = rcode NOERROR |
| Wi-Fi | 1 แถวต่อ field | ตัวเลข (signal %, rate) | `target` = ชื่อ field; `text_value` สำหรับ state/SSID/BSSID |
| ARP | 1 summary row ต่อ sweep | จำนวนอุปกรณ์ | upsert `devices` แยก; ไม่เขียน probe ต่ออุปกรณ์ |
| public IP | 1 แถว | — | `text_value` = IP |
| monitor_gap | 1 event (ไม่ใช่ probe) | — | detail: `{gap_seconds, last_ts}` |

`ok = 0` แยกสาเหตุด้วย `error_kind`:

- `network` — probe ทำงานได้ แต่ปลายทางไม่ตอบ (ใช้ตัดสิน event)
- `timeout` — เกินเวลาที่กำหนด
- `probe_error` — probe รันไม่ได้ (netsh/arp หาย, สิทธิ์ไม่พอ)
- `parse_error` — อ่านผลไม่ได้

### Retention และ maintenance

- raw probes: **30 วัน**
- rollup รายชั่วโมง: **365 วัน**
- events: **365 วัน**
- rollup คำนวณจาก raw ของชั่วโมงที่จบแล้ว (idempotent upsert) **ก่อน** ลบ raw
- maintenance tick: ตอน start และทุก **6 ชั่วโมง** ใน `probe loop`
  หรือสั่งด้วย `blackbox db maintenance`
- `meta` เก็บ `last_rollup_hour`, `last_maintenance`, `last_vacuum`
- ลบเป็นชุด (`DELETE ... WHERE ts < ? LIMIT 5000` วนซ้ำ) แล้ว `PRAGMA optimize`
- `VACUUM` เดือนละครั้ง (เช็กจาก `meta.last_vacuum`) หรือเมื่อผู้ใช้สั่ง
- batch insert ใน transaction เดียว (ไม่ commit ทีละแถว)

## Event rules (Phase 1)

| Event | เงื่อนไข | Severity |
|---|---|---|
| `gateway_down` | gateway ping fail 3 รอบติด (90 วิ) | high |
| `internet_down` | internet target fail 3 รอบติด แต่ gateway ตอบ | high |
| `dns_fail` | DNS query fail 2 ครั้งติด (timeout หรือ rcode != NOERROR) | high |
| `dns_slow` | latency > 1s ต่อเนื่อง 3 ครั้ง | medium |
| `latency_spike` | latency > 3× median 1 ชม. ต่อเนื่อง 5 นาที | medium |
| `packet_loss` | loss > 5% ในหน้าต่าง 5 นาที (ต่อ target, ≥ 30 packets) | high |
| `wifi_drop` | เฉพาะเมื่อ Wi-Fi เป็น monitored link: disconnect หรือ signal < 30% 2 ตัวอย่างติด | medium |
| `new_device` | MAC ไม่เคยเห็น (passive ARP — best effort) | low/medium |
| `public_ip_change` | IP เปลี่ยน (ถ้าเปิด probe) | low |
| `monitor_gap` | ไม่มีรอบที่สำเร็จเกิน 2× base interval (default 60 วิ) | medium |
| `interface_change` | default route/interface เปลี่ยน | low |
| `router_reboot` | uptime reset (optional ผ่าน Router Watch) | medium |

- DNS probe ยิงตรงไป resolver จึงไม่ถูก Windows cache หลอก
- `packet_loss` คิดแยกต่อ target; ถ้า internet ขาดทั้งเส้นให้รายงาน `internet_down` เป็นหลัก
- `monitor_gap` ใช้ cadence ที่เร็วที่สุด (ping 30 วิ) ไม่ใช่ 2× ของ Wi-Fi
- เปิด event เมื่อเงื่อนไขเริ่ม และปิด (`ts_end`) เมื่อกลับปกติ
- ห้ามสร้าง event ซ้ำซ้อน: ถ้ามี event ชนิดเดียวกันเปิดอยู่ ให้อัปเดต evidence
- evidence เป็น JSON: ค่า probe ที่เกี่ยวข้อง, gateway, Wi-Fi state, ช่วงเวลา

## CLI (Phase 0)

```text
blackbox db init
blackbox probe once [--probe gateway|internet|dns|wifi|arp|all]
blackbox probe loop [--interval 30]
blackbox show recent [--limit 50]      # timeline: probes + events
blackbox show probes --probe internet --since 1h
blackbox db maintenance               # rollup + retention + optimize
blackbox db vacuum
```

- ทุกคำสั่งรับ `--data-dir` สำหรับ test/demo (ไม่แตะ `%APPDATA%`)
- `show recent` แสดง timeline ผสม: probe ล่าสุด + event (Phase 0 มี `monitor_gap`)
- exit code 0 = สำเร็จ, 1 = error, 2 = probe fail บางตัว (ยังเขียน DB)
- log ลง stderr ไม่เขียนข้อมูลลับ

## Running in VS Code (required)

ผู้ใช้ตรวจงานผ่าน VS Code — ต้องเปิดโฟลเดอร์ `black-box/` แล้วกด Run/F5 ได้ทันที

- **ไฟล์หลัก:** `main.py` ที่ root
  - dispatch ไป `blackbox.cli:main`
  - รันจาก root ได้โดยไม่ต้องตั้ง `PYTHONPATH`
  - ลงท้ายด้วย `if __name__ == "__main__": raise SystemExit(main())`
- **Interpreter:** `.venv\Scripts\python.exe`
- **`.vscode/launch.json`:**
  - `Black Box: probe loop` → `main.py probe loop --data-dir ${workspaceFolder}/data`
  - `Black Box: probe once` → `main.py probe once --data-dir ${workspaceFolder}/data`
  - `Black Box: show recent` → `main.py show recent --data-dir ${workspaceFolder}/data`
  - `Black Box: tests` → pytest
- **`.vscode/settings.json`:** `python.defaultInterpreterPath` + `PYTHONUTF8=1`
- **คำสั่งพื้นฐาน:**
  ```powershell
  .\.venv\Scripts\python.exe main.py db init --data-dir .\data
  .\.venv\Scripts\python.exe main.py probe loop --data-dir .\data
  .\.venv\Scripts\python.exe main.py show recent --data-dir .\data
  ```
- Phase 2: ไม่มี args → เปิด launcher; มี args → CLI
- ห้าม hard-code path — ใช้ `--data-dir` หรือ `%APPDATA%\BlackBox`

## Testing strategy

| ชั้น | วิธี |
|---|---|
| Unit: parsers | fixture output จริงจาก Windows en/th |
| Unit: rules | synthetic time series |
| Store | `sqlite:///:memory:` + temp file |
| Integration | probe จริงกับ NimbusNet / gateway |
| Manual | เครือข่ายจริง 1–2 วัน ดู false positive |

- ห้ามเทสต์ที่ต้องใช้เน็ตจริงใน unit suite
- ใช้ `freezegun`-style injection ผ่าน clock parameter (ไม่เพิ่ม dependency ถ้าไม่จำเป็น)

## Phase 0 acceptance criteria

1. `blackbox probe loop` รันต่อเนื่อง 10 นาทีโดยไม่ crash และไม่มี probe ค้างเกิน timeout
2. เขียน probe ครบทุกตัวตาม schedule ลง SQLite (temp path) พร้อม `interface`/`error_kind`
3. `show recent` แสดง timeline ของ probes + `monitor_gap`
4. maintenance/rollup ทำงาน (ทดสอบด้วยเวลาจำลอง)
5. Unit tests ผ่านทั้งหมด (คาด ~30–40 ตัว)
6. ไม่ต้องสิทธิ์ admin
7. ไม่มีการเรียก network ออกนอกเครื่อง ยกเว้น ping/DNS/public IP (public IP default off)
8. มี `--data-dir` และไม่แตะข้อมูลจริงระหว่างเทสต์
9. `main.py` รันได้จาก VS Code (probe once / loop / show recent)
10. `.vscode/launch.json` และ `settings.json` ใช้งานได้

## UI (Phase 2)

แนวคิด: ปฏิทิน/timeline เหมือน Google Calendar

- **วัน:** timeline แนวนอน 24 ชม. — กล่องสีตามช่วงเวลา, เส้นเวลาปัจจุบัน,
  คลิกกล่อง → แผงรายละเอียดด้านข้าง
- **สัปดาห์:** 7 แถว × 24 ชม. เป็น heatmap
- **เดือน:** ปฏิทินรายวัน สีตาม severity
- **ปี:** 12 ช่องเดือน เป็น heatmap
- **แถบซ้าย:** สถานะสุขภาพ (นิยาม 99.2% ให้ชัด) + ตัวกรองประเภท event
- **ลากเลือกช่วงเวลา:** "อธิบายช่วงนี้"
- **สี:** เขียว/เหลือง/ส้ม/แดง + ไอคอน/ลวดลาย (ไม่พึ่งสีอย่างเดียว)
- **รายละเอียด event:** เกิดอะไร, เริ่ม–จบ, หลักฐาน, event ที่เกี่ยวข้อง
- **Zoom:** scroll/pinch ตามระดับ; ซูมออกให้ aggregate ไม่วาดทุก event
- **Empty state:** "เน็ตปกติตลอดช่วงนี้" ไม่ใช่จอว่าง

## Security requirements

1. **Local API (Phase 2):** bind `127.0.0.1` เท่านั้น, token สุ่ม, ตรวจ Host/Origin,
   ไม่เปิด CORS; runtime token ไฟล์สิทธิ์ user-only
2. **Subprocess:** ใช้ argv array, ห้าม `shell=True`, ตรวจชื่อ interface กับ allowlist;
   ping ใช้ `IcmpSendEcho` ไม่เรียก `ping.exe` จาก PATH
3. **Target allowlist:** gateway + 1.1.1.1 + 8.8.8.8; ห้ามรับ target อะไรก็ได้จาก config
4. **Data at rest:** ACL user-only, ไม่เก็บ secret, retention 30/365 วัน;
   encryption เป็น option ภายหลัง
5. **Export:** เตือนก่อน export, มีโหมด redact, escape ข้อมูลก่อนใส่ HTML/PDF
6. **Supply chain:** pin dependency, ไม่ auto-update ถ้าไม่มี signature verification
7. **Logs:** ไม่ log public IP/SSID ระดับ info; redact ข้อมูลที่ระบุบ้าน
8. **ICMP fallback:** ถ้า ICMP ถูกบล็อก ให้ลอง TCP 443 หรือ DNS ก่อนสรุปว่าเน็ตล่ม

## Packaging (ภายหลัง)

- Nuitka onefile + MSVC เหมือน Router Watch
- ไม่มี Playwright/Chromium
- launcher + engine (`--serve`) ใช้ pattern เดียวกัน
- ข้อมูลอยู่ที่ `%APPDATA%\BlackBox\`

## What's left to the builder

- วิธี parse `netsh`/`arp` ให้รองรับ Windows ภาษาไทยและอังกฤษ (ใช้ fixtures en/th)
- รายละเอียด baseline algorithm ของ `latency_spike` (median 1 ชม., warm-up)
- วิธี detect default route/interface บน Windows แบบไม่พึ่ง locale
- จัดการ edge case: VPN, หลาย NIC, adapter หลุดกลางทาง
- รูปแบบ evidence pack (Phase 3)
- UI layout (Phase 2)
- ชื่อแบรนด์/icon

## Open questions (ไม่บล็อก Phase 0)

- per-device bandwidth — อยู่นอก MVP
- Raspberry Pi — อนาคต
- active ARP sweep — ไม่ทำใน MVP (ขัด anti-goal); ถ้าจะทำเป็น opt-in Phase 4
- VPN / หลาย NIC — MVP ใช้ default route + override; ถ้าต้องการ auto-detect physical NIC ค่อยเพิ่ม

## Builder check — decisions (2026-11-19)

1. **Network path**: auto = interface ที่ถือ default route, re-detect ทุก 5 นาที,
   บันทึก `interface` ทุกแถว, override ได้; VPN แสดง interface ใน evidence
2. **DNS**: query ตรงด้วย `dnspython` ไปยัง resolver ที่ตั้งไว้ + 1.1.1.1
   วัด rcode + latency — ไม่ผ่าน Windows cache
3. **Schema**: เพิ่ม `interface`, `text_value`, `detail` (JSON), `error_kind`;
   ARP เขียน summary row + upsert `devices`; Wi-Fi แยกแถวต่อ field
4. **ICMP**: 3 echo ต่อ target ต่อรอบ; 1.1.1.1 และ 8.8.8.8 ทุกรอบ;
   ใช้ `IcmpSendEcho` ผ่าน ctypes (ไม่ต้อง admin, ไม่พึ่ง locale)
5. **Timeout**: ping 2s, DNS 3s, netsh/arp 5s; ข้าม tick ที่ missed;
   `--interval` คุมเฉพาะ ping
6. **ARP**: passive `arp -a` เท่านั้นใน MVP; `new_device` เป็น best-effort
7. **Retention**: rollup ก่อนลบ raw, maintenance ทุก 6 ชม. + CLI, เก็บสถานะใน `meta`
8. **Phase 0 events**: เขียนเฉพาะ `monitor_gap`; `show recent` = probes + events
