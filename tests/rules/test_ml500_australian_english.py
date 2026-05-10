"""Tests for ML500 (Australian English)."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes


def test_ml500_flagged_in_variable(tmp_path: Path) -> None:
    violations = check("my_color = 'red'\n", tmp_path)
    assert "ML500" in codes(violations)


def test_ml500_flagged_in_function_name(tmp_path: Path) -> None:
    violations = check("def initialize_app(): pass\n", tmp_path)
    assert "ML500" in codes(violations)


def test_ml500_flagged_in_class_name(tmp_path: Path) -> None:
    violations = check("class ColorManager: pass\n", tmp_path)
    assert "ML500" in codes(violations)


def test_ml500_flagged_in_argument(tmp_path: Path) -> None:
    violations = check("def fn(color): pass\n", tmp_path)
    assert "ML500" in codes(violations)


def test_ml500_flagged_in_comment(tmp_path: Path) -> None:
    violations = check("# This is a color\n", tmp_path)
    assert "ML500" in codes(violations)


def test_ml500_ok_australian(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def initialise_colour(favourite_colour):
            # This colour is nice
            my_favourite_colour = favourite_colour
    """)
    violations = check(code, tmp_path)
    # Filter to only ML500 to avoid noise from other rules
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_ml500_ignored_in_string_literal(tmp_path: Path) -> None:
    # Strings are ignored to avoid false positives with external APIs/JSON
    violations = check("x = 'my favorite color'\n", tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_ml500_ignored_in_attribute_access(tmp_path: Path) -> None:
    # Attribute access is ignored for external APIs
    violations = check("obj.color = 'red'\n", tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_ml500_ignored_in_keyword_argument(tmp_path: Path) -> None:
    # Keyword arguments are ignored for external APIs
    violations = check("api_call(color='red')\n", tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_noqa_ml500_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        my_color = 'red'  # noqa: ML500
    """)
    violations = check(code, tmp_path)
    assert "ML500" not in codes(violations)
