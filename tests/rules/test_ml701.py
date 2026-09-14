"""Tests for ML701 — a timezone is silently substituted instead of a bad one being rejected.

The positive fixture is a real defect, reduced: an `isinstance` check that correctly
discovers the value is not a real IANA zone, and an `else` branch that then discards that
discovery and carries on with an invented one.
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


def test_ml701_flags_isinstance_else_zone(tmp_path: Path) -> None:
    # The canonical shape. The isinstance has already proven the value is a fixed offset;
    # the else branch throws that proof away.
    code = textwrap.dedent("""\
        import zoneinfo


        def week_bounds(today: str) -> str:
            tz = today.tzinfo if isinstance(today.tzinfo, zoneinfo.ZoneInfo) else zoneinfo.ZoneInfo("UTC")
            return tz
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_or_utc(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import UTC


        def resolve(user_tz: str) -> str:
            return user_tz or UTC
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_truthiness_else_timezone_utc(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import timezone


        def resolve(tz: str) -> str:
            return tz if tz else timezone.utc
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_a_fixed_offset_fallback(tmp_path: Path) -> None:
    # A constructed fixed offset is the same defect, and a more obviously wrong one.
    code = textwrap.dedent("""\
        from datetime import timedelta, timezone


        def resolve(tz: str) -> str:
            return tz or timezone(timedelta(hours=10))
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_a_bare_zoneinfo_import(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from zoneinfo import ZoneInfo


        def resolve(tz: str) -> str:
            return tz or ZoneInfo("Australia/Sydney")
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_ml701_ignores_ordinary_string_defaulting(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def label_for(name: str) -> str:
            return name or "unknown"
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_ordinary_numeric_defaulting(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def port_for(configured: int) -> int:
            return configured if configured else 8080
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_an_isinstance_check_that_does_not_substitute(tmp_path: Path) -> None:
    # Raising is the fix this rule is steering towards, so it must obviously stay silent.
    code = textwrap.dedent("""\
        import zoneinfo


        def zone_of(instant: str) -> str:
            tz = instant.tzinfo
            if not isinstance(tz, zoneinfo.ZoneInfo):
                msg = "expected a real IANA zone"
                raise TypeError(msg)
            return tz
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_a_default_argument(tmp_path: Path) -> None:
    # The zone is chosen at the signature, where a reader can see it — not swapped in
    # after a check has already failed.
    code = textwrap.dedent("""\
        from zoneinfo import ZoneInfo


        def resolve(tz: ZoneInfo = ZoneInfo("UTC")) -> ZoneInfo:
            return tz
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_an_and_chain(tmp_path: Path) -> None:
    # Only `or` substitutes. An `and` chain guards rather than replaces.
    code = textwrap.dedent("""\
        from datetime import UTC


        def resolve(enabled: bool) -> bool:
            return enabled and UTC
    """)
    violations = check(code, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_noqa_ml701_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import UTC


        def resolve(user_tz: str) -> str:
            return user_tz or UTC  # noqa: ML701
    """)
    violations = check(code, tmp_path)
    assert "ML701" not in codes(violations)
