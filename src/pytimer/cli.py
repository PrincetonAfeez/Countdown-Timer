"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .app import TimerApp
from .engine import TimerEngine
from .errors import InvalidDurationError
from .notifiers import build_notifier
from .parsers import ParserRegistry
from .persistence import Config, JSONPresetRepository, SessionLog, default_data_dir
from .renderers import build_renderer

COMMANDS = {"start", "preset", "log"}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(_normalize_argv(list(argv or sys.argv[1:])))
    data_dir = args.data_dir or default_data_dir()
    config = Config.load(data_dir / "config.toml")
    registry = ParserRegistry.from_names(config.parser_order)

    try:
        if args.command == "start":
            return _run_start(args, data_dir, config, registry)
        if args.command == "preset":
            return _run_preset(args, data_dir, config, registry)
        if args.command == "log":
            return _run_log(args, data_dir)
    except (InvalidDurationError, KeyError) as exc:
        print(f"pytimer: {exc}", file=sys.stderr)
        return 2
    return 0


def build_parser() -> argparse.ArgumentParser:
    global_options = argparse.ArgumentParser(add_help=False)
    global_options.add_argument("--no-sound", action="store_true", help="disable completion sounds")
    global_options.add_argument("--minimal", action="store_true", help="use pipe-friendly output")
    global_options.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    global_options.add_argument("--data-dir", type=Path, help=argparse.SUPPRESS)

    parser = argparse.ArgumentParser(
        prog="pytimer",
        description="Terminal countdown timer",
        parents=[global_options],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser(
        "start",
        parents=[global_options],
        help="start one or more timers",
    )
    start.add_argument("durations", nargs="+", help="duration text such as 5m, 1:30:00, or '5 min'")
    start.add_argument("--label", help="label for the timer")

    preset = subparsers.add_parser("preset", parents=[global_options], help="run or manage presets")
    preset.add_argument("action", nargs="?", help="preset name, add, list, or remove")
    preset.add_argument("values", nargs="*", help="arguments for preset actions")

    log = subparsers.add_parser("log", parents=[global_options], help="show session log")
    log.add_argument("--last", type=int, default=10, help="number of recent rows to show")
    log.add_argument("--stats", action="store_true", help="group total time by label")
    return parser


def _normalize_argv(argv: list[str]) -> list[str]:
    skip_next = False
    for index, arg in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if arg == "--data-dir":
            skip_next = True
            continue
        if arg.startswith("-"):
            continue
        if arg in COMMANDS:
            return argv
        return [*argv[:index], "start", *argv[index:]]
    return argv


def _run_start(
    args: argparse.Namespace,
    data_dir: Path,
    config: Config,
    registry: ParserRegistry,
) -> int:
    engine = TimerEngine()
    for index, text in enumerate(args.durations, start=1):
        duration = registry.parse(text)
        label = args.label or format(duration, "compact")
        if len(args.durations) > 1 and args.label:
            label = f"{args.label} {index}"
        engine.add_timer(duration, label=label)
    _run_app(args, data_dir, config, engine)
    return 0


def _run_preset(
    args: argparse.Namespace,
    data_dir: Path,
    config: Config,
    registry: ParserRegistry,
) -> int:
    repository = JSONPresetRepository(data_dir / "presets.json", parser=registry)
    action = args.action or "list"
    if action == "list":
        for name, duration in repository.list().items():
            print(f"{name:<16} {format(duration, 'compact')}")
        return 0
    if action == "add":
        if len(args.values) != 2:
            raise InvalidDurationError("Usage: pytimer preset add <name> <duration>")
        name, text = args.values
        repository.add(name, registry.parse(text))
        print(f"Added preset {name}")
        return 0
    if action == "remove":
        if len(args.values) != 1:
            raise KeyError("Usage: pytimer preset remove <name>")
        repository.remove(args.values[0])
        print(f"Removed preset {args.values[0]}")
        return 0
    if args.values:
        raise KeyError("Usage: pytimer preset <name>")
    duration = repository.get(action)
    engine = TimerEngine()
    engine.add_timer(duration, label=action)
    _run_app(args, data_dir, config, engine)
    return 0


def _run_log(args: argparse.Namespace, data_dir: Path) -> int:
    log = SessionLog(data_dir / "sessions.jsonl")
    if args.stats:
        for label, duration in log.stats_by_label().items():
            print(f"{label:<24} {format(duration, 'pretty')}")
        return 0
    for record in log.recent(args.last):
        when = record.completed_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        pretty_duration = format(record.duration, "pretty")
        print(f"{when}  {record.status.value:<9}  {record.label:<24} {pretty_duration}")
    return 0


def _run_app(
    args: argparse.Namespace,
    data_dir: Path,
    config: Config,
    engine: TimerEngine,
) -> None:
    renderer_name = "minimal" if args.minimal else config.renderer
    color = not args.no_color and sys.stdout.isatty()
    renderer = build_renderer(renderer_name, color=color)
    notifier = build_notifier(config.notifiers, no_sound=args.no_sound)
    app = TimerApp(
        engine=engine,
        renderer=renderer,
        notifier=notifier,
        session_log=SessionLog(data_dir / "sessions.jsonl"),
        tick_rate_hz=config.tick_rate_hz,
    )
    app.run()
