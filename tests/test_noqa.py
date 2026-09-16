"""Tests for noqa suppression handling: per-line and file-level."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from ml_lints.comments import scan_comments
from ml_lints.noqa import has_file_noqa, has_noqa
from tests.conftest import check, codes

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from ml_lints.comments import Comment


def _comments(*lines: str) -> Sequence[Comment]:
    # The noqa functions consume real comment tokens, so build them the same way the
    # runner does rather than hand-constructing Comment tuples.
    return scan_comments("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Per-line noqa
# ---------------------------------------------------------------------------


def test_has_noqa_matches_code_on_line() -> None:
    assert has_noqa(_comments("x = {}  # noqa: ML100"), [1], "ML100")


def test_has_noqa_does_not_match_other_code() -> None:
    assert not has_noqa(_comments("x = {}  # noqa: ML200"), [1], "ML100")


def test_has_noqa_bare_is_not_honoured() -> None:
    assert not has_noqa(_comments("x = {}  # noqa"), [1], "ML100")


def test_has_noqa_out_of_range_line_ignored() -> None:
    assert not has_noqa(_comments("x = {}  # noqa: ML100"), [5], "ML100")


def test_has_noqa_ignores_lines_outside_the_span() -> None:
    assert not has_noqa(_comments("x = {}  # noqa: ML100", "y = {}"), [2], "ML100")


def test_has_noqa_ignores_directive_inside_string_literal() -> None:
    # The directive is string content, not a comment. Honouring it would let any string
    # that happens to mention noqa silently hide a real violation on its line.
    assert not has_noqa(_comments('x = "# noqa: ML100"'), [1], "ML100")


def test_has_noqa_finds_real_comment_after_string_mentioning_noqa() -> None:
    # A raw-line search would partition on the first '# noqa' (inside the string) and
    # parse the wrong tail. Only the comment token counts.
    assert has_noqa(_comments('x = "# noqa: ML200"  # noqa: ML100'), [1], "ML100")


def test_has_noqa_honours_directive_after_another_in_same_comment() -> None:
    # `# type: ignore  # noqa: ...` is a single comment token; the noqa must still count.
    assert has_noqa(_comments("x = {}  # type: ignore  # noqa: ML100"), [1], "ML100")


def test_has_noqa_requires_space_after_hash() -> None:
    # `#noqa:` has never been honoured; token-awareness does not change that.
    assert not has_noqa(_comments("x = {}  #noqa: ML100"), [1], "ML100")


def test_has_noqa_bare_directive_does_not_block_later_line_in_span() -> None:
    # A multi-line annotation passes its whole span. A bare noqa on one line of it names
    # no code, so it must not stop a valid directive on another line from being seen.
    comments = _comments("def f() -> dict[  # noqa", "    str, str]:  # noqa: ML102", "    ...")
    assert has_noqa(comments, [1, 2], "ML102")


# ---------------------------------------------------------------------------
# File-level noqa
# ---------------------------------------------------------------------------


def test_has_file_noqa_matches_code_anywhere_in_file() -> None:
    assert has_file_noqa(_comments("x = 1", "# ml-lints: noqa: ML501"), "ML501")


def test_has_file_noqa_does_not_match_other_code() -> None:
    assert not has_file_noqa(_comments("# ml-lints: noqa: ML500"), "ML501")


def test_has_file_noqa_matches_one_of_several_codes() -> None:
    assert has_file_noqa(_comments("# ml-lints: noqa: ML500, ML501"), "ML501")


def test_has_file_noqa_bare_is_not_honoured() -> None:
    assert not has_file_noqa(_comments("# ml-lints: noqa"), "ML501")


def test_has_file_noqa_bare_does_not_block_later_directive() -> None:
    assert has_file_noqa(_comments("# ml-lints: noqa", "# ml-lints: noqa: ML501"), "ML501")


def test_has_file_noqa_absent_returns_false() -> None:
    assert not has_file_noqa(_comments("x = 1"), "ML501")


def test_has_file_noqa_ignores_directive_inside_string_literal() -> None:
    # The dangerous case: a rule module whose bad_example documents file-level noqa would
    # otherwise switch that rule off for the entire module.
    assert not has_file_noqa(_comments('EXAMPLE = """', "# ml-lints: noqa: ML501", '"""'), "ML501")


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


# ---------------------------------------------------------------------------
# End-to-end: directives inside string literals suppress nothing
# ---------------------------------------------------------------------------


def test_line_noqa_inside_string_does_not_suppress(tmp_path: Path) -> None:
    # The triple-quoted string opens on the violating line and runs to its end, so a
    # raw-line search sees exactly `# noqa: ML100` there — a well-formed directive that is
    # nonetheless string content.
    code = 'def make() -> dict: return {"k": """# noqa: ML100\n"""}\n'
    violations = check(code, tmp_path)
    assert "ML100" in codes(violations)


def test_file_noqa_inside_string_does_not_suppress(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        EXAMPLE = \"\"\"
        # ml-lints: noqa: ML100
        \"\"\"

        def make() -> dict:
            return {}
    """)
    violations = check(code, tmp_path)
    assert "ML100" in codes(violations)
