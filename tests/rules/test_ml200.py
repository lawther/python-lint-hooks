"""Tests for ML200 — dataclass is not frozen."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes


def test_dataclass_not_frozen(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML200"]


def test_dataclass_frozen_explicit_ok(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == []


def test_dataclass_frozen_false_flagged(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass(frozen=False)
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML200"]


def test_dataclass_attr_style_flagged(tmp_path: Path) -> None:
    # @dataclasses.dataclass (attribute access style) is also caught.
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML200"]


def test_noqa_ml200_suppresses(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass  # noqa: ML200
            class Mutable:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == []
