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


def test_dict_wrong_arity_flagged(tmp_path: Path) -> None:
    # dict[str] supplies only one type argument instead of the required two.
    # The analyser treats malformed parameterisation as equivalent to a bare dict (ML100).
    violations = check("def foo() -> dict[str]: ...\n", tmp_path)
    assert codes(violations) == ["ML100"]


def test_typing_attr_dict_bare_flagged(tmp_path: Path) -> None:
    # typing.Dict (attribute access, no subscript) should be caught by _check_attribute,
    # the same as an imported bare Dict name.
    violations = check("import typing\ndef foo() -> typing.Dict: ...\n", tmp_path)
    assert codes(violations) == ["ML100"]


def test_exotic_subscript_head_ok(tmp_path: Path) -> None:
    # (list, dict)[str] is a subscript whose head is an ast.Tuple — neither ast.Name
    # nor ast.Attribute. _check_subscript falls through with an empty head_name and
    # produces no findings; this exercises the otherwise-untouched 71->74 branch.
    violations = check("def foo() -> (list, dict)[str]: ...\n", tmp_path)
    assert violations == []


def test_noqa_ml100_suppresses(tmp_path: Path) -> None:
    violations = check("def foo() -> dict: ...  # noqa: ML100\n", tmp_path)
    assert violations == []
