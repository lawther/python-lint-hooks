"""Tests for ML104 — function returns a variable-length tuple."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import check, codes

if TYPE_CHECKING:
    from pathlib import Path


def test_variable_length_tuple_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple[int, ...]: ...\n", tmp_path)
    assert codes(violations) == ["ML104"]


def test_fixed_tuple_is_not_ml104(tmp_path: Path) -> None:
    # Fixed-length tuples are ML103, not ML104.
    violations = check("def foo() -> tuple[int, str]: ...\n", tmp_path)
    assert "ML104" not in codes(violations)
    assert "ML103" in codes(violations)


def test_noqa_ml104_suppresses(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple[int, ...]: ...  # noqa: ML104\n", tmp_path)
    assert violations == []
