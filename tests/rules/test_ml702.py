"""Tests for ML702 — a datetime floored to midnight without a zone conversion.

The negative cases matter more than the positive ones here. `.replace()` is a busy method
and only one of its keyword sets means "local midnight"; the rest are correct, common, and
must stay silent.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from tests.conftest import check, codes

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Positive tests — the rule SHOULD fire
# ---------------------------------------------------------------------------


def test_ml702_flags_an_unconverted_floor(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def local_midnight(instant: str) -> str:
            return instant.replace(hour=0, minute=0, second=0, microsecond=0)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML702"]


def test_ml702_flags_a_floor_on_a_parsed_value(tmp_path: Path) -> None:
    # datetime.fromisoformat carries whatever offset was in the string — a fixed one.
    code = textwrap.dedent("""\
        import datetime


        def local_midnight(raw: str) -> datetime.datetime:
            return datetime.datetime.fromisoformat(raw).replace(hour=0)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML702"]


def test_ml702_flags_a_floor_on_an_unconverted_local(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def local_midnight(instant: str) -> str:
            candidate = instant
            return candidate.replace(hour=0, minute=0)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML702"]


def test_ml702_flags_a_local_reassigned_away_from_the_conversion(tmp_path: Path) -> None:
    # The exemption is about the value, not the name. Rebinding clears it.
    code = textwrap.dedent("""\
        import zoneinfo


        def local_midnight(instant: str, other: str, tz: zoneinfo.ZoneInfo) -> str:
            local = instant.astimezone(tz)
            local = other
            return local.replace(hour=0, minute=0)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML702"]


def test_ml702_flags_a_loop_variable(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def floors(instants: list[str]) -> list[str]:
            return [instant.replace(hour=0) for instant in instants]
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML702"]


# ---------------------------------------------------------------------------
# Negative tests — safe receivers
# ---------------------------------------------------------------------------


def test_ml702_allows_direct_chaining(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import zoneinfo


        def local_midnight(instant: str, tz: zoneinfo.ZoneInfo) -> str:
            return instant.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml702_allows_one_hop_through_a_local(tmp_path: Path) -> None:
    # The house idiom: convert once into a named local, then work from it.
    code = textwrap.dedent("""\
        import zoneinfo


        def local_midnight(instant: str, tz: zoneinfo.ZoneInfo) -> str:
            local = instant.astimezone(tz)
            return local.replace(hour=0, minute=0, second=0, microsecond=0)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml702_allows_a_conversion_visible_from_a_closure(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import zoneinfo


        def build(instant: str, tz: zoneinfo.ZoneInfo) -> str:
            local = instant.astimezone(tz)

            def floor() -> str:
                return local.replace(hour=0, minute=0)

            return floor()
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml702_allows_an_annotated_conversion(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import zoneinfo


        def local_midnight(instant: str, tz: zoneinfo.ZoneInfo) -> str:
            local: str = instant.astimezone(tz)
            return local.replace(hour=0, minute=0)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml702_flags_a_floor_after_converting_to_utc(tmp_path: Path) -> None:
    # `.astimezone(UTC)` is not a conversion for this rule's purposes — it produces a
    # fixed offset, which is precisely the hazardous value. This is the shape a test uses
    # to imitate what psycopg hands back for a timestamptz.
    code = textwrap.dedent("""\
        from datetime import UTC


        def local_midnight(instant: str) -> str:
            as_psycopg_would_hand_it_back = instant.astimezone(UTC)
            return as_psycopg_would_hand_it_back.replace(hour=0, minute=0)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML702"]


def test_ml702_flags_a_floor_after_converting_to_a_constructed_offset(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import timedelta, timezone


        def local_midnight(instant: str) -> str:
            return instant.astimezone(timezone(timedelta(hours=10))).replace(hour=0)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML702"]


# ---------------------------------------------------------------------------
# Negative tests — keyword sets that are not a midnight floor
# ---------------------------------------------------------------------------


def test_ml702_ignores_offset_stripping(tmp_path: Path) -> None:
    # Deliberate, common, and the opposite of this defect: comparing two values with
    # their offsets removed on purpose.
    code = textwrap.dedent("""\
        def strip(wide: str, narrow: str) -> bool:
            return wide.replace(tzinfo=None) == narrow.replace(tzinfo=None)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml702_ignores_hour_flooring(tmp_path: Path) -> None:
    # Flooring to the top of the hour is sub-day and offset-independent.
    code = textwrap.dedent("""\
        def top_of_hour(instant: str) -> str:
            return instant.replace(minute=0, second=0, microsecond=0)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml702_ignores_year_bumping(tmp_path: Path) -> None:
    # A far-future sentinel. Nothing to do with local midnight.
    code = textwrap.dedent("""\
        def next_year(monday: str) -> str:
            return monday.replace(year=monday.year + 1)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml702_ignores_replace_on_other_types(tmp_path: Path) -> None:
    # str.replace takes no keywords, so it cannot collide — but dataclasses.replace and
    # friends are worth pinning as silent too.
    code = textwrap.dedent("""\
        def rename(path: str) -> str:
            return path.replace("a", "b")
    """)
    violations = check(code, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_noqa_ml702_suppresses(tmp_path: Path) -> None:
    # The legitimate use: a test that deliberately builds the wrong floor in order to
    # assert that the zone conversion is load-bearing.
    code = textwrap.dedent("""\
        def proves_the_zone_matters(as_psycopg_would_hand_it_back: str) -> str:
            return as_psycopg_would_hand_it_back.replace(hour=0, minute=0)  # noqa: ML702
    """)
    violations = check(code, tmp_path)
    assert "ML702" not in codes(violations)
