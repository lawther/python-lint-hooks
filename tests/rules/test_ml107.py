"""Tests for ML107 — function returns a Mapping of primitive types."""

from pathlib import Path

from tests.conftest import check


def test_mapping_of_primitives_flagged(tmp_path: Path) -> None:
    violations = check("from typing import Mapping\ndef foo() -> Mapping[str, str]: ...\n", tmp_path)
    assert len(violations) == 1
    assert violations[0].code == "ML107"
    assert "returns Mapping of primitives" in violations[0].message


def test_mutable_mapping_of_primitives_flagged(tmp_path: Path) -> None:
    violations = check("from typing import MutableMapping\ndef foo() -> MutableMapping[int, bool]: ...\n", tmp_path)
    assert len(violations) == 1
    assert violations[0].code == "ML107"


def test_nested_mapping_flagged(tmp_path: Path) -> None:
    violations = check(
        "from typing import Mapping, Optional\ndef foo() -> Optional[Mapping[str, str]]: ...\n", tmp_path
    )
    assert len(violations) == 1
    assert violations[0].code == "ML107"


def test_newtype_mapping_ok(tmp_path: Path) -> None:
    code = """
from typing import Mapping, NewType
UserId = NewType('UserId', str)
Address = NewType('Address', str)
def foo() -> Mapping[UserId, Address]: ...
"""
    violations = check(code, tmp_path)
    assert len(violations) == 0


def test_noqa_ml107_suppresses(tmp_path: Path) -> None:
    violations = check("from typing import Mapping\ndef foo() -> Mapping[str, str]: ...  # noqa: ML107\n", tmp_path)
    assert len(violations) == 0
