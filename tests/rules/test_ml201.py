"""Tests for ML201 — class contains only forbidden types."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes


def test_dataclass_wrapping_only_forbidden_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from dataclasses import dataclass
        @dataclass(frozen=True)
        class MatchCacheBuildResult:
            counts: dict[int, int]
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML201"]
    assert "Class 'MatchCacheBuildResult' only contains forbidden types" in violations[0].message


def test_class_wrapping_only_forbidden_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        class Wrapper:
            data: dict[str, str]
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML201"]


def test_class_with_multiple_forbidden_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        class MultiWrapper:
            data: dict[str, str]
            meta: tuple[int, int]
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML201"]


def test_class_with_mixed_types_ok(tmp_path: Path) -> None:
    # One valid field means the class is not an all-forbidden wrapper.
    code = textwrap.dedent("""\
        class Valid:
            data: dict[str, str]
            id: int
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_noqa_ml201_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        class Wrapper:  # noqa: ML201
            data: dict[str, str]
    """)
    violations = check(code, tmp_path)
    assert violations == []
