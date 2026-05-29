"""ML501 — Hacky pluralisation in string literal.

Hacky plurals like `version(s)` or `item[es]` are visual clutter and represent a lazy
approach to user-facing copy. Instead of using parenthetical shortcuts, code should
either rephrase sentences to be count-agnostic or use conditional logic to choose the
correct singular or plural form.
"""

from __future__ import annotations

import ast
import re
from typing import ClassVar

from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, register


@register
class ML501(Rule):
    """Detects hacky pluralisation like 'version(s)' or 'item[es]' in string literals.

    This rule enforces clean, professional user-facing copy. Rather than using
    tacky 1980s-style parenthetical plurals, developers should either:
    1. Write conditional logic to select the singular or plural string based on count.
    2. Rephrase the copy to be count-agnostic.

    When refactoring, remember to check and update verb agreements (e.g., 'is'/'are',
    'has'/'have', 'need'/'needs', 'was'/'were') in the surrounding text.
    """

    code: ClassVar[RuleCode] = RuleCode.ML501
    category: ClassVar[RuleCategory] = RuleCategory.LOCALISATION
    summary: ClassVar[str] = "Hacky pluralisation in string literal"
    suggestion: ClassVar[str] = (
        "Avoid hacky parenthetical or bracketed plurals like '(s)'. Use proper pluralisation "
        "or rephrase the sentence. Remember to also check and update verb agreements "
        "(e.g. 'is/are', 'need/needs', 'has/have') in surrounding text."
    )

    # Matches a word followed by (s), (es), [s], or [es] case-insensitively,
    # ensuring it's not followed immediately by another letter.
    PLURAL_RE = re.compile(r"\b[a-zA-Z]+(?:\([sS]\)|\([eE][sS]\)|\[[sS]\]|\[[eE][sS]\])(?![a-zA-Z])")

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._docstring_nodes: set[int] = set()

    def _record_docstring(self, node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Find and record the docstring of a node so we can ignore it."""
        if not node.body:
            return
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            self._docstring_nodes.add(id(first.value))

    def enter_Module(self, node: ast.Module) -> None:
        self._record_docstring(node)

    def enter_ClassDef(self, node: ast.ClassDef) -> None:
        self._record_docstring(node)

    def enter_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._record_docstring(node)

    enter_AsyncFunctionDef = enter_FunctionDef

    def enter_Constant(self, node: ast.Constant) -> None:
        """Check all string literals for hacky plurals, skipping docstrings."""
        if not isinstance(node.value, str):
            return
        if id(node) in self._docstring_nodes:
            return

        lineno = getattr(node, "lineno", None)
        col_offset = getattr(node, "col_offset", None)
        if lineno is None or col_offset is None:
            return

        # Determine quote/prefix offset if we are on the same line as the start of the literal
        try:
            line_text = self._context.source_lines[lineno - 1]
            token_prefix = line_text[col_offset:]
            match_quotes = re.match(r'^[rfub]*("{3}|\'{3}|"|\')', token_prefix, re.IGNORECASE)
            offset = len(match_quotes.group(0)) if match_quotes else 0
        except IndexError:
            offset = 0

        text = node.value
        for match in self.PLURAL_RE.finditer(text):
            word = match.group()
            prefix = text[: match.start()]
            line_offset = prefix.count("\n")

            violation_line = lineno + line_offset
            if line_offset == 0:
                current_col = col_offset + offset + match.start()
            else:
                last_newline = prefix.rfind("\n")
                current_col = match.start() - last_newline - 1

            self.report(
                violation_line,
                current_col + 1,
                f"Found hacky pluralisation '{word}' in string literal",
            )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    bad_example: ClassVar[str] = """
def prune_versions(count: int) -> None:
    print(f"Pruning {count} old secret version(s)...")
"""

    good_examples: ClassVar[list[str]] = [
        """
def prune_versions(count: int) -> None:
    if count == 1:
        print("Pruning 1 old secret version...")
    else:
        print(f"Pruning {count} old secret versions...")
""",
    ]
