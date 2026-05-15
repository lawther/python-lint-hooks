"""Tests for ML500 (Australian English)."""

from __future__ import annotations

import pathlib
import textwrap
from pathlib import Path

import pytest

from python_lint_hooks.rules.ml500_australian_english import ML500
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


def test_ml500_ignored_imported_name_in_annotation(tmp_path: Path) -> None:
    # Imported names used in annotations must not be flagged — the developer has no control
    # over the spelling of a third-party class name. The correct flag site is the definition;
    # fixing it there cascades to all usages via normal refactoring.
    code = textwrap.dedent("""\
        from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
        from typing import Annotated

        _bearer = HTTPBearer()

        def authenticated_uid(
            credentials: Annotated[HTTPAuthorizationCredentials, ...],
        ) -> str:
            return credentials.credentials
    """)
    violations = check(code, tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_ml500_ignored_inline_attribute_reference(tmp_path: Path) -> None:
    # Both sides of a dotted name in free text are exempt — the entire token is an external
    # API reference the developer cannot rename. This covers obj.color (color after the dot)
    # and colors.get (color before the dot) and api.get_color (color inside the method name).
    # Sentence boundaries are not affected: "colors. Next sentence" is still flagged.
    code = textwrap.dedent("""\
        \"\"\"Official reference for colors.get, obj.color, and api.get_color.
        \"\"\"
    """)
    violations = check(code, tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_ml500_sentence_boundary_still_flagged(tmp_path: Path) -> None:
    # A period followed by a space (sentence boundary) does not exempt the preceding word.
    code = "# I like colors. Get the value.\n"
    violations = check(code, tmp_path)
    assert "ML500" in codes(violations)


def test_ml500_ignored_in_url(tmp_path: Path) -> None:
    # URLs are outside the developer's control and must never be flagged, even when they
    # contain American-spelled path segments (e.g. /colors/get in the Google Calendar API).
    code = textwrap.dedent("""\
        \"\"\"See https://developers.google.com/calendar/api/v3/reference/colors/get for details.
        \"\"\"
    """)
    violations = check(code, tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_ml500_noqa_on_closing_docstring_line_suppresses_whole_docstring(tmp_path: Path) -> None:
    # A noqa on the closing """ line suppresses all ML500 violations within the docstring.
    # This is the right place because per-line noqa inside docstring text is impractical
    # (no # character, line-length concerns). Canonical use case: HTTP header names like
    # 'Authorization' which are locked in by RFC and cannot be changed.
    code = textwrap.dedent("""\
        def fn():
            \"\"\"Extracts the Authorization header.

            This mirrors the color of the sky.
            \"\"\"  # noqa: ML500
            pass
    """)
    violations = check(code, tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_ml500_noqa_on_closing_line_does_not_suppress_outside_docstring(tmp_path: Path) -> None:
    # The noqa on the closing """ only covers that docstring — violations elsewhere are still caught.
    code = textwrap.dedent("""\
        my_color = 1

        def fn():
            \"\"\"Authorization header.
            \"\"\"  # noqa: ML500
            pass
    """)
    violations = check(code, tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert len(ml500_violations) == 1
    assert "color" in ml500_violations[0].message


def test_ml500_missing_spelling_map_disables_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulates a partial installation where spelling_map.json was not bundled
    # (e.g., stripped by a Docker layer or incorrectly vendored). The rule must
    # fall back to an empty map — no violations and no crash — rather than
    # raising FileNotFoundError.
    original_exists = pathlib.Path.exists
    monkeypatch.setattr(ML500, "_SPELLING_MAP", None)
    monkeypatch.setattr(
        pathlib.Path,
        "exists",
        lambda self: False if self.name == "spelling_map.json" else original_exists(self),
    )

    violations = check("my_color = 'red'\n", tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []


def test_ml500_imported_alias_also_exempt(tmp_path: Path) -> None:
    # An aliased import is tracked under its local alias, so usage of the alias is exempt.
    code = textwrap.dedent("""\
        from some_lib import ColorManager as CM
        x = CM()
    """)
    violations = check(code, tmp_path)
    ml500_violations = [v for v in violations if v.code == "ML500"]
    assert ml500_violations == []
