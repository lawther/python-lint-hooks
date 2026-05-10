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


def test_class_wrapping_mapping_of_primitives_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from typing import Mapping
        class Wrapper:
            data: Mapping[str, str]
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


def test_classvar_does_not_mask_forbidden_instance_fields(tmp_path: Path) -> None:
    # ClassVar[int] produces no forbidden-type findings, so the ML201 loop exits
    # early at "at least one field is fine". A class whose only *instance* fields
    # are forbidden types may silently pass — adversarial check for that false negative.
    code = textwrap.dedent("""\
        from typing import ClassVar
        class Wrapper:
            _counter: ClassVar[int] = 0
            data: dict[str, str]
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML201"]


def test_typing_qualified_classvar_filtered_flagged(tmp_path: Path) -> None:
    # typing.ClassVar[int] (attribute form) must be recognised by _is_classvar and
    # excluded from the annotation list, leaving only the forbidden instance field.
    code = textwrap.dedent("""\
        import typing
        class Wrapper:
            _counter: typing.ClassVar[int] = 0
            data: dict[str, str]
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML201"]


def test_union_annotation_with_forbidden_type_flagged(tmp_path: Path) -> None:
    # dict[str, str] | None is a BinOp annotation — _is_classvar() falls through to
    # return False (it is not a ClassVar), and the forbidden dict inside the union
    # is still detected, so ML201 fires.
    code = textwrap.dedent("""\
        class Wrapper:
            data: dict[str, str] | None
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML201"]


def test_noqa_ml201_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        class Wrapper:  # noqa: ML201
            data: dict[str, str]
    """)
    violations = check(code, tmp_path)
    assert violations == []
