"""Test the renderers"""

from pytimer.duration import Duration
from pytimer.engine import TimerEngine
from pytimer.renderers import BigRenderer, MinimalRenderer
from pytimer.time_source import FakeTimeSource


def test_big_renderer_returns_string_without_writing() -> None:
    source = FakeTimeSource()
    engine = TimerEngine(time_source=source)
    timer = engine.add_timer(Duration.from_seconds(5), label="tea")
    engine.start(timer.id)

    output = BigRenderer(color=False).render(engine.list_timers(), source.monotonic())

    assert "tea [running]" in output
    assert "00:05" in output
    assert "[" in output and "]" in output


def test_minimal_renderer_is_pipe_friendly() -> None:
    source = FakeTimeSource()
    engine = TimerEngine(time_source=source)
    timer = engine.add_timer(Duration.from_seconds(5), label="tea")

    output = MinimalRenderer().render(engine.list_timers(), source.monotonic())

    assert output == f"{timer.id}|tea|pending|5000"

