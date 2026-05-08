"""Tests for ML100 — function returns a bare (unparameterised) dict."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import check, codes


def test_bare_dict_no_subscript_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> dict: ...\n", tmp_path)
    assert codes(violations) == ["ML100"]


def test_capital_dict_bare_flagged(tmp_path: Path) -> None:
    violations = check("from typing import Dict\ndef foo() -> Dict: ...\n", tmp_path)
    assert codes(violations) == ["ML100"]


def test_str_return_ok(tmp_path: Path) -> None:
    violations = check("def foo() -> str: ...\n", tmp_path)
    assert violations == []


def test_noqa_ml100_suppresses(tmp_path: Path) -> None:
    violations = check("def foo() -> dict: ...  # noqa: ML100\n", tmp_path)
    assert violations == []
