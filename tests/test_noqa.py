"""Tests for noqa suppression handling: per-line and file-level."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from ml_lints.noqa import has_file_noqa, has_noqa
from tests.conftest import check, codes

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Per-line noqa
# ---------------------------------------------------------------------------


def test_has_noqa_matches_code_on_line() -> None:
    assert has_noqa(["x = {}  # noqa: ML100"], [1], "ML100")


def test_has_noqa_does_not_match_other_code() -> None:
    assert not has_noqa(["x = {}  # noqa: ML200"], [1], "ML100")


def test_has_noqa_bare_is_not_honoured() -> None:
    assert not has_noqa(["x = {}  # noqa"], [1], "ML100")


def test_has_noqa_out_of_range_line_ignored() -> None:
    assert not has_noqa(["x = {}"], [5], "ML100")


# ---------------------------------------------------------------------------
# File-level noqa
# ---------------------------------------------------------------------------


def test_has_file_noqa_matches_code_anywhere_in_file() -> None:
    source_lines = ["# ml-lints: noqa: ML501", "x = 1"]
    assert has_file_noqa(source_lines, "ML501")


def test_has_file_noqa_does_not_match_other_code() -> None:
    source_lines = ["# ml-lints: noqa: ML500"]
    assert not has_file_noqa(source_lines, "ML501")


def test_has_file_noqa_matches_one_of_several_codes() -> None:
    source_lines = ["# ml-lints: noqa: ML500, ML501"]
    assert has_file_noqa(source_lines, "ML501")


def test_has_file_noqa_bare_is_not_honoured() -> None:
    source_lines = ["# ml-lints: noqa"]
    assert not has_file_noqa(source_lines, "ML501")


def test_has_file_noqa_absent_returns_false() -> None:
    assert not has_file_noqa(["x = 1"], "ML501")


# ---------------------------------------------------------------------------
# End-to-end: a file-level directive suppresses a real rule anywhere in the file
# ---------------------------------------------------------------------------


def test_file_noqa_suppresses_violation_anywhere_in_file(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        # ml-lints: noqa: ML100

        def make() -> dict:
            return {}
    """)
    violations = check(code, tmp_path)
    assert "ML100" not in codes(violations)


def test_file_noqa_only_suppresses_named_code(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        # ml-lints: noqa: ML200

        def make() -> dict:
            return {}
    """)
    violations = check(code, tmp_path)
    assert "ML100" in codes(violations)
