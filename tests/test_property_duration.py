# ruff: noqa: E402,I001
"""Test the duration round-trip property with a property-based test"""

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st  # noqa: E402

from pytimer.duration import Duration  # noqa: E402
from pytimer.parsers import ParserRegistry  # noqa: E402


@given(st.integers(min_value=0, max_value=24 * 60 * 60 * 1000))
def test_compact_format_round_trips(total_milliseconds: int) -> None:
    duration = Duration(total_milliseconds)

    assert ParserRegistry().parse(format(duration, "compact")) == duration
