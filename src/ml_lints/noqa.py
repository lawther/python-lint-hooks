"""Noqa suppression handling.

A `# noqa: <code>` comment on a relevant source line suppresses the matching rule on
that line. A `# ml-lints: noqa: <code>` comment anywhere in the file suppresses the
matching rule for the whole file — for a rule module whose own `bad_example` must
contain the pattern it detects, no single line is the right place to suppress it.

Both forms require explicit code(s). Bare `# noqa` and bare `# ml-lints: noqa` are
intentionally not honoured: either would suppress every rule (on a line, or in the
whole file respectively), hiding violations the author was not thinking about.

Only real comment tokens are searched. A directive inside a string literal is not a
comment, and honouring it would let a string silently hide a real violation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ml_lints.comments import Comment

_LINE_DIRECTIVE = "# noqa"
_FILE_DIRECTIVE = "# ml-lints: noqa"


def has_noqa(comments: Sequence[Comment], line_numbers: Sequence[int], code: str) -> bool:
    """Return True if a comment on any of the given lines carries a noqa suppressing code."""
    wanted_lines = frozenset(line_numbers)
    return any(comment.line in wanted_lines and _suppresses(comment, _LINE_DIRECTIVE, code) for comment in comments)


def has_file_noqa(comments: Sequence[Comment], code: str) -> bool:
    """Return True if any comment carries a file-level noqa suppressing code."""
    return any(_suppresses(comment, _FILE_DIRECTIVE, code) for comment in comments)


def _suppresses(comment: Comment, directive: str, code: str) -> bool:
    """Return True if comment holds directive with an explicit code list that includes code.

    The whole comment token is searched, so a directive may follow another one in the same
    comment (`# type: ignore  # noqa: ML100`). A bare directive names no code.
    """
    token = f"#{comment.text}"
    if directive not in token:
        return False
    _, _, tail = token.partition(directive)
    tail = tail.strip()
    if not tail.startswith(":"):
        return False
    codes = [c.strip() for c in tail[1:].split(",")]
    return code in codes
