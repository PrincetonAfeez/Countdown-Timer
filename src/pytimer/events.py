"""Tiny observer pattern implementation for timer events."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar, cast

from .timer import Timer


class Event:
    """Marker base class for all events."""


@dataclass(frozen=True)
class TimerStarted(Event):
    timer: Timer


@dataclass(frozen=True)
class TimerPaused(Event):
    timer: Timer


@dataclass(frozen=True)
class TimerResumed(Event):
    timer: Timer


@dataclass(frozen=True)
class TimerCompleted(Event):
    timer: Timer


@dataclass(frozen=True)
class TimerCancelled(Event):
    timer: Timer


@dataclass(frozen=True)
class TimerTick(Event):
    timers: tuple[Timer, ...]
    now: float


E = TypeVar("E", bound=Event)
E_contra = TypeVar("E_contra", bound=Event, contravariant=True)


class EventHandler(Protocol[E_contra]):
    def __call__(self, event: E_contra) -> None:
        """Handle an event."""


class EventBus:
    def __init__(self) -> None:
        self._handlers: defaultdict[type[Event], list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: EventHandler[E]) -> None:
        self._handlers[event_type].append(cast(Callable[[Event], None], handler))

    def publish(self, event: Event) -> None:
        for event_type, handlers in list(self._handlers.items()):
            if isinstance(event, event_type):
                for handler in list(handlers):
                    handler(event)
