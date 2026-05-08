"""Tests for ML105 — NewType wraps a forbidden type."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes


def test_newtype_wrapping_bare_dict_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from typing import NewType
        HeaderDict = NewType("HeaderDict", dict[str, str])
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML105"]
    assert "NewType 'HeaderDict' wraps a forbidden type" in violations[0].message


def test_newtype_wrapping_bare_tuple_flagged(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from typing import NewType
        Coords = NewType("Coords", tuple[int, int])
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML105"]


def test_newtype_wrapping_ok_type_allowed(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from typing import NewType
        UserId = NewType("UserId", int)
    """)
    violations = check(code, tmp_path)
    assert violations == []


def test_noqa_ml105_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from typing import NewType
        HeaderDict = NewType("HeaderDict", dict[str, str])  # noqa: ML105
    """)
    violations = check(code, tmp_path)
    assert violations == []
