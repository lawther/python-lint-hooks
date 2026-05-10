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


def test_ml500_flagged_in_docstring(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        def resolve():
            \"\"\"Normalize this.\"\"\"
            pass
    """)
    violations = check(code, tmp_path)
    assert "ML500" in codes(violations)


def test_ml500_multiline_docstring(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        \"\"\"
        This module has a color.
        And another color here.
        \"\"\"
        def foo():
            \"\"\"
            Function with color.
            \"\"\"
            pass
    """)
    violations = check(code, tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert len(ml500_violations) == 3
    lines = sorted([v.line for v in ml500_violations])
    assert lines == [2, 3, 7]


def test_ml500_multiple_per_line(tmp_path: Path) -> None:
    code = "# color color color\ndef color_color(): pass"
    violations = check(code, tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    # 3 in comment, 1 in function name (aggregated) = 4
    assert len(ml500_violations) == 4
    # Check the aggregated function name violation
    fn_violation = next(v for v in ml500_violations if "color_color" in v.message)
    assert "Use Australian English: 'colour_colour' instead of 'color_color'" in fn_violation.message


def test_noqa_ml500_suppresses(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        my_color = 'red'  # noqa: ML500
    """)
    violations = check(code, tmp_path)
    assert "ML500" not in codes(violations)


def test_ml500_preserves_case(tmp_path: Path) -> None:
    # Title Case
    code = "# Neighborhood window\n"
    violations = check(code, tmp_path)
    assert "Use Australian English: 'Neighbourhood' instead of 'Neighborhood'" in violations[0].message

    # ALL CAPS
    code = "# USE COLOR HERE\n"
    violations = check(code, tmp_path)
    assert "Use Australian English: 'COLOUR' instead of 'COLOR'" in violations[0].message

    # camelCase part - should be aggregated
    code = "def initializeColor(): pass\n"
    violations = check(code, tmp_path)
    messages = [v.message for v in violations if v.code == "ML500"]
    assert len(messages) == 1
    assert "Use Australian English: 'initialiseColour' instead of 'initializeColor'" in messages[0]


def test_ml500_snake_case_aggregated(tmp_path: Path) -> None:
    code = "fix_my_initialized_thing = 1\n"
    violations = check(code, tmp_path)
    assert (
        "Use Australian English: 'fix_my_initialised_thing' instead of 'fix_my_initialized_thing'"
        in violations[0].message
    )


def test_ml500_kebab_case_in_comment(tmp_path: Path) -> None:
    # kebab-case in comments should still report individual words (via _check_text)
    code = "# my-color-is-red\n"
    violations = check(code, tmp_path)
    assert "Use Australian English: 'colour' instead of 'color'" in violations[0].message
