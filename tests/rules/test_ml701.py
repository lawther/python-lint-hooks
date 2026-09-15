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


# ---------------------------------------------------------------------------
# Fallback hidden behind a name
# ---------------------------------------------------------------------------


def test_ml701_flags_a_fallback_bound_to_a_module_constant(tmp_path: Path) -> None:
    # The indirection is the only difference from the inline ternary, and it is not a
    # difference that matters: the zone is still invented.
    code = textwrap.dedent("""\
        import zoneinfo

        _FALLBACK = zoneinfo.ZoneInfo("UTC")


        def alias_fallback(n: str) -> str:
            return zoneinfo.ZoneInfo(n) if n else _FALLBACK
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_a_constant_defined_after_the_function_that_uses_it(tmp_path: Path) -> None:
    # A module-level name is resolved when the function runs, not when it is defined, so
    # this is legal Python and the rule must not depend on source order.
    code = textwrap.dedent("""\
        import zoneinfo


        def alias_fallback(n: str) -> str:
            return zoneinfo.ZoneInfo(n) if n else _FALLBACK


        _FALLBACK = zoneinfo.ZoneInfo("UTC")
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_a_local_name_bound_to_a_zone(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import timezone


        def resolve(tz: str) -> str:
            fallback = timezone.utc
            return tz or fallback
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_ignores_a_name_bound_to_something_that_is_not_a_zone(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        _FALLBACK = "unknown"


        def label_for(name: str) -> str:
            return name or _FALLBACK
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_an_imported_alias(tmp_path: Path) -> None:
    # The binding is in another module, so the rule cannot see it is a zone. Silence is
    # the honest answer rather than a guess from the spelling of the name.
    code = textwrap.dedent("""\
        from other import _FALLBACK


        def alias_fallback(n: str) -> str:
            return n or _FALLBACK
    """)
    violations = check(code, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Guarded arms — the shape the pattern grows into once it has logging attached
# ---------------------------------------------------------------------------


def test_ml701_flags_an_absence_guard_and_an_except_arm(tmp_path: Path) -> None:
    # Reduced from casey_ai's get_user_timezone. Two substitutions: the early return and
    # the except arm. `zoneinfo.ZoneInfo(n)` is the real zone both of them displace.
    code = textwrap.dedent("""\
        import zoneinfo


        def get_user_timezone(n: str) -> str:
            if n is None:
                return zoneinfo.ZoneInfo("UTC")
            try:
                return zoneinfo.ZoneInfo(n)
            except zoneinfo.ZoneInfoNotFoundError:
                return zoneinfo.ZoneInfo("UTC")
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701", "ML701"]


def test_ml701_flags_a_falsiness_guard(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import zoneinfo


        def resolve(n: str) -> str:
            if not n:
                return zoneinfo.ZoneInfo("UTC")
            return zoneinfo.ZoneInfo(n)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_the_else_arm_of_a_presence_test(tmp_path: Path) -> None:
    # Same guard written the other way round: the fallback is now in the else.
    code = textwrap.dedent("""\
        import zoneinfo


        def resolve(n: str) -> str:
            if n is not None:
                return zoneinfo.ZoneInfo(n)
            else:
                return zoneinfo.ZoneInfo("UTC")
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_ignores_a_function_with_no_real_zone_to_displace(tmp_path: Path) -> None:
    # Nothing was substituted: this function never had a real zone in reach.
    code = textwrap.dedent("""\
        import zoneinfo


        def utc() -> str:
            return zoneinfo.ZoneInfo("UTC")
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_a_guarded_constant_when_nothing_builds_a_real_zone(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import zoneinfo


        def tz_for(cfg: str) -> str:
            if not cfg.zone:
                return zoneinfo.ZoneInfo("UTC")
            return load(cfg)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_an_unguarded_return_of_a_zone(tmp_path: Path) -> None:
    # The zone is chosen unconditionally, not swapped in after a check failed.
    code = textwrap.dedent("""\
        import zoneinfo


        def resolve(n: str) -> str:
            zone = zoneinfo.ZoneInfo(n)
            return zoneinfo.ZoneInfo("UTC")
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_does_not_borrow_a_nested_function_as_the_displaced_zone(tmp_path: Path) -> None:
    # The real zone is built in the inner function; the outer one never had it in reach.
    code = textwrap.dedent("""\
        import zoneinfo


        def outer(n: str) -> str:
            def inner(m: str) -> str:
                return zoneinfo.ZoneInfo(m)

            if n is None:
                return zoneinfo.ZoneInfo("UTC")
            return inner(n)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_noqa_ml701_suppresses_a_guarded_arm(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import zoneinfo


        def resolve(n: str) -> str:
            if n is None:
                return zoneinfo.ZoneInfo("UTC")  # noqa: ML701
            return zoneinfo.ZoneInfo(n)
    """)
    violations = check(code, tmp_path)
    assert "ML701" not in codes(violations)


# ---------------------------------------------------------------------------
# A lookup papered over by its own default argument
# ---------------------------------------------------------------------------


def test_ml701_flags_a_mapping_get_default(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import timezone


        def dict_default(zones: dict, k: str) -> str:
            return zones.get(k, timezone.utc)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_pop_setdefault_getattr_and_next_defaults(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import timezone


        def defaults(zones: dict, k: str, row: str, it: str) -> str:
            zones.pop(k, timezone.utc)
            zones.setdefault(k, timezone.utc)
            getattr(row, "tz", timezone.utc)
            return next(it, timezone.utc)
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"] * 4


def test_ml701_ignores_a_zone_passed_as_an_ordinary_argument(tmp_path: Path) -> None:
    # `tzinfo=` is the zone being used, not a default standing in for a failed lookup.
    code = textwrap.dedent("""\
        from datetime import datetime, time, timezone


        def midnight(d: str) -> str:
            return datetime.combine(d, time.min, tzinfo=timezone.utc)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_a_get_with_no_default(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def lookup(zones: dict, k: str) -> str:
            return zones.get(k)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_noqa_ml701_suppresses_a_lookup_default(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from datetime import timezone


        def dict_default(zones: dict, k: str) -> str:
            return zones.get(k, timezone.utc)  # noqa: ML701
    """)
    violations = check(code, tmp_path)
    assert "ML701" not in codes(violations)


def test_ml701_does_not_leak_a_local_zone_name_into_another_function(tmp_path: Path) -> None:
    # `fallback` is a zone in one() and a plain string in two(). A name is only a zone
    # inside the scope that bound it.
    code = textwrap.dedent("""\
        import zoneinfo


        def one(n: str) -> str:
            fallback = zoneinfo.ZoneInfo("UTC")
            return n or fallback


        def two(label: str, fallback: str) -> str:
            return label or fallback
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


# ---------------------------------------------------------------------------
# Derived zones — a zone built from a value is the caller's, not an invented one
# ---------------------------------------------------------------------------


def test_ml701_ignores_a_fallback_to_a_zone_derived_from_a_value(tmp_path: Path) -> None:
    # Reduced from astral/sun.py. The name is rebound to the zone the *caller* supplied,
    # so falling back to it is the fix this rule recommends, not the defect it describes.
    code = textwrap.dedent("""\
        import zoneinfo


        def dawn(tzinfo: str, date: str) -> str:
            if isinstance(tzinfo, str):
                tzinfo = zoneinfo.ZoneInfo(tzinfo)
            return date.tzinfo or tzinfo
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_ignores_an_inline_zone_built_from_a_value(tmp_path: Path) -> None:
    # The same expression written inline rather than through a name. Reaching for a second
    # source that genuinely holds the zone is threading it in, not guessing.
    code = textwrap.dedent("""\
        import zoneinfo


        def resolve(event: str, user: str) -> str:
            return event.tz or zoneinfo.ZoneInfo(user.tz_name)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_flags_a_zone_built_from_a_module_string_constant(tmp_path: Path) -> None:
    # Indirection does not change the trade: `ZoneInfo(_DEFAULT_ZONE_NAME)` over a
    # module-level literal is the same program as `ZoneInfo("UTC")`.
    code = textwrap.dedent("""\
        import zoneinfo

        _DEFAULT_ZONE_NAME = "UTC"
        _FALLBACK = zoneinfo.ZoneInfo(_DEFAULT_ZONE_NAME)


        def resolve(n: str) -> str:
            return zoneinfo.ZoneInfo(n) if n else _FALLBACK
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_a_fixed_offset_however_its_offset_was_arrived_at(tmp_path: Path) -> None:
    # `timezone(...)` yields a fixed offset whatever it is handed, and a fixed offset is
    # never the zone the caller had — so the derived-zone exemption does not reach it.
    code = textwrap.dedent("""\
        from datetime import timedelta, timezone


        def resolve(tz: str) -> str:
            fallback = timezone(timedelta(hours=11))
            return tz or fallback
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_flags_a_name_bound_to_both_a_derived_and_a_constant_zone(tmp_path: Path) -> None:
    # Reduced from psycopg/_tz.py: `zi` is bound to `ZoneInfo(sname)` and then, in the
    # handler, to `timezone.utc`. The constant binding is the one that makes the return a
    # substitution.
    code = textwrap.dedent("""\
        import zoneinfo
        from datetime import timezone


        def get_tzinfo(sname: str) -> str:
            try:
                zi = zoneinfo.ZoneInfo(sname)
            except KeyError:
                zi = timezone.utc
                return zi
            return zi
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]


def test_ml701_reads_the_zone_identity_through_the_key_keyword(tmp_path: Path) -> None:
    # `ZoneInfo(key=name)` is the same call as `ZoneInfo(name)`, so the derived-zone
    # exemption has to reach it too.
    code = textwrap.dedent("""\
        import zoneinfo


        def resolve(name: str, d: str) -> str:
            fallback = zoneinfo.ZoneInfo(key=name)
            return d.tzinfo or fallback
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_ml701_flags_a_constant_zone_named_by_the_key_keyword(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        import zoneinfo


        def resolve(n: str, d: str) -> str:
            fallback = zoneinfo.ZoneInfo(key="UTC")
            return zoneinfo.ZoneInfo(n) if n else fallback
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML701"]
