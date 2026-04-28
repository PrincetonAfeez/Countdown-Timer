"""Test the app loop with a fake time source"""

from io import StringIO

from pytimer.app import TimerApp
from pytimer.display import Display
from pytimer.duration import Duration
from pytimer.engine import TimerEngine
from pytimer.notifiers import NullNotifier
from pytimer.persistence import SessionLog
from pytimer.renderers import MinimalRenderer
from pytimer.time_source import FakeTimeSource
from pytimer.timer import TimerStatus


def test_threaded_app_loop_exits_after_timer_completion(tmp_path) -> None:
    source = FakeTimeSource()
    engine = TimerEngine(time_source=source)
    engine.add_timer(Duration(0), label="instant")
    output = StringIO()
    app = TimerApp(
        engine=engine,
        renderer=MinimalRenderer(),
        notifier=NullNotifier(),
        session_log=SessionLog(tmp_path / "sessions.jsonl"),
        tick_rate_hz=100,
        display=Display(output=output, ansi=False),
    )

    app.run()

    assert engine.list_timers()[0].status == TimerStatus.COMPLETED
    assert "instant" in output.getvalue()

