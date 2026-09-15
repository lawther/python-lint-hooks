"""Tests for ML001 — a file that parses fine but is not clean UTF-8.

See CONTRIBUTING_RULES.md's "File-level rules" section: ML001 sets uses_prelude=False
because its trigger only counts on the file's first two physical lines, so its
bad_example/good_examples in ml001_utf8_clean.py are tested standalone. These tests add
the cases that need real on-disk bytes (a BOM, an actually non-ASCII latin-1 payload).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ml_lints.runner import check_paths
from ml_lints.violation import RuleCode
from tests.conftest import codes

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Positive tests — the rule SHOULD fire
# ---------------------------------------------------------------------------


def test_ml001_flagged_for_declared_latin1_encoding(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_bytes('# -*- coding: latin-1 -*-\nx = "caf\xe9"\n'.encode("latin-1"))

    violations = check_paths([path])

    assert codes(violations) == [RuleCode.ML001]


def test_ml001_flagged_for_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_bytes(b"\xef\xbb\xbfx = 1\n")

    violations = check_paths([path])

    assert codes(violations) == [RuleCode.ML001]


def test_ml001_reports_the_coding_declaration_line(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_bytes('#!/usr/bin/env python3\n# -*- coding: latin-1 -*-\nx = "caf\xe9"\n'.encode("latin-1"))

    violations = check_paths([path])

    assert len(violations) == 1
    assert violations[0].line == 2


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_ml001_ok_for_clean_utf8(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("x = 1\n", encoding="utf-8")

    violations = check_paths([path])

    assert violations == []


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_ml001_suppressible_via_enabled_codes(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_bytes(b"\xef\xbb\xbfx = 1\n")

    violations = check_paths([path], frozenset({RuleCode.ML100}))

    assert violations == []
