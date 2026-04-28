"""Config, preset repository, and JSONL session logging."""

from __future__ import annotations

import json
import tomllib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .duration import Duration
from .parsers import ParserRegistry
from .timer import Timer, TimerStatus


def default_data_dir() -> Path:
    return Path.home() / ".pytimer"


@dataclass(frozen=True)
class Config:
    tick_rate_hz: float = 10.0
    renderer: str = "big"
    notifiers: tuple[str, ...] = ("bell",)
    color_scheme: str = "default"
    parser_order: tuple[str, ...] = ("compact", "colon", "natural")
    bell_volume: float = 1.0

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or default_data_dir() / "config.toml"
        if not path.exists():
            return cls()
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls(
            tick_rate_hz=float(data.get("tick_rate_hz", cls.tick_rate_hz)),
            renderer=str(data.get("renderer", cls.renderer)),
            notifiers=tuple(data.get("notifiers", cls.notifiers)),
            color_scheme=str(data.get("color_scheme", cls.color_scheme)),
            parser_order=tuple(data.get("parser_order", cls.parser_order)),
            bell_volume=float(data.get("bell_volume", cls.bell_volume)),
        )


class PresetRepository(ABC):
    @abstractmethod
    def list(self) -> dict[str, Duration]:
        """Return all presets."""

    @abstractmethod
    def get(self, name: str) -> Duration:
        """Return a preset duration."""

    @abstractmethod
    def add(self, name: str, duration: Duration) -> None:
        """Add or replace a preset."""

    @abstractmethod
    def remove(self, name: str) -> None:
        """Remove a preset."""


class JSONPresetRepository(PresetRepository):
    def __init__(
        self,
        path: Path | None = None,
        parser: ParserRegistry | None = None,
    ) -> None:
        self.path = path or default_data_dir() / "presets.json"
        self.parser = parser or ParserRegistry()

    def list(self) -> dict[str, Duration]:
        return {name: self.parser.parse(text) for name, text in self._load().items()}

    def get(self, name: str) -> Duration:
        presets = self.list()
        if name not in presets:
            raise KeyError(f"Unknown preset: {name}")
        return presets[name]

    def add(self, name: str, duration: Duration) -> None:
        data = self._load()
        data[name] = format(duration, "compact")
        self._save(data)

    def remove(self, name: str) -> None:
        data = self._load()
        if name not in data:
            raise KeyError(f"Unknown preset: {name}")
        del data[name]
        self._save(data)

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            data = {"pomodoro": "25m", "tea": "4m", "standup": "15m"}
            self._save(data)
            return data
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in raw.items()}

    def _save(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class InMemoryPresetRepository(PresetRepository):
    def __init__(self, presets: dict[str, Duration] | None = None) -> None:
        self._presets = dict(presets or {})

    def list(self) -> dict[str, Duration]:
        return dict(self._presets)

    def get(self, name: str) -> Duration:
        return self._presets[name]

    def add(self, name: str, duration: Duration) -> None:
        self._presets[name] = duration

    def remove(self, name: str) -> None:
        del self._presets[name]


@dataclass(frozen=True)
class SessionRecord:
    label: str
    duration: Duration
    status: TimerStatus
    completed_at: datetime


class SessionLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_data_dir() / "sessions.jsonl"

    def append(
        self,
        timer: Timer,
        status: TimerStatus | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        status = status or timer.status
        completed_at = completed_at or datetime.now(UTC)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "label": timer.label,
            "duration_ms": timer.original_duration.total_milliseconds,
            "duration": format(timer.original_duration, "compact"),
            "status": status.value,
            "completed_at": completed_at.isoformat(),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

    def recent(self, count: int = 10) -> list[SessionRecord]:
        return self._read_records()[-count:]

    def stats_by_label(self) -> dict[str, Duration]:
        totals: dict[str, int] = {}
        for record in self._read_records():
            totals[record.label] = totals.get(record.label, 0) + record.duration.total_milliseconds
        return {label: Duration(total) for label, total in sorted(totals.items())}

    def _read_records(self) -> list[SessionRecord]:
        if not self.path.exists():
            return []
        records: list[SessionRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload: dict[str, Any] = json.loads(line)
            records.append(
                SessionRecord(
                    label=str(payload["label"]),
                    duration=Duration(int(payload["duration_ms"])),
                    status=TimerStatus(str(payload["status"])),
                    completed_at=datetime.fromisoformat(str(payload["completed_at"])),
                )
            )
        return records
