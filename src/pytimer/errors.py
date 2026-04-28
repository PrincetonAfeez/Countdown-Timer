"""Custom exception hierarchy for the timer application."""


class TimerError(Exception):
    """Base class for all timer-specific errors."""


class InvalidDurationError(TimerError, ValueError):
    """Raised when duration text or arithmetic would create an invalid duration."""


class TimerNotFoundError(TimerError, LookupError):
    """Raised when a timer id is unknown to the engine."""


class InvalidStateTransitionError(TimerError, RuntimeError):
    """Raised when a timer transition is not legal for its current state."""

