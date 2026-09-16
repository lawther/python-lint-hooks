"""Tests for the token-aware comment scanner."""

from __future__ import annotations

import textwrap

from ml_lints.comments import scan_comments


def test_scan_comments_finds_own_line_and_trailing_comments() -> None:
    source = textwrap.dedent("""\
        # leading
        x = 1  # trailing
    """)
    assert [(c.line, c.col, c.text) for c in scan_comments(source)] == [
        (1, 1, " leading"),
        (2, 8, " trailing"),
    ]


def test_scan_comments_ignores_hash_inside_a_string_literal() -> None:
    # The whole point of the module: only the tokeniser knows which "#" starts a comment.
    source = 'x = "# not a comment"\ny = """\n# also not a comment\n"""\n'
    assert scan_comments(source) == ()


def test_scan_comments_finds_a_comment_on_a_line_whose_string_contains_a_hash() -> None:
    # Splitting the line on its first "#" would have produced '### x ###"  # real' as the
    # comment text, at the column of the string's first "#".
    source = 'x = "### x ###"  # real\n'
    assert [(c.line, c.col, c.text) for c in scan_comments(source)] == [(1, 18, " real")]


def test_scan_comments_reports_col_as_the_offset_its_text_is_measured_from() -> None:
    # col points at the first character *after* the "#", so col + text.index(word) lands on
    # the word. Rules add 1 to convert to a 1-based report column.
    source = "#   spaced\n"
    (comment,) = scan_comments(source)
    assert source[comment.col : comment.col + len(comment.text)] == comment.text


def test_scan_comments_keeps_what_it_found_when_tokenising_fails() -> None:
    # tokenize.TokenError is not a SyntaxError, so source that ast.parse accepts could still
    # fail here. The comments found before the failure survive; the run does not abort.
    source = '# kept\nx = """unterminated\n'
    assert [c.text for c in scan_comments(source)] == [" kept"]
