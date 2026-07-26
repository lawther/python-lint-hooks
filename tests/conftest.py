"""Shared test helpers for all rule tests."""

from __future__ import annotations

from pathlib import Path

from ml_lints.runner import check_paths
from ml_lints.violation import RuleCode, Violation


def check(code: str, tmp_path: Path) -> list[Violation]:
    """Write code to a temp file and run the project-wide checker against it.

    Runs through `check_paths` so rules that consume the cross-file NewType index
    (ML108, ML109) still operate correctly on single-file snippets.
    """
    path = tmp_path / "sample.py"
    path.write_text(code, encoding="utf-8")
    return check_paths([path])


def check_project(files: dict[str, str], tmp_path: Path) -> list[Violation]:
    """Write a multi-file project under tmp_path and run the full project-wide checker.

    Keys in `files` are relative paths (e.g. "pkg/models.py"); values are file contents.
    The project-wide NewType index is built from every file before the per-file pass.
    """
    written: list[Path] = []
    for rel, source in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        written.append(path)
    return check_paths(written)


def codes(violations: list[Violation]) -> list[RuleCode]:
    """Extract rule codes from a list of violations."""
    return [v.code for v in violations]
