"""Interactive command registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .duration import Duration
from .engine import TimerEngine
from .errors import InvalidStateTransitionError, TimerNotFoundError
from .timer import TimerStatus


@dataclass
class AppState:
    """The state of the application"""
    active_timer_id: str | None = None
    show_help: bool = False
    shutdown_requested: bool = False
    default_add_duration: Duration = field(default_factory=lambda: Duration.from_seconds(5 * 60))
    adjust_step: Duration = field(default_factory=lambda: Duration.from_seconds(30))


class Command(ABC):
    """A command to execute against the engine and UI state"""
    description: str

    @abstractmethod
    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute a command against the engine and UI state."""


class PauseResumeCommand(Command):
    """Pause/resume the active timer"""
    description = "pause/resume active timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute the pause/resume command"""
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
    """Reset the active timer"""
    description = "reset active timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute the reset command"""
        timer_id = _active_timer_id(engine, state)
        if timer_id is None:
            return
        engine.reset(timer_id)
        engine.start(timer_id)


class AddCommand(Command):
    """Add a 5 minute timer"""
    description = "add a 5 minute timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute the add command"""
        label = f"timer {len(engine.list_timers()) + 1}"
        timer = engine.add_timer(state.default_add_duration, label=label)
        state.active_timer_id = timer.id
        if not any(existing.status == TimerStatus.RUNNING for existing in engine.list_timers()):
            engine.start(timer.id)


class DeleteCommand(Command):
    """Cancel the active timer"""
    description = "cancel active timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute the delete command"""
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
        """Initialize the adjust command"""
        self.subtract = subtract
        self.description = "subtract 30 seconds" if subtract else "add 30 seconds"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute the adjust command"""
        timer_id = _active_timer_id(engine, state)
        if timer_id is None:
            return
        try:
            engine.adjust(timer_id, state.adjust_step, subtract=self.subtract)
        except (InvalidStateTransitionError, ValueError):
            return


class NextCommand(Command):
    """Select the next timer in the list"""
    description = "select next timer"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute the next command"""
        _select_next(engine, state)


class HelpCommand(Command):
    """Toggle the help overlay"""
    description = "toggle help"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute the help command"""
        state.show_help = not state.show_help


class QuitCommand(Command):
    """Quit the application"""
    description = "quit"

    def execute(self, engine: TimerEngine, state: AppState) -> None:
        """Execute the quit command"""
        state.shutdown_requested = True


def default_command_registry() -> dict[str, Command]:
    """Get the default command registry"""
    return {
        "p": PauseResumeCommand(),
        "r": ResetCommand(),
        "a": AddCommand(),
        "d": DeleteCommand(),
        "+": AdjustCommand(subtract=False),
        "-": AdjustCommand(subtract=True),
        "n": NextCommand(),
        "?": HelpCommand(),
        "q": QuitCommand(),
    }


def render_help(commands: dict[str, Command]) -> str:
    """Render the help text"""
    rows = ["Keybindings", "-----------"]
    for key, command in commands.items():
        rows.append(f"{key:>2}  {command.description}")
    return "\n".join(rows)


def _active_timer_id(engine: TimerEngine, state: AppState) -> str | None:
    """Get the active timer id"""
    if state.active_timer_id is not None:
        try:
            engine.get_timer(state.active_timer_id)
            return state.active_timer_id
        except TimerNotFoundError:
            state.active_timer_id = None
    for timer in engine.list_timers():
        if timer.status in {TimerStatus.RUNNING, TimerStatus.PAUSED, TimerStatus.PENDING}:
            state.active_timer_id = timer.id
            return timer.id
    return None


def _select_next(engine: TimerEngine, state: AppState) -> None:
    """Select the next timer in the list"""
    timers = engine.list_timers()
    if not timers:
        state.active_timer_id = None
        return
    ids = [timer.id for timer in timers]
    if state.active_timer_id not in ids:
        state.active_timer_id = ids[0]
        return
    index = ids.index(state.active_timer_id)
    state.active_timer_id = ids[(index + 1) % len(ids)]

