"""Tests for ML700 — a timezone parameter or attribute is not typed as a real IANA zone.

The fixtures are drawn from real code. The positive case is the shape that shipped a bug:
a `tz: object` parameter feeding `datetime.combine(..., tzinfo=tz)` behind a
`type: ignore[arg-type]`. The negative cases are the near-misses that sit next to it in
the same codebase and must stay silent, because a rule that fires on correct code is more
expensive here than one that misses cases.
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


def test_ml700_flags_tz_annotated_object(tmp_path: Path) -> None:
    # The real defect: `object` admits a fixed-offset tzinfo, and the type: ignore below
    # it is the tell that the annotation was widened to make an error go away.
    code = textwrap.dedent("""\
        import datetime


        def hm_to_datetime(d: datetime.date, hour: int, tz: object) -> datetime.datetime:
            return datetime.datetime.combine(d, datetime.time(0, 0), tzinfo=tz)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700"]


def test_ml700_flags_tz_annotated_any(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from typing import Any


        def floor_day(instant: str, tz: Any) -> str:
            return instant
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700"]


def test_ml700_flags_unannotated_zone_parameter(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def floor_day(instant: str, user_tz) -> str:
            return instant
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700"]


def test_ml700_flags_bare_tzinfo_under_a_non_matching_name(tmp_path: Path) -> None:
    # The name-independent trigger. `whatever` is not a zone-ish name, but a bare
    # `tzinfo` annotation is a widening mistake regardless of what it is called.
    code = textwrap.dedent("""\
        from datetime import tzinfo


        def floor_day(instant: str, whatever: tzinfo) -> str:
            return instant
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700"]


def test_ml700_flags_dotted_datetime_tzinfo(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import datetime


        def floor_day(instant: str, tz: datetime.tzinfo) -> str:
            return instant
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700"]


def test_ml700_flags_zone_suffixed_names(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def solve(owner_timezone: object, calendar_zone: object) -> None:
            return None
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700", "ML700"]


def test_ml700_flags_widened_class_attribute(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import dataclasses


        @dataclasses.dataclass(frozen=True)
        class SyncContext:
            user_tz: object
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700"]


def test_ml700_flags_keyword_only_and_positional_only_parameters(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def solve(tz: object, /, *, user_tz: object) -> None:
            return None
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700", "ML700"]


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_ml700_allows_zoneinfo(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import zoneinfo


        def floor_day(instant: str, tz: zoneinfo.ZoneInfo) -> str:
            return instant
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml700_allows_a_union_containing_zoneinfo(tmp_path: Path) -> None:
    # An Optional zone is a separate argument to have; it is not this defect, because
    # the None branch is visible to the reader and to the type checker.
    code = textwrap.dedent("""\
        from zoneinfo import ZoneInfo


        def floor_day(instant: str, user_tz: ZoneInfo | None = None) -> str:
            return instant
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml700_allows_str_iana_keys(tmp_path: Path) -> None:
    # A string cannot do datetime arithmetic, so it cannot cause this defect. Boundary
    # code legitimately carries zones as keys on the way in and out.
    code = textwrap.dedent("""\
        import pydantic


        class CalendarOut(pydantic.BaseModel):
            timezone: str


        def region_for(timezone: str) -> str:
            return timezone
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml700_allows_an_unresolvable_alias(tmp_path: Path) -> None:
    # The AST cannot see through `_BatchUserTz`. Silence is the honest answer — firing
    # here would punish exactly the wrap-it-in-a-real-type habit the project asks for.
    code = textwrap.dedent("""\
        def solve(user_tz: _BatchUserTz) -> None:
            return None
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml700_ignores_self_and_cls(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        class Clock:
            def now(self) -> str:
                return ""

            @classmethod
            def build(cls) -> str:
                return ""
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml700_ignores_object_under_a_non_timezone_name(tmp_path: Path) -> None:
    # Only bare `tzinfo` is name-independent. `object` on an unrelated parameter is
    # somebody else's rule.
    code = textwrap.dedent("""\
        def handle(payload: object) -> None:
            return None
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml700_ignores_module_level_annotations(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        tz: object = None
    """)
    violations = check(code, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_noqa_ml700_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def floor_day(instant: str, tz: object) -> str:  # noqa: ML700
            return instant
    """)
    violations = check(code, tmp_path)
    assert "ML700" not in codes(violations)


# ---------------------------------------------------------------------------
# datetime-subclass exemption — frozen-clock test fakes
# ---------------------------------------------------------------------------


def test_ml700_exempts_a_datetime_subclass(tmp_path: Path) -> None:
    # `datetime.now` takes `tzinfo | None` in the stdlib. An override cannot narrow to
    # ZoneInfo without failing the type checker, so the whole class is exempt. This is
    # the frozen-clock fake pattern, and it accounted for every false positive in the
    # codebase this rule was built against.
    code = textwrap.dedent("""\
        from datetime import datetime, tzinfo


        class FrozenNow(datetime):
            @classmethod
            def now(cls, tz: tzinfo | None = None) -> datetime:
                return cls(2026, 9, 14, tzinfo=tz)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml700_exempts_a_datetime_subclass_declared_inside_a_function(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import datetime, tzinfo


        def frozen_at(instant: datetime) -> type[datetime]:
            class Frozen(datetime):
                @classmethod
                def now(cls, tz: tzinfo | None = None) -> datetime:
                    return instant

            return Frozen
    """)
    violations = check(code, tmp_path)
    assert "ML700" not in codes(violations)


def test_ml700_exempts_a_dotted_datetime_base(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import datetime


        class FrozenNow(datetime.datetime):
            @classmethod
            def now(cls, tz: object = None) -> datetime.datetime:
                return cls(2026, 9, 14)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml700_still_fires_in_a_class_that_does_not_subclass_datetime(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        class Clock:
            def floor_day(self, tz: object) -> str:
                return ""
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML700"]
