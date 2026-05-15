from __future__ import annotations

import ast
from typing import ClassVar

from python_lint_hooks.analyzers.forbidden_types import ForbiddenTypeAnalyzer
from python_lint_hooks.rules import CheckContext, Rule, RuleCategory, RuleCode, annotation_noqa_lines, register

_SERIALISATION_METHOD_NAMES: frozenset[str] = frozenset({"to_dict", "as_dict"})


@register
class ML102(Rule):
    """Function returns a dictionary of primitive types.

    Returning a dictionary like `dict[str, str]` is semantically "thin". It gives
    the caller no information about what the keys represent (e.g., is it a Username?
    An ID?) or what the values are. This encourages "primitive obsession", where
    domain logic is scattered instead of being encapsulated in a proper type.
    """

    code: ClassVar[RuleCode] = RuleCode.ML102
    category: ClassVar[RuleCategory] = RuleCategory.RETURN_TYPES
    summary: ClassVar[str] = "Function returns a `dict` of primitives"
    suggestion: ClassVar[str] = "Use a dataclass or `NewType` for keys/values"

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        self._function_depth: int = 0

    def enter_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._function_depth == 0 and node.returns is not None and node.name not in _SERIALISATION_METHOD_NAMES:
            self._check_return(node.name, node.returns)
        self._function_depth += 1

    def leave_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function_depth -= 1

    enter_AsyncFunctionDef = enter_FunctionDef  # type: ignore[assignment]
    leave_AsyncFunctionDef = leave_FunctionDef  # type: ignore[assignment]

    def _check_return(self, func_name: str, returns: ast.expr) -> None:
        analyzer = ForbiddenTypeAnalyzer()
        analyzer.analyze(returns)
        for finding in analyzer.findings:
            if finding.code != self.code:
                continue
            self.report(
                finding.line,
                finding.col,
                f"Function '{func_name}' returns dict of primitives; use NewType for keys/values or use a dataclass",
                noqa_lines=annotation_noqa_lines(returns),
            )

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    exemptions: ClassVar[str] = (
        "Methods named `to_dict` or `as_dict` are exempt. These are serialisation methods"
        " whose purpose is to produce a plain dict for an external consumer (an API, a logging"
        " framework, etc.). The semantic richness lives in the enclosing class, so flagging"
        " them is a false positive."
    )

    bad_example: ClassVar[str] = """
def get_user_scores() -> dict[str, int]:
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
UserId = NewType('UserId', str)
Score = NewType('Score', int)
def get_user_scores() -> dict[UserId, Score]:
    ...
""",
        """
@dataclass(frozen=True)
class UserScore:
    user_id: str
    score: int

def get_user_scores() -> list[UserScore]:
    ...
""",
    ]
