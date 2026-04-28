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
        

