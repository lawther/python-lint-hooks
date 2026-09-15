"""Tests for ML000 — a file that could not be read or parsed at all.

See CONTRIBUTING_RULES.md's "File-level rules (ML000 is the one exception)" section:
the generic bad_example harness in tests/test_rule_examples.py only exercises the
SyntaxError branch, since its example is written as UTF-8 text. The UnicodeDecodeError
and OSError branches are covered here instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ml_lints.runner import check_paths
from ml_lints.violation import RuleCode
from tests.conftest import check, codes

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Positive tests — the rule SHOULD fire
# ---------------------------------------------------------------------------


def test_ml000_flagged_for_syntax_error(tmp_path: Path) -> None:
    violations = check("def broken(\n", tmp_path)
    assert codes(violations) == [RuleCode.ML000]


def test_ml000_flagged_for_undecodable_bytes(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_bytes(b"\xa4 not valid utf-8 and no coding declaration\n")

    violations = check_paths([path])

    assert codes(violations) == [RuleCode.ML000]


def test_ml000_flagged_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.py"

    violations = check_paths([missing])

    assert codes(violations) == [RuleCode.ML000]


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_ml000_ok_for_valid_file(tmp_path: Path) -> None:
    violations = check("pass\n", tmp_path)
    assert violations == []


def test_ml000_ok_for_declared_non_utf8_encoding(tmp_path: Path) -> None:
    """A PEP 263 coding declaration makes a non-UTF-8 file legitimately valid Python."""
    path = tmp_path / "sample.py"
    path.write_bytes('# -*- coding: latin-1 -*-\nx = "caf\xe9"\n'.encode("latin-1"))

    violations = check_paths([path])

    assert violations == []


# ---------------------------------------------------------------------------
# Reporting behaviour
# ---------------------------------------------------------------------------


def test_ml000_does_not_abort_the_rest_of_the_run(tmp_path: Path) -> None:
    """One unreadable file must not stop other files in the same run from being checked."""
    broken = tmp_path / "broken.py"
    broken.write_bytes(b"\xa4 not valid utf-8\n")
    still_checked = tmp_path / "still_checked.py"
    still_checked.write_text("def get_data() -> dict: ...\n", encoding="utf-8")

    violations = check_paths([broken, still_checked])

    assert sorted(codes(violations)) == sorted([RuleCode.ML000, RuleCode.ML100])


def test_ml000_suppressible_via_enabled_codes(tmp_path: Path) -> None:
    """ML000 is selectable like any other code, unlike an inline noqa (the file doesn't parse)."""
    path = tmp_path / "sample.py"
    path.write_bytes(b"\xa4 not valid utf-8\n")

    violations = check_paths([path], frozenset({RuleCode.ML100}))

    assert violations == []
