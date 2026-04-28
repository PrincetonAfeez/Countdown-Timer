from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .duration import Duration
from .engine import TimerEngine
from .errors import InvalidStateTransitionError, TimerNotFoundError
from .timer import TimerStatus


@dataclass
class AppState:
    active_timer_id: str | None = None
    show_help: bool = False
    shutdown_requested: bool = False
    default_add_duration: Duration = field(default_factory=lambda: Duration.from_seconds(5 * 60))
    adjust_step: Duration = field(default_factory=lambda: Duration.from_seconds(30))


class Command(ABC):
    description: str

    @abstractmethod
    def execute(self, engine: TimerEngine, state: AppState) -> None:
        

class PauseResumeCommand(Command):
    description = "pause/resume active timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        timer_id = _active_timer_id(engine, state)
        if timer_id is None:
            return
        timer = engine.get_timer(timer_id)
        if timer.status == TimerStatus.PENDING:
            engine.start(timer_id)
        elif timer.status == TimerStatus.RUNNING:
            engine.pause(timer_id)
        elif timer.status == TimerStatus.PAUSED:
            engine.resume(timer_id)

class ResetCommand(Command):
    description = "reset active timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        timer_id = _active_timer_id(engine, state)
        if timer_id is None:
            return
        engine.reset(timer_id)
        engine.start(timer_id)


class ResetCommand(Command):
    description = "reset active timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        timer_id = _active_timer_id(engine, state)
        if timer_id is None:
            return
        engine.reset(timer_id)
        engine.start(timer_id)

class AddCommand(Command):
    description = "add a 5 minute timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        label = f"timer {len(engine.list_timers()) + 1}"
        timer = engine.add_timer(state.default_add_duration, label=label)
        state.active_timer_id = timer.id
        if not any(existing.status == TimerStatus.RUNNING for existing in engine.list_timers()):
            engine.start(timer.id)

class DeleteCommand(Command):
    description = "cancel active timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        timer_id = _active_timer_id(engine, state)
        if timer_id is None:
            return
        try:
            engine.cancel(timer_id)
        except InvalidStateTransitionError:
            return
        _select_next(engine, state)

class AdjustCommand(Command):
    def __init__(self, subtract: bool) -> None:
        self.subtract = subtract
        self.description = "subtract 30 seconds" if subtract else "add 30 seconds"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        timer_id = _active_timer_id(engine, state)
        if timer_id is None:
            return
        try:
            engine.adjust(timer_id, state.adjust_step, subtract=self.subtract)
        except (InvalidStateTransitionError, ValueError):
            return

class NextCommand(Command):
    description = "select next timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        _select_next(engine, state)

class HelpCommand(Command):
    description = "toggle help"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        state.show_help = not state.show_help

