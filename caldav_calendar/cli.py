from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .config import load_config
from .errors import (
    CaldavCalendarError,
    ConfirmationRequiredError,
    NotFoundError,
    ValidationError,
)
from .ics_event import build_event, event_to_bytes, new_uid as new_event_uid
from .ics_task import build_task, new_uid as new_task_uid, task_to_bytes
from .models import EventCreateInput, TaskCreateInput, load_json_file
from .output import emit, emit_error, fail_unexpected
from .sync import run_sync
from . import remote
from .vdir import (
    event_overlaps,
    event_summary,
    find_by_uid,
    iter_components,
    mark_task_done,
    overwrite_ics,
    task_summary,
    write_new_ics,
)


def _require_mode(args: argparse.Namespace) -> bool:
    if getattr(args, "dry_run", False) == getattr(args, "confirm", False):
        raise ConfirmationRequiredError("Write operations require exactly one of --dry-run or --confirm")
    return bool(args.dry_run)


def _audit(config, operation: str, payload: dict[str, Any]) -> None:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    audit_path = config.data_dir / "audit.log.jsonl"
    entry = {
        "timestamp": datetime.now().astimezone().isoformat(),
        "operation": operation,
        **payload,
    }
    with audit_path.open("a") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def _vcalendar_text(calendar) -> str:
    return calendar.to_ical().decode("utf-8")


def cmd_doctor(args: argparse.Namespace) -> int:
    env = {
        name: os.environ.get(name)
        for name in [
            "CALDAV_CALENDAR_CONFIG_DIR",
            "CALDAV_CALENDAR_AUTH_FILE",
            "CALDAV_CALENDAR_DATA_DIR",
            "CALDAV_CALENDAR_DEFAULT_TIMEZONE",
        ]
    }
    payload: dict[str, Any] = {
        "ok": True,
        "operation": "doctor",
        "env": {name: bool(value) for name, value in env.items()},
        "tools": {name: bool(shutil.which(name)) for name in ["vdirsyncer", "khal", "todo"]},
        "python": {"caldav": importlib.util.find_spec("caldav") is not None},
        "config": {},
    }
    try:
        config = load_config(require_files=False)
        payload["config"] = {
            "config_file": str(config.config_file) if config.config_file else None,
            "timezone": config.timezone,
            "backend": config.backend,
            "timezone_configured": bool(config.timezone),
            "event_dirs": {
                name: {"path": str(path), "exists": path.exists()}
                for name, path in config.event_calendars.items()
            },
            "task_dirs": {
                name: {"path": str(path), "exists": path.exists()}
                for name, path in config.task_lists.items()
            },
            "event_collections": config.event_collections,
            "task_collections": config.task_collections,
        }
    except CaldavCalendarError as exc:
        payload["ok"] = False
        payload["config_error"] = {"code": exc.code, "message": exc.message}
    return emit(payload)


def cmd_sync(args: argparse.Namespace) -> int:
    config = load_config()
    if config.backend == "direct-caldav":
        return emit({"ok": True, "operation": "sync", "backend": "direct-caldav", "sync": {"backend": "direct-caldav", "skipped": True, "reason": "direct CalDAV backend writes to remote immediately"}})
    result = run_sync()
    return emit({"ok": True, "operation": "sync", "sync": result})


def cmd_caldav_discover(args: argparse.Namespace) -> int:
    config = load_config()
    return emit({"ok": True, "operation": "caldav.discover", "collections": remote.discover(config)})


def cmd_event_list(args: argparse.Namespace) -> int:
    config = load_config()
    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date)
    if config.backend == "direct-caldav":
        return emit({"ok": True, "operation": "event.list", "items": remote.list_events(config, start, end)})
    items = []
    for calendar_name, directory in config.event_calendars.items():
        for item in iter_components(directory, "VEVENT"):
            if event_overlaps(item, start, end):
                items.append(event_summary(item, calendar_name))
    return emit({"ok": True, "operation": "event.list", "items": items})


def cmd_event_get(args: argparse.Namespace) -> int:
    config = load_config()
    if config.backend == "direct-caldav":
        return emit({"ok": True, "operation": "event.get", "item": remote.get_event(config, args.uid)})
    item = find_by_uid(list(config.event_calendars.values()), "VEVENT", args.uid)
    return emit({"ok": True, "operation": "event.get", "item": event_summary(item)})


def cmd_event_create(args: argparse.Namespace) -> int:
    dry_run = _require_mode(args)
    config = load_config()
    input_data = EventCreateInput.from_json(load_json_file(args.json_input), config.default_event_calendar, config.timezone)
    uid = new_event_uid()
    calendar = build_event(input_data, uid)
    item = {
        "kind": "event",
        "title": input_data.title,
        "start": input_data.start.isoformat(),
        "end": input_data.end.isoformat(),
        "timezone": input_data.timezone,
    }
    if dry_run:
        return emit(
            {
                "ok": True,
                "operation": "event.create",
                "dry_run": True,
                "would_create": item,
                "ical": _vcalendar_text(calendar),
            }
        )
    if config.backend == "direct-caldav":
        remote.create_event(config, input_data.calendar, _vcalendar_text(calendar))
        sync_result = {"backend": "direct-caldav", "skipped": True, "reason": "created directly on CalDAV server"}
        path = None
    else:
        directory = config.event_dir(input_data.calendar)
        path = write_new_ics(directory, uid, event_to_bytes(calendar))
        sync_result = run_sync()
    _audit(config, "event.create", {"uid": uid, "title": input_data.title, "dry_run": False, "result": "ok"})
    return emit(
        {
            "ok": True,
            "operation": "event.create",
            "dry_run": False,
            "uid": uid,
            "path": str(path) if path else None,
            "item": item,
            "sync": sync_result,
        }
    )


def cmd_task_list(args: argparse.Namespace) -> int:
    config = load_config()
    if config.backend == "direct-caldav":
        return emit({"ok": True, "operation": "task.list", "items": remote.list_tasks(config, args.status)})
    items = []
    for list_name, directory in config.task_lists.items():
        for item in iter_components(directory, "VTODO"):
            summary = task_summary(item, list_name)
            is_done = summary["status"].upper() in {"COMPLETED", "CANCELLED"}
            if args.status == "all" or (args.status == "done" and is_done) or (args.status == "open" and not is_done):
                items.append(summary)
    return emit({"ok": True, "operation": "task.list", "items": items})


def cmd_task_get(args: argparse.Namespace) -> int:
    config = load_config()
    if config.backend == "direct-caldav":
        return emit({"ok": True, "operation": "task.get", "item": remote.get_task(config, args.uid)})
    item = find_by_uid(list(config.task_lists.values()), "VTODO", args.uid)
    return emit({"ok": True, "operation": "task.get", "item": task_summary(item)})


def cmd_task_create(args: argparse.Namespace) -> int:
    dry_run = _require_mode(args)
    config = load_config()
    input_data = TaskCreateInput.from_json(load_json_file(args.json_input), config.default_task_list, config.timezone)
    uid = new_task_uid()
    calendar = build_task(input_data, uid)
    item = {
        "kind": "task",
        "title": input_data.title,
        "due": input_data.due,
        "status": "NEEDS-ACTION",
        "priority": input_data.priority,
    }
    if dry_run:
        return emit(
            {
                "ok": True,
                "operation": "task.create",
                "dry_run": True,
                "would_create": item,
                "ical": _vcalendar_text(calendar),
            }
        )
    if config.backend == "direct-caldav":
        remote.create_task(config, input_data.list_name, _vcalendar_text(calendar))
        sync_result = {"backend": "direct-caldav", "skipped": True, "reason": "created directly on CalDAV server"}
        path = None
    else:
        directory = config.task_dir(input_data.list_name)
        path = write_new_ics(directory, uid, task_to_bytes(calendar))
        sync_result = run_sync()
    _audit(config, "task.create", {"uid": uid, "title": input_data.title, "dry_run": False, "result": "ok"})
    return emit(
        {
            "ok": True,
            "operation": "task.create",
            "dry_run": False,
            "uid": uid,
            "path": str(path) if path else None,
            "item": item,
            "sync": sync_result,
        }
    )


def cmd_task_done(args: argparse.Namespace) -> int:
    dry_run = _require_mode(args)
    config = load_config()
    if config.backend == "direct-caldav":
        before = remote.get_task(config, args.uid)
        if dry_run:
            return emit(
                {
                    "ok": True,
                    "operation": "task.done",
                    "dry_run": True,
                    "would_mark_done": before,
                }
            )
        updated = remote.complete_task(config, args.uid)
        sync_result = {"backend": "direct-caldav", "skipped": True, "reason": "updated directly on CalDAV server"}
        _audit(config, "task.done", {"uid": args.uid, "title": updated.get("title", ""), "dry_run": False, "result": "ok"})
        return emit(
            {
                "ok": True,
                "operation": "task.done",
                "dry_run": False,
                "uid": args.uid,
                "item": updated,
                "sync": sync_result,
            }
        )
    item = find_by_uid(list(config.task_lists.values()), "VTODO", args.uid)
    before = task_summary(item)
    if dry_run:
        return emit(
            {
                "ok": True,
                "operation": "task.done",
                "dry_run": True,
                "would_mark_done": before,
            }
        )
    calendar = mark_task_done(item)
    overwrite_ics(item.path, calendar.to_ical())
    sync_result = run_sync()
    _audit(config, "task.done", {"uid": args.uid, "title": before.get("title", ""), "dry_run": False, "result": "ok"})
    return emit(
        {
            "ok": True,
            "operation": "task.done",
            "dry_run": False,
            "uid": args.uid,
            "item": {**before, "status": "COMPLETED"},
            "sync": sync_result,
        }
    )


def cmd_passthrough(argv: list[str]) -> int:
    aliases = {
        "discover": ["vdirsyncer", "discover"],
        "list": ["khal", "list"],
        "search": ["khal", "search"],
        "new": ["khal", "new"],
        "edit": ["khal", "edit"],
        "todo": ["todo"],
        "todoman": ["todo"],
        "khal": ["khal"],
        "vdirsyncer": ["vdirsyncer"],
    }
    command = argv[0]
    subprocess_args = aliases[command] + argv[1:]
    return subprocess.call(subprocess_args)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValidationError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="caldav-calendar")
    sub = parser.add_subparsers(dest="command", parser_class=JsonArgumentParser)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    sync = sub.add_parser("sync")
    sync.add_argument("--json", action="store_true")
    sync.set_defaults(func=cmd_sync)

    event = sub.add_parser("event")
    event_sub = event.add_subparsers(dest="event_command", required=True, parser_class=JsonArgumentParser)
    event_list = event_sub.add_parser("list")
    event_list.add_argument("--from", dest="from_date", required=True)
    event_list.add_argument("--to", dest="to_date", required=True)
    event_list.add_argument("--json", action="store_true")
    event_list.set_defaults(func=cmd_event_list)
    event_get = event_sub.add_parser("get")
    event_get.add_argument("--uid", required=True)
    event_get.add_argument("--json", action="store_true")
    event_get.set_defaults(func=cmd_event_get)
    event_create = event_sub.add_parser("create")
    event_create.add_argument("--json-input", required=True)
    event_create.add_argument("--dry-run", action="store_true")
    event_create.add_argument("--confirm", action="store_true")
    event_create.set_defaults(func=cmd_event_create)

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="task_command", required=True, parser_class=JsonArgumentParser)
    task_list = task_sub.add_parser("list")
    task_list.add_argument("--status", choices=["open", "done", "all"], required=True)
    task_list.add_argument("--json", action="store_true")
    task_list.set_defaults(func=cmd_task_list)
    task_get = task_sub.add_parser("get")
    task_get.add_argument("--uid", required=True)
    task_get.add_argument("--json", action="store_true")
    task_get.set_defaults(func=cmd_task_get)
    task_create = task_sub.add_parser("create")
    task_create.add_argument("--json-input", required=True)
    task_create.add_argument("--dry-run", action="store_true")
    task_create.add_argument("--confirm", action="store_true")
    task_create.set_defaults(func=cmd_task_create)
    task_done = task_sub.add_parser("done")
    task_done.add_argument("--uid", required=True)
    task_done.add_argument("--dry-run", action="store_true")
    task_done.add_argument("--confirm", action="store_true")
    task_done.set_defaults(func=cmd_task_done)

    caldav_parser = sub.add_parser("caldav")
    caldav_sub = caldav_parser.add_subparsers(dest="caldav_command", required=True, parser_class=JsonArgumentParser)
    caldav_discover = caldav_sub.add_parser("discover")
    caldav_discover.add_argument("--json", action="store_true")
    caldav_discover.set_defaults(func=cmd_caldav_discover)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if os.environ.get("CALDAV_CALENDAR_CONFIG_DIR") and not os.environ.get("XDG_CONFIG_HOME"):
        os.environ["XDG_CONFIG_HOME"] = os.environ["CALDAV_CALENDAR_CONFIG_DIR"]
    if argv and argv[0] in {"discover", "list", "search", "new", "edit", "todo", "todoman", "khal", "vdirsyncer"}:
        return cmd_passthrough(argv)
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if not hasattr(args, "func"):
            parser.print_help()
            return 1
        return args.func(args)
    except CaldavCalendarError as exc:
        return emit_error(exc)
    except ValueError as exc:
        return emit_error(ValidationError(str(exc)))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        return fail_unexpected(exc)


if __name__ == "__main__":
    raise SystemExit(main())
