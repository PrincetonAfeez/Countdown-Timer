"""Test the event bus"""

from pytimer.duration import Duration
from pytimer.engine import TimerEngine
from pytimer.events import Event, EventBus, TimerStarted
from pytimer.time_source import FakeTimeSource


def test_event_bus_calls_matching_subscribers() -> None:
    bus = EventBus()
    seen: list[Event] = []
    started: list[TimerStarted] = []
    engine = TimerEngine(time_source=FakeTimeSource(), event_bus=bus)
    timer = engine.add_timer(Duration.from_seconds(5), label="tea")

    bus.subscribe(Event, seen.append)
    bus.subscribe(TimerStarted, started.append)
    engine.start(timer.id)

    assert len(seen) == 1
    assert started[0].timer.label == "tea"

