"""Test the parsers"""

import pytest

from pytimer.duration import Duration
from pytimer.errors import InvalidDurationError
from pytimer.parsers import ParserRegistry


@pytest.mark.parametrize(
    ("text", "expected_ms"),
    [
        ("5m", 300_000),
        ("1h30m", 5_400_000),
        ("90s", 90_000),
        ("2h15m30s", 8_130_000),
        ("500ms", 500),
        ("5:00", 300_000),
        ("1:30:00", 5_400_000),
        ("00:00:10", 10_000),
        ("5 minutes", 300_000),
        ("1 hour 30 min", 5_400_000),
        ("ninety seconds", 90_000),
    ],
)
def test_parser_registry_accepts_supported_formats(text: str, expected_ms: int) -> None:
    assert ParserRegistry().parse(text) == Duration(expected_ms)


@pytest.mark.parametrize("text", ["", "-5m", "1:99", "five", "tomorrow"])
def test_parser_registry_rejects_invalid_formats(text: str) -> None:
    with pytest.raises(InvalidDurationError, match="Accepted formats"):
        ParserRegistry().parse(text)


def test_parser_registry_can_be_ordered() -> None:
    registry = ParserRegistry.from_names(["colon"])

    assert registry.parse("1:00") == Duration.from_seconds(60)
    with pytest.raises(InvalidDurationError):
        registry.parse("1m")

