"""Noqa suppression handling.

A `# noqa: <code>` comment on a relevant source line suppresses the matching rule.
Bare `# noqa` (without a code) is intentionally not honoured: it would suppress every
rule on a line, hiding violations the author was not thinking about. Suppressions must
name the code(s) being silenced.
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
