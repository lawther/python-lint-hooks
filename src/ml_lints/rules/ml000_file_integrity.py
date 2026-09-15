"""ML000 — a file could not be read or parsed at all.

See CONTRIBUTING_RULES.md for the full rule-writing guide, and the "File-level rules"
section in particular: unlike every other rule, ML000 never runs an AST walk — the
runner synthesises its Violation directly in `check_paths` when reading or parsing a
file fails, since a file that never produced a tree has nothing to walk.
"""

from __future__ import annotations

from typing import ClassVar

from ml_lints.rules import Rule, RuleCategory, RuleCode, register


@register
class ML000(Rule):
    """A source file could not be decoded or parsed, so it was skipped.

    Every other rule needs a parsed AST to run against, so a file that fails to read
    (missing, unreadable, undecodable even after checking for a PEP 263 encoding
    declaration) or fails to parse (a real syntax error) cannot be checked by anything
    else in this project. Reporting that here means the skip is visible in the normal
    output and fails the run, rather than the linter quietly reporting a clean sweep
    over files it never actually opened.
    """

    code: ClassVar[RuleCode] = RuleCode.ML000
    category: ClassVar[RuleCategory] = RuleCategory.FILE_INTEGRITY
    summary: ClassVar[str] = "File could not be read or parsed"
    suggestion: ClassVar[str] = "Fix the file's syntax or encoding, or exclude it from linting"

    bad_example: ClassVar[str] = """
    def broken(
    """

    good_examples: ClassVar[list[str]] = [
        """
        def fine() -> None:
            pass
        """,
    ]
