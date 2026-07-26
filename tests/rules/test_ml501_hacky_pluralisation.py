"""Tests for ML501 — Hacky pluralisation in string literal."""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

from ml_lints.rules import CheckContext
from ml_lints.rules.ml501_hacky_pluralisation import ML501
from tests.conftest import check, codes

# ---------------------------------------------------------------------------
# Positive tests — the rule SHOULD fire
# ---------------------------------------------------------------------------


def test_ml501_flagged_parentheses(tmp_path: Path) -> None:
    violations = check("msg = 'Pruning 1 old secret version(s) to save costs...'\n", tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert len(ml501_violations) == 1
    assert ml501_violations[0].line == 1
    assert "Found hacky pluralisation 'version(s)'" in ml501_violations[0].message


def test_ml501_flagged_square_brackets(tmp_path: Path) -> None:
    violations = check("msg = 'Only 1 backup version[s] available'\n", tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert len(ml501_violations) == 1
    assert "Found hacky pluralisation 'version[s]'" in ml501_violations[0].message


def test_ml501_flagged_es(tmp_path: Path) -> None:
    violations = check("msg = 'Updated 2 process(es)'\n", tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert len(ml501_violations) == 1
    assert "Found hacky pluralisation 'process(es)'" in ml501_violations[0].message


def test_ml501_flagged_case_insensitive(tmp_path: Path) -> None:
    violations = check("msg = 'Found file(S)'\n", tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert len(ml501_violations) == 1
    assert "Found hacky pluralisation 'file(S)'" in ml501_violations[0].message


def test_ml501_flagged_in_fstring(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        count = 1
        msg = f"Pruned {count} version(s) successfully"
    """)
    violations = check(code, tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert len(ml501_violations) == 1
    assert ml501_violations[0].line == 2
    assert "Found hacky pluralisation 'version(s)'" in ml501_violations[0].message


def test_ml501_multiline_string_offsets(tmp_path: Path) -> None:
    code = textwrap.dedent('''\
        msg = """
        Line 1
        Line 2 has version(s)
        Line 3
        """
    ''')
    violations = check(code, tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert len(ml501_violations) == 1
    assert ml501_violations[0].line == 3


def test_ml501_source_lines_index_error() -> None:
    """Ensure that we handle IndexError if the node's lineno is out of range for source_lines."""
    context = CheckContext(Path("sample.py"), source_lines=("a", "b"))
    rule = ML501(context)
    node = ast.Constant(value="version(s)")
    node.lineno = 10
    node.col_offset = 0
    rule.enter_Constant(node)
    assert len(rule.violations) == 1
    assert rule.violations[0].line == 10
    assert rule.violations[0].col == 1


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_ml501_ignored_in_comments(tmp_path: Path) -> None:
    violations = check("# This ensures we handle version(s)\n", tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert ml501_violations == []


def test_ml501_ignored_in_docstrings(tmp_path: Path) -> None:
    code = textwrap.dedent('''\
        def fn():
            """Normalize this version(s) function.
            
            It manages key(s) and secrets.
            """
            pass
    ''')
    violations = check(code, tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert ml501_violations == []


def test_ml501_no_false_positives(tmp_path: Path) -> None:
    # Not attached to a word
    violations = check("x = 'a = (s)'\n", tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert ml501_violations == []


def test_ml501_no_false_positives_lookahead(tmp_path: Path) -> None:
    # Next letter prevents matching
    violations = check("x = 'version(s)omething'\n", tmp_path)
    ml501_violations = [v for v in violations if v.code == "ML501"]
    assert ml501_violations == []


def test_ml501_no_lineno_or_col_offset() -> None:
    """Ensure that we safely return if lineno or col_offset is missing on a string constant."""
    context = CheckContext(Path("sample.py"), source_lines=())
    rule = ML501(context)
    node = ast.Constant(value="version(s)")
    if hasattr(node, "lineno"):
        del node.lineno
    if hasattr(node, "col_offset"):
        del node.col_offset
    rule.enter_Constant(node)
    assert not rule.violations


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_noqa_ml501_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        msg = 'Pruning 1 old secret version(s)...'  # noqa: ML501
    """)
    violations = check(code, tmp_path)
    assert "ML501" not in codes(violations)
