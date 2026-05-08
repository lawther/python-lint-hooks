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


def test_nonstring_name_falls_back_to_unknown(tmp_path: Path) -> None:
    # When the first argument is not a string literal (here an integer), the rule
    # cannot extract a name and falls back to "unknown". The forbidden-type finding
    # should still be reported — this exercises the 48->51 False branch.
    code = textwrap.dedent("""\
        from typing import NewType
        HeaderDict = NewType(42, dict[str, str])
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML105"]
    assert "'unknown'" in violations[0].message


def test_aliased_typing_module_flagged(tmp_path: Path) -> None:
    # import typing as t; t.NewType(...) — _is_newtype_call checks
    # func.value.id == "typing" literally, so an aliased import may be a false negative.
    code = textwrap.dedent("""\
        import typing as t
        HeaderDict = t.NewType("HeaderDict", dict[str, str])
    """)
    violations = check(code, tmp_path)
    assert codes(violations) == ["ML105"]


def test_noqa_ml105_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from typing import NewType
        HeaderDict = NewType("HeaderDict", dict[str, str])  # noqa: ML105
    """)
    violations = check(code, tmp_path)
    assert violations == []
