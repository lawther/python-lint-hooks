"""Tests for ML101 — function returns a bare (unparameterised) tuple."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import check, codes


def test_bare_tuple_no_subscript_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple: ...\n", tmp_path)
    assert codes(violations) == ["ML101"]


def test_capital_tuple_bare_flagged(tmp_path: Path) -> None:
    violations = check("from typing import Tuple\ndef foo() -> Tuple: ...\n", tmp_path)
    assert codes(violations) == ["ML101"]


def test_str_return_ok(tmp_path: Path) -> None:
    violations = check("def foo() -> str: ...\n", tmp_path)
    assert violations == []


def test_noqa_ml101_suppresses(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple: ...  # noqa: ML101\n", tmp_path)
    assert violations == []
