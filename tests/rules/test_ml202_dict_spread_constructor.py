"""Tests for ML202 — constructor called by spreading .__dict__ or vars()."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes

# ---------------------------------------------------------------------------
# Positive tests — the rule SHOULD fire
# ---------------------------------------------------------------------------


def test_dunder_dict_spread_flagged(tmp_path: Path) -> None:
    # Cls(**obj.__dict__) is the direct spelling of the anti-pattern.
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Point:
                x: int
                y: int
            p = Point(1, 2)
            q = Point(**p.__dict__)
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML202"]


def test_vars_spread_flagged(tmp_path: Path) -> None:
    # Cls(**vars(obj)) is equally broken — same rule applies.
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Point:
                x: int
                y: int
            p = Point(1, 2)
            q = Point(**vars(p))
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML202"]


def test_dict_literal_with_dunder_dict_spread_flagged(tmp_path: Path) -> None:
    # Cls(**{**obj.__dict__, "x": 10}) — the motivating example from the real codebase.
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Point:
                x: int
                y: int
            p = Point(1, 2)
            q = Point(**{**p.__dict__, "x": 10})
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML202"]


def test_dict_literal_with_vars_spread_flagged(tmp_path: Path) -> None:
    # Cls(**{**vars(obj), "x": 10}) — same pattern via vars().
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Point:
                x: int
                y: int
            p = Point(1, 2)
            q = Point(**{**vars(p), "x": 10})
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML202"]


def test_instance_spread_after_plain_variable_spread_flagged(tmp_path: Path) -> None:
    # Cls(**d, **obj.__dict__) — a plain dict variable spread precedes the instance spread.
    # The outer keyword loop hits a value that is neither an instance spread nor a dict
    # literal (the elif on line 65 is False), then must continue to the next keyword.
    # A premature break or return after the elif would silently miss this violation.
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Point:
                x: int
                y: int
            p = Point(1, 2)
            d = {"z": 3}
            q = Point(**d, **p.__dict__)
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML202"]


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_dataclasses_replace_ok(tmp_path: Path) -> None:
    # The idiomatic fix must not be flagged.
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Point:
                x: int
                y: int
            p = Point(1, 2)
            q = dataclasses.replace(p, x=10)
        """),
        tmp_path,
    )
    assert codes(violations) == []


def test_plain_dict_spread_ok(tmp_path: Path) -> None:
    # **{**some_dict, "key": val} where the spread is a plain dict, not .__dict__ or vars(), is fine.
    violations = check(
        textwrap.dedent("""\
            def f(x: int, y: int) -> None:
                pass
            d = {"x": 1, "y": 2}
            f(**{**d, "x": 10})
        """),
        tmp_path,
    )
    assert codes(violations) == []


def test_vars_no_args_ok(tmp_path: Path) -> None:
    # vars() with no arguments returns the local namespace, not an instance — not the anti-pattern.
    violations = check(
        textwrap.dedent("""\
            x = 1
            y = vars()
        """),
        tmp_path,
    )
    assert codes(violations) == []


def test_dunder_dict_attribute_read_ok(tmp_path: Path) -> None:
    # Merely reading obj.__dict__ (not spreading it into a call) is fine.
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Point:
                x: int
            p = Point(1)
            d = p.__dict__
        """),
        tmp_path,
    )
    assert codes(violations) == []


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_noqa_ml202_suppresses(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass(frozen=True)
            class Point:
                x: int
                y: int
            p = Point(1, 2)
            q = Point(**p.__dict__)  # noqa: ML202
        """),
        tmp_path,
    )
    assert "ML202" not in codes(violations)
