"""Test the persistence"""

from datetime import UTC, datetime

import pytest

from pytimer.duration import Duration
from pytimer.engine import TimerEngine
from pytimer.persistence import JSONPresetRepository, SessionLog
from pytimer.time_source import FakeTimeSource
from pytimer.timer import TimerStatus


def test_json_preset_repository_creates_defaults_and_updates(tmp_path) -> None:
    repository = JSONPresetRepository(tmp_path / "presets.json")

    assert repository.get("tea") == Duration.from_seconds(4 * 60)

    repository.add("nap", Duration.from_seconds(20 * 60))
    assert repository.get("nap") == Duration.from_seconds(20 * 60)

    repository.remove("nap")
    with pytest.raises(KeyError):
        repository.get("nap")


def test_session_log_recent_and_stats(tmp_path) -> None:
    source = FakeTimeSource()
    engine = TimerEngine(time_source=source)
    timer = engine.add_timer(Duration.from_seconds(5), label="tea")
    log = SessionLog(tmp_path / "sessions.jsonl")

    log.append(
        timer,
        status=TimerStatus.COMPLETED,
        completed_at=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
    )

    recent = log.recent(1)
    assert recent[0].label == "tea"
    assert recent[0].duration == Duration.from_seconds(5)
    assert log.stats_by_label()["tea"] == Duration.from_seconds(5)
