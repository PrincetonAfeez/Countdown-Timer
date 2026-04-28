from __future__ import annotations

import queue
import signal
import threading
import time
from collections.abc import Callable
from types import FrameType

from .commands import AppState, Command, default_command_registry, render_help
from .display import Display, raw_terminal, read_key_nonblocking, sleep_until_next_tick
from .engine import TimerEngine
from .errors import InvalidStateTransitionError
from .events import TimerCancelled, TimerCompleted
from .notifiers import Notifier
from .persistence import SessionLog
from .renderers import Renderer
from .timer import TimerStatus

SignalHandler = Callable[[int, FrameType | None], object] | int | None


class TimerApp:
    def __init__(
        self,
        engine: TimerEngine,
        renderer: Renderer,
        notifier: Notifier,
        session_log: SessionLog,
        tick_rate_hz: float = 10.0,
        commands: dict[str, Command] | None = None,
        display: Display | None = None,
    ) -> None:
        self.engine = engine
        self.renderer = renderer
        self.notifier = notifier
        self.session_log = session_log
        self.tick_rate_hz = tick_rate_hz
        self.commands = commands or default_command_registry()
        self.state = AppState()
        self.display = display or Display()
        self._keys: queue.Queue[str] = queue.Queue()
        self._stop_input = threading.Event()
        self.engine.events.subscribe(TimerCompleted, self._on_completed)
        self.engine.events.subscribe(TimerCancelled, self._on_cancelled)
