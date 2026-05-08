"""Shared test helpers for all rule tests."""

from __future__ import annotations

from pathlib import Path

from python_lint_hooks.runner import check_file
from python_lint_hooks.violation import RuleCode, Violation


def check(code: str, tmp_path: Path) -> list[Violation]:
    """Write code to a temp file and run the checker against it."""
    path = tmp_path / "sample.py"
    path.write_text(code, encoding="utf-8")
    return check_file(path)


def codes(violations: list[Violation]) -> list[RuleCode]:
    """Extract rule codes from a list of violations."""
    return [v.code for v in violations]
