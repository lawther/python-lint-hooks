"""Tests for ML106 — function returns a bare (unparameterised) Mapping."""

from pathlib import Path

from tests.conftest import check


def test_bare_mapping_flagged(tmp_path: Path) -> None:
    violations = check("from typing import Mapping\ndef foo() -> Mapping: ...\n", tmp_path)
    assert len(violations) == 1
    assert violations[0].code == "ML106"
    assert "returns bare Mapping" in violations[0].message


def test_bare_mutable_mapping_flagged(tmp_path: Path) -> None:
    violations = check("from typing import MutableMapping\ndef foo() -> MutableMapping: ...\n", tmp_path)
    assert len(violations) == 1
    assert violations[0].code == "ML106"
    assert "returns bare Mapping" in violations[0].message


def test_collections_abc_mapping_flagged(tmp_path: Path) -> None:
    violations = check("import collections.abc\ndef foo() -> collections.abc.Mapping: ...\n", tmp_path)
    assert len(violations) == 1
    assert violations[0].code == "ML106"


def test_mapping_wrong_arity_flagged(tmp_path: Path) -> None:
    violations = check("from typing import Mapping\ndef foo() -> Mapping[str]: ...\n", tmp_path)
    assert len(violations) == 1
    assert violations[0].code == "ML106"


def test_noqa_ml106_suppresses(tmp_path: Path) -> None:
    violations = check("from typing import Mapping\ndef foo() -> Mapping: ...  # noqa: ML106\n", tmp_path)
    assert len(violations) == 0
