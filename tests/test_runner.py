"""Integration tests that span multiple rules.

These live here rather than in tests/rules/ because they verify cross-rule behaviour
rather than a single rule.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from tests.conftest import check, codes

if TYPE_CHECKING:
    from pathlib import Path


def test_dict_and_tuple_violations_separate_codes(tmp_path: Path) -> None:
    # Primitive dict gets ML102, fixed tuple gets ML103.
    violations = check(
        textwrap.dedent("""\
            def foo() -> dict[str, str]: ...
            def bar() -> tuple[int, str]: ...
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML102", "ML103"]


def test_multiple_dict_violations(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            def foo() -> dict[str, str]: ...
            def bar() -> dict[str, int]: ...
        """),
        tmp_path,
    )
    assert len(violations) == 2
    assert all(v.code == "ML102" for v in violations)


def test_dataclass_return_ok(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass

            @dataclass(frozen=True)
            class User:
                id: int
                name: str

            def get_user() -> User: ...
        """),
        tmp_path,
    )
    assert violations == []
