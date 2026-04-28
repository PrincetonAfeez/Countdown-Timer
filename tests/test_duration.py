"""Test the duration"""

import pytest

from pytimer.duration import Duration
from pytimer.errors import InvalidDurationError


def test_duration_arithmetic_and_truthiness() -> None:
    thirty = Duration.from_seconds(30)
    ninety = Duration.from_seconds(90)

    assert thirty + ninety == Duration.from_seconds(120)
    assert ninety - thirty == Duration.from_seconds(60)
    assert thirty * 2 == Duration.from_seconds(60)
    assert ninety > thirty
    assert bool(Duration(0)) is False
    assert bool(thirty) is True


def test_duration_formats() -> None:
    duration = Duration(5_400_123)

    assert format(duration, "hms") == "01:30:00.123"
    assert format(duration, "ms") == "5400123ms"
    assert format(duration, "compact") == "1h30m123ms"
    assert format(duration, "pretty") == "1 hour, 30 minutes, 123 milliseconds"


def test_duration_rejects_negative_results() -> None:
    with pytest.raises(InvalidDurationError):
        Duration.from_seconds(1) - Duration.from_seconds(2)

