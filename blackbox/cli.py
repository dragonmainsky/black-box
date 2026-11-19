from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from blackbox.config import Config
from blackbox.paths import db_path, resolve_data_dir
from blackbox.probes.runner import ProbeRunner
from blackbox.store.db import create_engine, init_db
from blackbox.store.events import recent_events
from blackbox.store.probes import recent_probes
from blackbox.store.retention import run_maintenance


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--data-dir", default=None)
    return parser


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
                return 0

        parser.print_help()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
