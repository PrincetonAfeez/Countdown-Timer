"""Duration parsing strategies."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .duration import (
    MILLIS_PER_HOUR,
    MILLIS_PER_MINUTE,
    MILLIS_PER_SECOND,
    Duration,
)
from .errors import InvalidDurationError


class DurationParser(Protocol):
    name: str

    def parse(self, text: str) -> Duration:
        """Parse text into a duration or raise InvalidDurationError."""


class CompactParser:
    name = "compact"
    _token_re = re.compile(r"(?P<value>\d+(?:\.\d+)?)(?P<unit>ms|h|m|s)", re.IGNORECASE)
    _multipliers = {
        "h": MILLIS_PER_HOUR,
        "m": MILLIS_PER_MINUTE,
        "s": MILLIS_PER_SECOND,
        "ms": 1,
    }

    def parse(self, text: str) -> Duration:
        cleaned = text.strip().lower()
        if not cleaned:
            raise InvalidDurationError("Empty duration")

        position = 0
        total = 0.0
        matched = False
        for match in self._token_re.finditer(cleaned):
            if match.start() != position:
                raise InvalidDurationError(f"Invalid compact duration: {text!r}")
            matched = True
            total += float(match.group("value")) * self._multipliers[match.group("unit")]
            position = match.end()

        if not matched or position != len(cleaned):
            raise InvalidDurationError(f"Invalid compact duration: {text!r}")
        return Duration(int(round(total)))


class ColonParser:
    name = "colon"
    _colon_re = re.compile(r"^\s*(?P<parts>\d+(?::\d{1,2}){1,2})\s*$")

    def parse(self, text: str) -> Duration:
        match = self._colon_re.match(text)
        if not match:
            raise InvalidDurationError(f"Invalid colon duration: {text!r}")
        raw_parts = [int(part) for part in match.group("parts").split(":")]
        if len(raw_parts) == 2:
            hours = 0
            minutes, seconds = raw_parts
        elif len(raw_parts) == 3:
            hours, minutes, seconds = raw_parts
        else:
            raise InvalidDurationError(f"Invalid colon duration: {text!r}")
        if minutes >= 60 or seconds >= 60:
            raise InvalidDurationError("Minutes and seconds must be less than 60")
        return Duration(
            hours * MILLIS_PER_HOUR + minutes * MILLIS_PER_MINUTE + seconds * MILLIS_PER_SECOND
        )


class NaturalParser:
    name = "natural"
    _unit_multipliers = {
        "millisecond": 1,
        "milliseconds": 1,
        "milli": 1,
        "millis": 1,
        "hour": MILLIS_PER_HOUR,
        "hours": MILLIS_PER_HOUR,
        "hr": MILLIS_PER_HOUR,
        "hrs": MILLIS_PER_HOUR,
        "minute": MILLIS_PER_MINUTE,
        "minutes": MILLIS_PER_MINUTE,
        "min": MILLIS_PER_MINUTE,
        "mins": MILLIS_PER_MINUTE,
        "second": MILLIS_PER_SECOND,
        "seconds": MILLIS_PER_SECOND,
        "sec": MILLIS_PER_SECOND,
        "secs": MILLIS_PER_SECOND,
    }
    _ones = {
        "zero": 0,
        "one": 1,
        "a": 1,
        "an": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
    }
    _tens = {
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }

    def parse(self, text: str) -> Duration:
        tokens = re.findall(r"[a-zA-Z]+|\d+", text.lower().replace("-", " "))
        if not tokens:
            raise InvalidDurationError("Empty duration")

        total = 0
        amount_tokens: list[str] = []
        matched = False
        for token in tokens:
            if token == "and":
                continue
            if token in self._unit_multipliers:
                if not amount_tokens:
                    raise InvalidDurationError(f"Missing amount before {token!r}")
                amount = self._parse_amount(amount_tokens)
                total += amount * self._unit_multipliers[token]
                amount_tokens = []
                matched = True
            else:
                amount_tokens.append(token)

        if amount_tokens or not matched:
            raise InvalidDurationError(f"Invalid natural duration: {text!r}")
        return Duration(total)

    def _parse_amount(self, tokens: Iterable[str]) -> int:
        token_list = list(tokens)
        if len(token_list) == 1 and token_list[0].isdigit():
            return int(token_list[0])

        total = 0
        current = 0
        for token in token_list:
            if token.isdigit():
                current += int(token)
            elif token in self._ones:
                current += self._ones[token]
            elif token in self._tens:
                current += self._tens[token]
            elif token == "hundred":
                current = max(1, current) * 100
            else:
                raise InvalidDurationError(f"Unknown number word: {token!r}")
        total += current
        return total


@dataclass(frozen=True)
class ParserRegistry:
    parsers: tuple[DurationParser, ...] = (CompactParser(), ColonParser(), NaturalParser())

    @classmethod
    def from_names(cls, names: Iterable[str]) -> ParserRegistry:
        available: dict[str, DurationParser] = {
            "compact": CompactParser(),
            "colon": ColonParser(),
            "natural": NaturalParser(),
        }
        selected = tuple(available[name] for name in names if name in available)
        return cls(selected or tuple(available.values()))

    def parse(self, text: str) -> Duration:
        errors: list[str] = []
        for parser in self.parsers:
            try:
                return parser.parse(text)
            except InvalidDurationError as exc:
                errors.append(f"{parser.name}: {exc}")
        accepted = "compact (5m, 1h30m, 500ms), colon (5:00, 1:30:00), natural (5 minutes)"
        raise InvalidDurationError(
            f"Could not parse {text!r}. Accepted formats: {accepted}. Details: {'; '.join(errors)}"
        )
