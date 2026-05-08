"""Temporary home for tests of rules not yet ported to the registry.

This file will be deleted once all rules are ported. See tests/rules/ for the
permanent per-rule test files.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from python_lint_hooks.checker import check_file


def _check(code: str, tmp_path: Path) -> list:
    path = tmp_path / "sample.py"
    path.write_text(code, encoding="utf-8")
    return check_file(path)


def _codes(violations: list) -> list[str]:
    return [v.code for v in violations]


# ---------------------------------------------------------------------------
# ML105 — NewType wrapping forbidden types
# ---------------------------------------------------------------------------


def test_newtype_wrapping_bare_dict_flagged(tmp_path: Path) -> None:
    code = """\
        from typing import NewType
        HeaderDict = NewType("HeaderDict", dict[str, str])
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    assert _codes(violations) == ["ML105"]
    assert "NewType 'HeaderDict' wraps a forbidden type" in violations[0].message


def test_newtype_wrapping_bare_tuple_flagged(tmp_path: Path) -> None:
    code = """\
        from typing import NewType
        Coords = NewType("Coords", tuple[int, int])
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    assert _codes(violations) == ["ML105"]


def test_newtype_wrapping_ok_type_allowed(tmp_path: Path) -> None:
    code = """\
        from typing import NewType
        UserId = NewType("UserId", int)
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    assert violations == []


def test_noqa_ml105_suppresses(tmp_path: Path) -> None:
    code = """\
        from typing import NewType
        HeaderDict = NewType("HeaderDict", dict[str, str])  # noqa: ML105
    """
    violations = _check(textwrap.dedent(code), tmp_path)
    assert violations == []
