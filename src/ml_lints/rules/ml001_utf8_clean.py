"""ML001 — a file that parses fine but is not clean UTF-8.

See CONTRIBUTING_RULES.md for the full rule-writing guide, and the "File-level rules"
section in particular: this rule sets `uses_prelude = False` because its trigger
(a PEP 263 encoding declaration, or a UTF-8 BOM) only counts on the file's first two
physical lines, which the shared test PRELUDE would otherwise always precede.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from ml_lints.rules import Rule, RuleCategory, RuleCode, register

if TYPE_CHECKING:
    import ast
    from collections.abc import Sequence

# Mirrors the PEP 263 cookie pattern: a coding declaration is only recognised on the
# first or second physical line of the file.
_CODING_DECLARATION_RE = re.compile(r"^[ \t\f]*#.*coding[:=][ \t]*([-\w.]+)")


def _coding_declaration_line(source_lines: Sequence[str]) -> int | None:
    for lineno in (1, 2):
        if lineno > len(source_lines):
            break
        if _CODING_DECLARATION_RE.match(source_lines[lineno - 1]):
            return lineno
    return None


@register
class ML001(Rule):
    """A file was read successfully, but not as clean UTF-8.

    `tokenize.open()` (used by the runner to read every file) honours a PEP 263
    encoding declaration and a UTF-8 byte-order mark, so a file using either still
    parses without error. That leniency is exactly what lets an inconsistent mix of
    encodings creep into a codebase: this project is meant to be UTF-8 throughout, so
    a declared non-UTF-8 encoding, or a BOM, is flagged even though the file itself is
    otherwise perfectly valid Python.
    """

    code: ClassVar[RuleCode] = RuleCode.ML001
    category: ClassVar[RuleCategory] = RuleCategory.FILE_INTEGRITY
    summary: ClassVar[str] = "File is not clean UTF-8 (declared encoding or BOM)"
    suggestion: ClassVar[str] = "Re-save the file as UTF-8 without a BOM and drop the coding declaration"

    uses_prelude: ClassVar[bool] = False

    bad_example: ClassVar[str] = """
    # -*- coding: iso-8859-1 -*-
    def fine() -> None:
        pass
    """

    good_examples: ClassVar[list[str]] = [
        """
        def fine() -> None:
            pass
        """,
    ]

    def enter_Module(self, _node: ast.Module) -> None:
        if self._context.encoding == "utf-8":
            return
        line = _coding_declaration_line(self._context.source_lines) or 1
        self.report(line, 1, f"File is not clean UTF-8 (detected encoding: {self._context.encoding})")
