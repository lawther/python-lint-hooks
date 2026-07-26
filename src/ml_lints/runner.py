"""Single-walk AST runner that dispatches to all enabled rules."""

from __future__ import annotations

import ast
from pathlib import Path

from ml_lints.analyzers.newtype_index import NewTypeIndex
from ml_lints.rules import CheckContext, Rule, all_rules
from ml_lints.violation import RuleCode, Violation


def check_file(
    path: Path,
    enabled_codes: frozenset[RuleCode] | None = None,
    project_index: NewTypeIndex | None = None,
) -> list[Violation]:
    """Parse path and return violations from all enabled rules.

    When enabled_codes is None every registered rule runs. The CLI computes the enabled
    set from --select / --ignore and passes it in so disabled rules are never instantiated.

    project_index is an optional pre-built cross-file index. Rules that need cross-module
    type resolution (ML108, ML109) consume it; without one, they stay silent.
    """
    source = path.read_text(encoding="utf-8")
    source_lines = tuple(source.splitlines())
    tree = ast.parse(source, filename=str(path))
    context = CheckContext(path, source_lines, project_index=project_index)

    rules: list[Rule] = []
    for cls in all_rules():
        if enabled_codes is None or cls.code in enabled_codes:
            rules.append(cls(context))

    if rules:
        _walk(tree, rules)

    return [v for rule in rules for v in rule.violations]


def check_paths(
    paths: list[Path],
    enabled_codes: frozenset[RuleCode] | dict[Path, frozenset[RuleCode]] | None = None,
) -> list[Violation]:
    """Check multiple files with a shared project-wide NewType index.

    Performs a pre-pass to build a cross-file index of NewType definitions, class
    field annotations, and function return annotations. Then runs the per-file
    rule pass with that index available in CheckContext.

    Files that fail to parse during the pre-pass are silently skipped from the
    index; check_file will surface the parse error when the per-file pass tries
    to re-parse them.
    """
    index = NewTypeIndex()
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        index.ingest(str(path.resolve()), tree)
    index.finalise()

    violations: list[Violation] = []
    for path in paths:
        if isinstance(enabled_codes, dict):
            codes = enabled_codes.get(path)
        elif isinstance(enabled_codes, frozenset):
            codes = enabled_codes
        else:
            codes = None
        violations.extend(check_file(path, codes, project_index=index))
    return violations


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
