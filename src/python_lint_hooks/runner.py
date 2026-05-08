"""Single-walk AST runner that dispatches to all enabled rules."""

from __future__ import annotations

import ast
from pathlib import Path

from python_lint_hooks.rules import CheckContext, Rule, all_rules
from python_lint_hooks.violation import Violation


def check_file(path: Path, enabled_codes: frozenset[str] | None = None) -> list[Violation]:
    """Parse path and return violations from all enabled rules.

    When enabled_codes is None every registered rule runs. The CLI computes the enabled
    set from --select / --ignore and passes it in so disabled rules are never instantiated.
    """
    source = path.read_text(encoding="utf-8")
    source_lines = tuple(source.splitlines())
    tree = ast.parse(source, filename=str(path))
    context = CheckContext(path, source_lines)

    rules: list[Rule] = []
    for cls in all_rules():
        if enabled_codes is None or cls.code in enabled_codes:
            rules.append(cls(context))

    if rules:
        _walk(tree, rules)

    return [v for rule in rules for v in rule.violations]


def _walk(node: ast.AST, rules: list[Rule]) -> None:
    """Recursively walk the AST, dispatching enter/leave hooks to every rule."""
    node_type = type(node).__name__
    enter_attr = f"enter_{node_type}"
    leave_attr = f"leave_{node_type}"

    for rule in rules:
        method = getattr(rule, enter_attr, None)
        if method is not None:
            method(node)

    for child in ast.iter_child_nodes(node):
        _walk(child, rules)

    for rule in rules:
        method = getattr(rule, leave_attr, None)
        if method is not None:
            method(node)
