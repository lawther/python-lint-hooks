"""Tests for ML101 — function returns a bare (unparameterised) tuple."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import check, codes

if TYPE_CHECKING:
    from pathlib import Path


def test_bare_tuple_no_subscript_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple: ...\n", tmp_path)
    assert codes(violations) == ["ML101"]


def test_capital_tuple_bare_flagged(tmp_path: Path) -> None:
    violations = check("from typing import Tuple\ndef foo() -> Tuple: ...\n", tmp_path)
    assert codes(violations) == ["ML101"]


def test_str_return_ok(tmp_path: Path) -> None:
    violations = check("def foo() -> str: ...\n", tmp_path)
    assert violations == []


def test_typing_attr_tuple_bare_flagged(tmp_path: Path) -> None:
    # typing.Tuple (attribute access, no subscript) should be caught by _check_attribute,
    # the same as an imported bare Tuple name.
    violations = check("import typing\ndef foo() -> typing.Tuple: ...\n", tmp_path)
    assert codes(violations) == ["ML101"]


def test_tuple_literal_annotation_flagged(tmp_path: Path) -> None:
    # (int, str) as a return annotation is an ast.Tuple node in the AST, not a Subscript.
    # The analyser flags it as ML101 (bare tuple) since it is not the modern tuple[int, str] form.
    violations = check("def foo() -> (int, str): ...\n", tmp_path)
    assert codes(violations) == ["ML101"]


def test_noqa_ml101_suppresses(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple: ...  # noqa: ML101\n", tmp_path)
    assert violations == []
