"""Completion notification strategies."""

from __future__ import annotations

import logging
import sys
import time
from typing import Protocol, TextIO

from .timer import Timer

LOGGER = logging.getLogger(__name__)


class Notifier(Protocol):
    def notify(self, timer: Timer) -> None:
        """Notify that a timer completed."""


class BellNotifier:
    def __init__(self, output: TextIO | None = None) -> None:
        self.output = output or sys.stdout

    def notify(self, timer: Timer) -> None:
        self.output.write("\a")
        self.output.flush()


class BannerNotifier:
    def __init__(self, output: TextIO | None = None, seconds: float = 3.0) -> None:
        self.output = output or sys.stdout
        self.seconds = seconds

    def notify(self, timer: Timer) -> None:
        message = f" TIMER COMPLETE: {timer.label} "
        banner = "\033[2J\033[H\033[41;97;1m" + message.center(80) + "\033[0m\n"
        self.output.write(banner)
        self.output.flush()
        time.sleep(self.seconds)


class DesktopNotifier:
    def __init__(self, app_name: str = "pytimer") -> None:
        self.app_name = app_name
        self._warned = False

    def notify(self, timer: Timer) -> None:
        try:
            from plyer import notification  # type: ignore[import-not-found]
        except ImportError:
            if not self._warned:
                LOGGER.warning(
                    "Desktop notifications unavailable; install pytimer-countdown[desktop]"
                )
                self._warned = True
            return
        notification.notify(
            title=f"{timer.label} complete",
            message=f"{format(timer.original_duration, 'pretty')} finished",
            app_name=self.app_name,
        )


class CompositeNotifier:
    def __init__(self, notifiers: list[Notifier] | tuple[Notifier, ...]) -> None:
        self.notifiers = tuple(notifiers)

    def notify(self, timer: Timer) -> None:
        for notifier in self.notifiers:
            notifier.notify(timer)


class NullNotifier:
    def notify(self, timer: Timer) -> None:
        return None


def build_notifier(names: tuple[str, ...], no_sound: bool = False) -> Notifier:
    if no_sound:
        return NullNotifier()
    builders = {
        "bell": BellNotifier,
        "banner": BannerNotifier,
        "desktop": DesktopNotifier,
    }
    notifiers = [builders[name]() for name in names if name in builders]
    return CompositeNotifier(notifiers) if notifiers else NullNotifier()
