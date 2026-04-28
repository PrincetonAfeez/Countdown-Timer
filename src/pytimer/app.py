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


    def run(self) -> None:
        self._start_next_pending_if_idle()
        previous_handlers = self._install_signal_handlers()
        input_thread = threading.Thread(target=self._read_input, name="pytimer-input", daemon=True)
        input_thread.start()

        try:
            with raw_terminal():
                while True:
                    tick_started_at = time.monotonic()
                    self._drain_keys()
                    self.engine.tick()
                    self._start_next_pending_if_idle()
                    self._render()

                    if self.state.shutdown_requested:
                        self._cancel_open_timers()
                        break
                    if self._all_timers_terminal():
                        break

                    sleep_until_next_tick(tick_started_at, 1 / self.tick_rate_hz)
        finally:
            self._stop_input.set()
            input_thread.join(timeout=1.0)
            self._restore_signal_handlers(previous_handlers)
            self.display.close()

    def _render(self) -> None:
        now = self.engine.time_source.monotonic()
        rendered = self.renderer.render(self.engine.list_timers(), now)
        if self.state.show_help:
            rendered = f"{rendered}\n\n{render_help(self.commands)}"
        self.display.render(rendered)


    def _drain_keys(self) -> None:
        while True:
            try:
                key = self._keys.get_nowait()
            except queue.Empty:
                return
            command = self.commands.get(key)
            if command is not None:
                command.execute(self.engine, self.state)

    def _read_input(self) -> None:
        while not self._stop_input.is_set():
            try:
                key = read_key_nonblocking()
            except KeyboardInterrupt:
                self.state.shutdown_requested = True
                return
            if key:
                self._keys.put(key)
            time.sleep(0.02)

    def _start_next_pending_if_idle(self) -> None:
        timers = self.engine.list_timers()
        if any(timer.status in {TimerStatus.RUNNING, TimerStatus.PAUSED} for timer in timers):
            return
        for timer in timers:
            if timer.status == TimerStatus.PENDING:
                self.engine.start(timer.id)
                self.state.active_timer_id = timer.id
                return

    def _cancel_open_timers(self) -> None:
        for timer in self.engine.list_timers():
            if timer.status in {TimerStatus.PENDING, TimerStatus.RUNNING, TimerStatus.PAUSED}:
                try:
                    self.engine.cancel(timer.id)
                except InvalidStateTransitionError:
                    continue

