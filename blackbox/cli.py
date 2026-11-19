from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from blackbox.config import Config
from blackbox.events.narrator import narrate_event
from blackbox.paths import db_path, resolve_data_dir
from blackbox.probes.runner import ProbeRunner
from blackbox.status import SystemStatus, get_system_status
from blackbox.store.db import create_engine, init_db
from blackbox.store.events import recent_events
from blackbox.store.probes import recent_probes
from blackbox.store.retention import run_maintenance


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--data-dir", default=None)
    return parser

_THAI_MONTHS = [
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]


def format_ts(value: str, tz: timezone | None = None) -> str:
    local = datetime.fromisoformat(value).astimezone(tz)
    return f"{local.day} {_THAI_MONTHS[local.month - 1]} {local.year} {local:%H:%M:%S}"


def format_range(start: str, end: str | None, tz: timezone | None = None) -> str:
    start_local = datetime.fromisoformat(start).astimezone(tz)
    if not end:
        return f"{format_ts(start, tz)}–ongoing"
    end_local = datetime.fromisoformat(end).astimezone(tz)
    seconds = max(0, int((end_local - start_local).total_seconds()))
    minutes, secs = divmod(seconds, 60)
    duration = f"{minutes} นาที {secs} วิ" if minutes else f"{secs} วิ"
    return f"{format_ts(start, tz)}–{end_local:%H:%M:%S} ({duration})"


def format_status_output(
    status: SystemStatus, tz: timezone | None = None
) -> str:
    if status.status == "unknown":
        return "ยังไม่มีข้อมูล"

    lines = []
    lines.append(f"=== สถานะเครือข่าย: {status.status_text} ===")
    if status.interface:
        lines.append(f"Interface : {status.interface}")
    if status.gateway:
        lines.append(f"Gateway   : {status.gateway}")
    if status.public_ip:
        lines.append(f"Public IP : {status.public_ip}")
    if status.device_count > 0:
        lines.append(f"อุปกรณ์   : {status.device_count} เครื่อง")
    if status.last_cycle:
        lines.append(f"ตรวจล่าสุด : {format_ts(status.last_cycle, tz)}")

    lines.append("")
    if status.open_events:
        lines.append(f"[เหตุการณ์ที่กำลังเกิด] ({len(status.open_events)} รายการ)")
        for evt in status.open_events:
            start_str = format_ts(evt["ts_start"], tz)
            lines.append(
                f"  - {evt['type']} [{evt['severity']}] (เริ่มเมื่อ {start_str})"
            )
            narrative = evt.get("narrative") or narrate_event(evt)
            if narrative:
                lines.append(f"    {narrative}")
    else:
        lines.append("[เหตุการณ์ที่กำลังเกิด]")
        lines.append("  ไม่มี (เครือข่ายปกติ)")

    lines.append("")
    if status.recent_events:
        lines.append(f"[เหตุการณ์ล่าสุด] ({len(status.recent_events)} รายการ)")
        for evt in status.recent_events:
            rng_str = format_range(evt["ts_start"], evt.get("ts_end"), tz)
            lines.append(f"  - {rng_str} | {evt['type']} [{evt['severity']}]")
            narrative = evt.get("narrative") or narrate_event(evt)
            if narrative:
                lines.append(f"    {narrative}")
    else:
        lines.append("[เหตุการณ์ล่าสุด]")
        lines.append("  ไม่มีประวัติเหตุการณ์")

    return "\n".join(lines)

def build_parser() -> argparse.ArgumentParser:
    common = _common_parser()
    parser = argparse.ArgumentParser(
        prog="blackbox", description="Home Network Black Box"
    )
    parser.add_argument("--version", action="version", version="0.1.0")
    sub = parser.add_subparsers(dest="command")

    db = sub.add_parser("db", help="database maintenance")
    db_sub = db.add_subparsers(dest="db_command")
    db_sub.add_parser("init", parents=[common], help="create the database")
    maintenance = db_sub.add_parser(
        "maintenance", parents=[common], help="rollup and retention"
    )
    maintenance.add_argument("--vacuum", action="store_true")

    probe = sub.add_parser("probe", help="run probes")
    probe_sub = probe.add_subparsers(dest="probe_command")
    probe_sub.add_parser(
        "once", parents=[common], help="run all probes once"
    )
    loop = probe_sub.add_parser(
        "loop", parents=[common], help="run probes continuously"
    )
    loop.add_argument("--interval", type=int, default=None)

    show = sub.add_parser("show", help="show recorded data")
    show_sub = show.add_subparsers(dest="show_command")
    recent = show_sub.add_parser(
        "recent", parents=[common], help="recent probes and events"
    )
    recent.add_argument("--limit", type=int, default=50)
    status_parser = show_sub.add_parser(
        "status", parents=[common], help="summary status and latest events"
    )
    status_parser.add_argument("--limit", type=int, default=5)

    desktop = sub.add_parser(
        "desktop", parents=[common], help="open tray and browser UI"
    )
    desktop.add_argument("--port", type=int, default=None)
    desktop.add_argument("--no-browser", action="store_true")

    serve = sub.add_parser("serve-api", parents=[common], help="run local API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--token", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    try:
        data_dir = resolve_data_dir(getattr(args, "data_dir", None))
        config = Config(data_dir=data_dir)
        interval = getattr(args, "interval", None)
        if interval is not None:
            config = config.with_base_interval(interval)
        config.validate()

        if args.command == "desktop":
            from blackbox.desktop import run_desktop

            run_desktop(
                data_dir=data_dir,
                port=getattr(args, "port", None),
                open_browser=not getattr(args, "no_browser", False),
            )
            return 0

        engine = create_engine(data_dir)
        init_db(engine)

        if args.command == "db":
            if args.db_command == "init":
                print(f"สร้างฐานข้อมูลแล้ว: {db_path(data_dir)}")
                return 0
            if args.db_command == "maintenance":
                counts = run_maintenance(
                    engine,
                    datetime.now(timezone.utc),
                    retention_days=config.retention_days,
                    rollup_days=config.rollup_retention_days,
                    vacuum=args.vacuum,
                )
                print(counts)
                return 0

        if args.command == "probe":
            runner = ProbeRunner(engine, config)
            if args.probe_command == "once":
                results = runner.run_once()
                print(f"เก็บผลแล้ว {len(results)} รายการ")
                return 2 if any(not result.ok for result in results) else 0
            if args.probe_command == "loop":
                runner.run_forever()
                return 0

        if args.command == "show":
            if args.show_command == "status":
                status_data = get_system_status(
                    engine, recent_limit=getattr(args, "limit", 5)
                )
                print(format_status_output(status_data))
                return 0
            if args.show_command == "recent":
                rows = recent_probes(engine, limit=args.limit)
                events = recent_events(engine, limit=args.limit)
                if not rows and not events:
                    print("ยังไม่มีข้อมูล")
                    return 0
                entries: list[tuple[str, str, dict]] = []
                for row in rows:
                    entries.append((row["ts"], "probe", row))
                for event in events:
                    entries.append((event["ts_start"], "event", event))
                entries.sort(key=lambda item: item[0], reverse=True)
                for ts, kind, item in entries[: args.limit]:
                    if kind == "probe":
                        value = (
                            item["value"]
                            if item["value"] is not None
                            else item["text_value"]
                        )
                        status = (
                            "ok"
                            if item["ok"]
                            else f"fail:{item['error_kind']}"
                        )
                        print(
                            f"{ts} | {item['probe']} | {item['target']} | "
                            f"{value} | {status}"
                        )
                    else:
                        end = item.get("ts_end") or "ongoing"
                        print(
                            f"{ts} | {item['type']} | {item['severity']} | "
                            f"{item['title']} | {end}"
                        )
                        narrative = narrate_event(item)
                        if narrative:
                            print(f"  {narrative}")
                return 0

        if args.command == "serve-api":
            from blackbox.api import run_api

            run_api(
                engine=engine,
                host=args.host,
                port=args.port,
                token=args.token,
                data_dir=data_dir,
            )
            return 0

        parser.print_help()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
