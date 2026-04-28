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
