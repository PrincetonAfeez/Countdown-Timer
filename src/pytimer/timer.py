"""Timer state and pure timing functions."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from .duration import Duration


class TimerStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Legal state transitions:
# PENDING   -> RUNNING, CANCELLED
# RUNNING   -> PAUSED, COMPLETED, CANCELLED
# PAUSED    -> RUNNING, CANCELLED
# COMPLETED -> terminal
# CANCELLED -> terminal
LEGAL_TRANSITIONS: dict[TimerStatus, set[TimerStatus]] = {
    TimerStatus.PENDING: {TimerStatus.RUNNING, TimerStatus.CANCELLED},
    TimerStatus.RUNNING: {TimerStatus.PAUSED, TimerStatus.COMPLETED, TimerStatus.CANCELLED},
    TimerStatus.PAUSED: {TimerStatus.RUNNING, TimerStatus.CANCELLED},
    TimerStatus.COMPLETED: set(),
    TimerStatus.CANCELLED: set(),
}


@dataclass(frozen=True)
class Timer:
    id: str
    label: str
    original_duration: Duration
    created_at: float
    status: TimerStatus = TimerStatus.PENDING
    start_monotonic: float | None = None
    pause_started_at: float | None = None
    paused_elapsed: Duration = field(default_factory=lambda: Duration(0))
    ended_at: float | None = None

    def with_changes(self, **changes: Any) -> Timer:
        return replace(self, **changes)


def elapsed_duration(timer: Timer, now_monotonic: float) -> Duration:
    """Return active elapsed time, excluding pauses."""

    if timer.start_monotonic is None:
        return Duration(0)

    effective_now = now_monotonic
    if timer.status == TimerStatus.PAUSED and timer.pause_started_at is not None:
        effective_now = timer.pause_started_at
    elif timer.ended_at is not None:
        effective_now = timer.ended_at

    elapsed_seconds = max(
        0.0,
        effective_now - timer.start_monotonic - timer.paused_elapsed.total_seconds,
    )
    return Duration.from_seconds(elapsed_seconds)


def remaining_time(
    original_duration: Duration,
    start_monotonic: float | None,
    paused_elapsed: Duration,
    now_monotonic: float,
    status: TimerStatus,
    pause_started_at: float | None = None,
    ended_at: float | None = None,
) -> Duration:
    """Pure countdown calculation used by the engine and renderers."""

    if status == TimerStatus.PENDING or start_monotonic is None:
        return original_duration
    if status == TimerStatus.COMPLETED:
        return Duration(0)

    effective_now = now_monotonic
    if status == TimerStatus.PAUSED and pause_started_at is not None:
        effective_now = pause_started_at
    elif ended_at is not None:
        effective_now = ended_at

    elapsed = Duration.from_seconds(
        max(0.0, effective_now - start_monotonic - paused_elapsed.total_seconds)
    )
    return original_duration.clamp_subtract(elapsed)


def timer_remaining(timer: Timer, now_monotonic: float) -> Duration:
    return remaining_time(
        timer.original_duration,
        timer.start_monotonic,
        timer.paused_elapsed,
        now_monotonic,
        timer.status,
        timer.pause_started_at,
        timer.ended_at,
    )
