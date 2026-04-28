"""Injectable time sources."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol


class TimeSource(Protocol):
    def monotonic(self) -> float:
        """Return a monotonic timestamp in seconds."""


class SystemTimeSource:
    def monotonic(self) -> float:
        return time.monotonic()


@dataclass
class FakeTimeSource:
    current: float = 0.0

    def monotonic(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("Fake time cannot move backwards")
        self.current += seconds

