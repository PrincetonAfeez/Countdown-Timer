"""Timer engine and explicit state transitions."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

from .duration import Duration
from .errors import InvalidDurationError, InvalidStateTransitionError, TimerNotFoundError
from .events import (
    EventBus,
    TimerCancelled,
    TimerCompleted,
    TimerPaused,
    TimerResumed,
    TimerStarted,
    TimerTick,
)
from .time_source import SystemTimeSource, TimeSource
from .timer import LEGAL_TRANSITIONS, Timer, TimerStatus, timer_remaining


class TimerEngine:
    """Manage timers through validated state transitions."""

    def __init__(
        self,
        time_source: TimeSource | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.time_source: TimeSource = time_source or SystemTimeSource()
        self.events = event_bus or EventBus()
        self._timers: dict[str, Timer] = {}

    def add_timer(
        self,
        duration: Duration,
        label: str | None = None,
        timer_id: str | None = None,
    ) -> Timer:
        timer_id = timer_id or uuid4().hex
        label = label or format(duration, "compact")
        timer = Timer(
            id=timer_id,
            label=label,
            original_duration=duration,
            created_at=self.time_source.monotonic(),
        )
        self._timers[timer.id] = timer
        return timer

    def list_timers(self) -> list[Timer]:
        return sorted(self._timers.values(), key=lambda timer: timer.created_at)

    def get_timer(self, timer_id: str) -> Timer:
        try:
            return self._timers[timer_id]
        except KeyError as exc:
            raise TimerNotFoundError(f"Unknown timer id: {timer_id}") from exc

    def remaining(self, timer_id: str, now: float | None = None) -> Duration:
        now = self.time_source.monotonic() if now is None else now
        return timer_remaining(self.get_timer(timer_id), now)

    def start(self, timer_id: str) -> Timer:
        timer = self.get_timer(timer_id)
        self._validate_transition(timer, TimerStatus.RUNNING)
        now = self.time_source.monotonic()
        updated = timer.with_changes(
            status=TimerStatus.RUNNING,
            start_monotonic=now,
            pause_started_at=None,
            paused_elapsed=Duration(0),
            ended_at=None,
        )
        self._store(updated)
        self.events.publish(TimerStarted(updated))
        return updated

    def pause(self, timer_id: str) -> Timer:
        timer = self.get_timer(timer_id)
        self._validate_transition(timer, TimerStatus.PAUSED)
        updated = timer.with_changes(
            status=TimerStatus.PAUSED,
            pause_started_at=self.time_source.monotonic(),
        )
        self._store(updated)
        self.events.publish(TimerPaused(updated))
        return updated

    def resume(self, timer_id: str) -> Timer:
        timer = self.get_timer(timer_id)
        self._validate_transition(timer, TimerStatus.RUNNING)
        now = self.time_source.monotonic()
        if timer.pause_started_at is None:
            raise InvalidStateTransitionError("Cannot resume a timer without pause state")
        paused_elapsed = timer.paused_elapsed + Duration.from_seconds(now - timer.pause_started_at)
        updated = timer.with_changes(
            status=TimerStatus.RUNNING,
            pause_started_at=None,
            paused_elapsed=paused_elapsed,
        )
        self._store(updated)
        self.events.publish(TimerResumed(updated))
        return updated

    def cancel(self, timer_id: str) -> Timer:
        timer = self.get_timer(timer_id)
        self._validate_transition(timer, TimerStatus.CANCELLED)
        updated = timer.with_changes(
            status=TimerStatus.CANCELLED,
            ended_at=self.time_source.monotonic(),
        )
        self._store(updated)
        self.events.publish(TimerCancelled(updated))
        return updated

    def reset(self, timer_id: str) -> Timer:
        timer = self.get_timer(timer_id)
        updated = timer.with_changes(
            status=TimerStatus.PENDING,
            start_monotonic=None,
            pause_started_at=None,
            paused_elapsed=Duration(0),
            ended_at=None,
        )
        self._store(updated)
        return updated

    def adjust(self, timer_id: str, delta: Duration, subtract: bool = False) -> Timer:
        timer = self.get_timer(timer_id)
        if timer.status in {TimerStatus.COMPLETED, TimerStatus.CANCELLED}:
            raise InvalidStateTransitionError("Cannot adjust a terminal timer")
        signed_delta = -delta.total_milliseconds if subtract else delta.total_milliseconds
        new_total = timer.original_duration.total_milliseconds + signed_delta
        if new_total < 0:
            raise InvalidDurationError("Timer duration cannot be adjusted below zero")
        updated = timer.with_changes(original_duration=Duration(new_total))
        self._store(updated)
        return updated

    def tick(self) -> list[Timer]:
        now = self.time_source.monotonic()
        completed: list[Timer] = []
        for timer in self.list_timers():
            if timer.status != TimerStatus.RUNNING:
                continue
            if not timer_remaining(timer, now):
                completed.append(self._complete(timer, now))
        self.events.publish(TimerTick(tuple(self.list_timers()), now))
        return completed

    @contextmanager
    def fake_time(self, source: TimeSource) -> Iterator[TimerEngine]:
        previous = self.time_source
        self.time_source = source
        try:
            yield self
        finally:
            self.time_source = previous

    def _complete(self, timer: Timer, now: float) -> Timer:
        self._validate_transition(timer, TimerStatus.COMPLETED)
        updated = timer.with_changes(status=TimerStatus.COMPLETED, ended_at=now)
        self._store(updated)
        self.events.publish(TimerCompleted(updated))
        return updated

    def _store(self, timer: Timer) -> None:
        self._timers[timer.id] = timer

    def _validate_transition(self, timer: Timer, target: TimerStatus) -> None:
        if target not in LEGAL_TRANSITIONS[timer.status]:
            raise InvalidStateTransitionError(
                f"Cannot transition timer {timer.id!r} from {timer.status.value} to {target.value}"
            )
