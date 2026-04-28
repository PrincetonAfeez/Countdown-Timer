"""Duration value object.

The class stores one canonical value: total milliseconds. All display fields are
derived from that value, so equivalent inputs such as ``30s`` and ``0:30`` cannot
drift into subtly different internal representations.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering
from typing import Any

from .errors import InvalidDurationError

MILLIS_PER_SECOND = 1_000
MILLIS_PER_MINUTE = 60 * MILLIS_PER_SECOND
MILLIS_PER_HOUR = 60 * MILLIS_PER_MINUTE


@total_ordering
@dataclass(frozen=True)
class Duration:
    """Immutable duration stored as total milliseconds."""

    total_milliseconds: int

    def __post_init__(self) -> None:
        if isinstance(self.total_milliseconds, bool) or not isinstance(
            self.total_milliseconds, int
        ):
            raise InvalidDurationError("Duration must be stored as an integer millisecond value")
        if self.total_milliseconds < 0:
            raise InvalidDurationError("Duration cannot be negative")

    @classmethod
    def from_milliseconds(cls, milliseconds: int) -> Duration:
        return cls(milliseconds)

    @classmethod
    def from_seconds(cls, seconds: int | float) -> Duration:
        if isinstance(seconds, bool) or not isinstance(seconds, int | float):
            raise InvalidDurationError("Seconds must be numeric")
        if seconds < 0:
            raise InvalidDurationError("Duration cannot be negative")
        return cls(int(round(float(seconds) * MILLIS_PER_SECOND)))

    @property
    def hours(self) -> int:
        return self.total_milliseconds // MILLIS_PER_HOUR

    @property
    def minutes(self) -> int:
        return (self.total_milliseconds % MILLIS_PER_HOUR) // MILLIS_PER_MINUTE

    @property
    def seconds(self) -> int:
        return (self.total_milliseconds % MILLIS_PER_MINUTE) // MILLIS_PER_SECOND

    @property
    def millis(self) -> int:
        return self.total_milliseconds % MILLIS_PER_SECOND

    @property
    def total_seconds(self) -> float:
        return self.total_milliseconds / MILLIS_PER_SECOND

    def clamp_subtract(self, other: Duration) -> Duration:
        """Subtract without going below zero, useful for countdown displays."""

        return Duration(max(0, self.total_milliseconds - other.total_milliseconds))

    def __add__(self, other: object) -> Duration:
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(self.total_milliseconds + other.total_milliseconds)

    def __sub__(self, other: object) -> Duration:
        if not isinstance(other, Duration):
            return NotImplemented
        result = self.total_milliseconds - other.total_milliseconds
        if result < 0:
            raise InvalidDurationError("Duration subtraction cannot produce a negative value")
        return Duration(result)

    def __mul__(self, scalar: object) -> Duration:
        if isinstance(scalar, bool) or not isinstance(scalar, int | float):
            return NotImplemented
        if scalar < 0:
            raise InvalidDurationError("Duration cannot be multiplied by a negative value")
        return Duration(int(round(self.total_milliseconds * float(scalar))))

    def __rmul__(self, scalar: object) -> Duration:
        return self.__mul__(scalar)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Duration):
            return NotImplemented
        return self.total_milliseconds < other.total_milliseconds

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Duration) and self.total_milliseconds == other.total_milliseconds

    def __bool__(self) -> bool:
        return self.total_milliseconds != 0

    def __format__(self, spec: str) -> str:
        spec = spec or "hms"
        if spec == "hms":
            base = f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}"
            if self.millis:
                return f"{base}.{self.millis:03d}"
            return base
        if spec == "ms":
            return f"{self.total_milliseconds}ms"
        if spec == "compact":
            return self._format_compact()
        if spec == "pretty":
            return self._format_pretty()
        raise ValueError(f"Unsupported duration format specifier: {spec!r}")

    def _format_compact(self) -> str:
        parts: list[str] = []
        if self.hours:
            parts.append(f"{self.hours}h")
        if self.minutes:
            parts.append(f"{self.minutes}m")
        if self.seconds:
            parts.append(f"{self.seconds}s")
        if self.millis:
            parts.append(f"{self.millis}ms")
        return "".join(parts) if parts else "0ms"

    def _format_pretty(self) -> str:
        units = [
            ("hour", self.hours),
            ("minute", self.minutes),
            ("second", self.seconds),
            ("millisecond", self.millis),
        ]
        parts = [f"{value} {name}{'' if value == 1 else 's'}" for name, value in units if value]
        return ", ".join(parts) if parts else "0 milliseconds"
