"""Noqa suppression handling.

A `# noqa: <code>` comment on a relevant source line suppresses the matching rule on
that line. A `# ml-lints: noqa: <code>` comment anywhere in the file suppresses the
matching rule for the whole file — for a rule module whose own `bad_example` must
contain the pattern it detects, no single line is the right place to suppress it.

Both forms require explicit code(s). Bare `# noqa` and bare `# ml-lints: noqa` are
intentionally not honoured: either would suppress every rule (on a line, or in the
whole file respectively), hiding violations the author was not thinking about.
"""

from __future__ import annotations


def has_noqa(source_lines: list[str], line_numbers: list[int], code: str) -> bool:
    """Return True if any of the given source lines carries a noqa suppressing code."""
    for lineno in line_numbers:
        if lineno < 1 or lineno > len(source_lines):
            continue
        line = source_lines[lineno - 1]
        if "# noqa" not in line:
            continue
        _, _, noqa_tail = line.partition("# noqa")
        noqa_tail = noqa_tail.strip()
        if not noqa_tail or not noqa_tail.startswith(":"):
            return False  # bare `noqa` is not honoured
        codes = [c.strip() for c in noqa_tail[1:].split(",")]
        if code in codes:
            return True
    return False


def has_file_noqa(source_lines: list[str], code: str) -> bool:
    """Return True if any source line carries a file-level noqa suppressing code."""
    for line in source_lines:
        if "# ml-lints: noqa" not in line:
            continue
        _, _, noqa_tail = line.partition("# ml-lints: noqa")
        noqa_tail = noqa_tail.strip()
        if not noqa_tail or not noqa_tail.startswith(":"):
            continue  # bare file-level noqa is not honoured
        codes = [c.strip() for c in noqa_tail[1:].split(",")]
        if code in codes:
            return True
    return False
