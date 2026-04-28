"""Terminal display and keyboard helpers."""

from __future__ import annotations

import contextlib
import os
import select
import sys
import time
from collections.abc import Iterator
from typing import Any, TextIO


class Display:
    """Own stdout and redraw only when the rendered string changes."""

    def __init__(self, output: TextIO | None = None, ansi: bool = True) -> None:
        self.output = output or sys.stdout
        self.ansi = ansi
        self._last = ""

    def render(self, text: str) -> None:
        if text == self._last:
            return
        self._last = text
        if self.ansi:
            self._write("\033[?25l\033[H\033[2J")
        self._write(text)
        if not text.endswith("\n"):
            self._write("\n")
        self.output.flush()

    def close(self) -> None:
        if self.ansi:
            self._write("\033[0m\033[?25h")
            self.output.flush()

    def _write(self, text: str) -> None:
        try:
            self.output.write(text)
        except UnicodeEncodeError:
            encoding = self.output.encoding or "utf-8"
            safe = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
            self.output.write(safe)


@contextlib.contextmanager
def raw_terminal() -> Iterator[None]:
    """Set cbreak mode on Unix. Windows uses msvcrt polling instead."""

    if os.name == "nt" or not sys.stdin.isatty():
        yield
        return

    termios: Any = __import__("termios")
    tty: Any = __import__("tty")

    file_descriptor = sys.stdin.fileno()
    previous = termios.tcgetattr(file_descriptor)
    try:
        tty.setcbreak(file_descriptor)
        yield
    finally:
        termios.tcsetattr(file_descriptor, termios.TCSADRAIN, previous)


def read_key_nonblocking() -> str | None:
    if not sys.stdin.isatty():
        return None
    if os.name == "nt":
        return _read_windows_key()
    readable, _, _ = select.select([sys.stdin], [], [], 0)
    if readable:
        return sys.stdin.read(1)
    return None


def _read_windows_key() -> str | None:
    import msvcrt

    if not msvcrt.kbhit():
        return None
    key = msvcrt.getwch()
    if key in {"\x00", "\xe0"}:
        msvcrt.getwch()
        return None
    if key == "\x03":
        raise KeyboardInterrupt
    return key


def sleep_until_next_tick(started_at: float, tick_seconds: float) -> None:
    elapsed = time.monotonic() - started_at
    time.sleep(max(0.0, tick_seconds - elapsed))
