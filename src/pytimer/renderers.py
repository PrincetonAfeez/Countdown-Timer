"""Pure renderers for terminal output."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from .duration import Duration
from .timer import Timer, TimerStatus, timer_remaining

ASCII_DIGITS: dict[str, tuple[str, ...]] = {
    "0": (" ### ", "#   #", "#   #", "#   #", " ### "),
    "1": ("  #  ", " ##  ", "  #  ", "  #  ", " ### "),
    "2": (" ### ", "#   #", "   # ", "  #  ", "#####"),
    "3": ("#### ", "    #", " ### ", "    #", "#### "),
    "4": ("#   #", "#   #", "#####", "    #", "    #"),
    "5": ("#####", "#    ", "#### ", "    #", "#### "),
    "6": (" ### ", "#    ", "#### ", "#   #", " ### "),
    "7": ("#####", "    #", "   # ", "  #  ", " #   "),
    "8": (" ### ", "#   #", " ### ", "#   #", " ### "),
    "9": (" ### ", "#   #", " ####", "    #", " ### "),
    ":": ("     ", "  #  ", "     ", "  #  ", "     "),
    " ": ("     ", "     ", "     ", "     ", "     "),
}

ANSI_RESET = "\033[0m"
ANSI_BY_STATUS = {
    TimerStatus.RUNNING: "\033[32m",
    TimerStatus.PAUSED: "\033[33m",
    TimerStatus.COMPLETED: "\033[31;1m",
    TimerStatus.CANCELLED: "\033[90m",
    TimerStatus.PENDING: "\033[36m",
}


class Renderer(ABC):
    def __init__(self, color: bool = True) -> None:
        self.color = color

    @abstractmethod
    def render(self, timers: list[Timer], now: float) -> str:
        """Return terminal output. Renderers never write to stdout."""


class BigRenderer(Renderer):
    def render(self, timers: list[Timer], now: float) -> str:
        if not timers:
            return "No timers. Press a to add one or q to quit."

        active = _select_active(timers)
        remaining = timer_remaining(active, now)
        clock = format_clock(remaining)
        big_clock = "\n".join(_ascii_clock(clock))
        status_line = _style(
            f"{active.label} [{active.status.value}] {format(remaining, 'hms')}",
            active.status,
            remaining,
            self.color,
        )
        progress = render_progress(active, now)
        others = [
            _timer_line(timer, now, color=self.color)
            for timer in timers
            if timer.id != active.id
        ]
        sections = [status_line, big_clock, progress]
        if others:
            sections.append("")
            sections.append("Other timers")
            sections.extend(others)
        return "\n".join(sections)


class CompactRenderer(Renderer):
    def render(self, timers: list[Timer], now: float) -> str:
        if not timers:
            return "No timers"
        return "\n".join(_timer_line(timer, now, color=self.color) for timer in timers)


class MinimalRenderer(Renderer):
    def __init__(self) -> None:
        super().__init__(color=False)

    def render(self, timers: list[Timer], now: float) -> str:
        if not timers:
            return "no timers"
        lines = []
        for timer in timers:
            remaining = timer_remaining(timer, now)
            lines.append(
                "|".join(
                    [
                        timer.id,
                        timer.label,
                        timer.status.value,
                        str(remaining.total_milliseconds),
                    ]
                )
            )
        return "\n".join(lines)


def build_renderer(name: str, color: bool = True) -> Renderer:
    if name == "minimal":
        return MinimalRenderer()
    if name == "compact":
        return CompactRenderer(color=color)
    return BigRenderer(color=color)


def format_clock(duration: Duration) -> str:
    total_seconds = math.ceil(duration.total_milliseconds / 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def render_progress(timer: Timer, now: float, width: int = 30) -> str:
    if not timer.original_duration:
        fraction = 1.0
    else:
        remaining = timer_remaining(timer, now).total_milliseconds
        elapsed = max(0, timer.original_duration.total_milliseconds - remaining)
        fraction = min(1.0, elapsed / timer.original_duration.total_milliseconds)
    filled = round(fraction * width)
    return "[" + ("█" * filled) + ("░" * (width - filled)) + f"] {fraction:>5.0%}"


def _ascii_clock(clock: str) -> list[str]:
    rows = ["", "", "", "", ""]
    for char in clock:
        glyph = ASCII_DIGITS.get(char, ASCII_DIGITS[" "])
        for index, row in enumerate(glyph):
            rows[index] += row + " "
    return rows


def _select_active(timers: list[Timer]) -> Timer:
    for status in (TimerStatus.RUNNING, TimerStatus.PAUSED, TimerStatus.PENDING):
        for timer in timers:
            if timer.status == status:
                return timer
    return timers[0]


def _timer_line(timer: Timer, now: float, color: bool) -> str:
    remaining = timer_remaining(timer, now)
    line = (
        f"{timer.id[:8]}  {timer.label:<18.18}  {timer.status.value:<9}  "
        f"{format(remaining, 'hms'):>12}  {render_progress(timer, now, width=16)}"
    )
    return _style(line, timer.status, remaining, color)


def _style(text: str, status: TimerStatus, remaining: Duration, color: bool) -> str:
    if not color:
        return text
    if status == TimerStatus.RUNNING and remaining.total_milliseconds <= 10_000:
        return f"\033[31m{text}{ANSI_RESET}"
    return f"{ANSI_BY_STATUS[status]}{text}{ANSI_RESET}"
