"""Token-aware extraction of a source file's real comments.

A `#` character only starts a comment when Python's tokeniser says so. Scanning source
lines for `#` cannot tell a comment apart from a `#` inside a string literal, so any rule
that reads comments that way reports violations against string contents. This module
exists so no rule has to make that mistake: the runner tokenises each file once and hands
the result to every rule via `CheckContext.comments`.
"""

from __future__ import annotations

import contextlib
import io
import tokenize
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Sequence


class Comment(NamedTuple):
    """One comment token, positioned the way `Rule.report` wants it.

    line is 1-based. col is the 0-based column of the first character after the `#`, which
    is the offset `text` is measured from. text is the comment body with the leading `#`
    stripped and nothing else altered.
    """

    line: int
    col: int
    text: str


def scan_comments(source: str) -> Sequence[Comment]:
    """Return every real comment in source, in file order.

    Tokenising can fail on source that `ast.parse` accepted: `tokenize.TokenError` is not a
    `SyntaxError`, and the two are separate implementations. When that happens the comments
    found before the failure are returned and the rest of the file goes unscanned, rather
    than one odd file aborting the whole run.
    """
    comments: list[Comment] = []
    readline = io.StringIO(source).readline
    with contextlib.suppress(tokenize.TokenError):
        for token in tokenize.generate_tokens(readline):
            if token.type == tokenize.COMMENT:
                line, col = token.start
                comments.append(Comment(line=line, col=col + 1, text=token.string[1:]))
    return tuple(comments)
