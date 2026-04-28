"""Test the timer engine"""

import pytest

from pytimer.duration import Duration
from pytimer.engine import TimerEngine
from pytimer.errors import InvalidStateTransitionError
from pytimer.events import TimerCompleted
from pytimer.time_source import FakeTimeSource
from pytimer.timer import TimerStatus


@pytest.fixture
def fake_time() -> FakeTimeSource:
    return FakeTimeSource()


@pytest.fixture
def engine(fake_time: FakeTimeSource) -> TimerEngine:
    return TimerEngine(time_source=fake_time)


def test_legal_start_pause_resume_cancel(engine: TimerEngine) -> None:
    timer = engine.add_timer(Duration.from_seconds(30), label="stretch")

    assert engine.start(timer.id).status == TimerStatus.RUNNING
    assert engine.pause(timer.id).status == TimerStatus.PAUSED
    assert engine.resume(timer.id).status == TimerStatus.RUNNING
    assert engine.cancel(timer.id).status == TimerStatus.CANCELLED


def test_illegal_resume_completed_timer(
    engine: TimerEngine,
    fake_time: FakeTimeSource,
) -> None:
    timer = engine.add_timer(Duration.from_seconds(1), label="tiny")

    engine.start(timer.id)
    fake_time.advance(1)
    engine.tick()

    with pytest.raises(InvalidStateTransitionError):
        engine.resume(timer.id)


def test_pause_resume_arithmetic_excludes_paused_time(
    engine: TimerEngine,
    fake_time: FakeTimeSource,
) -> None:
    timer = engine.add_timer(Duration.from_seconds(60), label="focus")

    engine.start(timer.id)
    fake_time.advance(10)
    engine.pause(timer.id)
    fake_time.advance(30)
    engine.resume(timer.id)
    fake_time.advance(5)

    assert engine.remaining(timer.id) == Duration.from_seconds(45)


def test_tick_completes_and_emits_event(
    engine: TimerEngine,
    fake_time: FakeTimeSource,
) -> None:
    completed: list[TimerCompleted] = []
    engine.events.subscribe(TimerCompleted, completed.append)
    timer = engine.add_timer(Duration.from_seconds(2), label="tea")

    engine.start(timer.id)
    fake_time.advance(2)
    tick_completed = engine.tick()

    assert tick_completed[0].status == TimerStatus.COMPLETED
    assert completed[0].timer.id == timer.id
    assert engine.remaining(timer.id) == Duration(0)


def test_fake_time_context_manager_swaps_source() -> None:
    engine = TimerEngine(time_source=FakeTimeSource(10))
    replacement = FakeTimeSource(99)

    with engine.fake_time(replacement):
        assert engine.time_source.monotonic() == 99

    assert engine.time_source.monotonic() == 10

