"""Tests for MLxxx — copy this file to tests/rules/test_mlxxx.py when adding a new rule.

See CONTRIBUTING_RULES.md for the full testing guide.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes

# ---------------------------------------------------------------------------
# Positive tests — the rule SHOULD fire
# ---------------------------------------------------------------------------


def test_mlxxx_flagged(tmp_path: Path) -> None:
    # TODO: replace with a minimal snippet that triggers the rule
    violations = check("...\n", tmp_path)
    assert "MLxxx" in codes(violations)


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_mlxxx_ok(tmp_path: Path) -> None:
    # TODO: replace with a snippet that is valid and should NOT be flagged
    violations = check("pass\n", tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_noqa_mlxxx_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        # TODO: replace with a suppressed snippet
        pass  # noqa: MLxxx
    """)
    violations = check(code, tmp_path)
    assert "MLxxx" not in codes(violations)
