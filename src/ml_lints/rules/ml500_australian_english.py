"""ML500 — American English spelling detected.

The project requires Australian English spelling in all code and comments.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from pathlib import Path
from typing import ClassVar, cast

from ml_lints.rules import CheckContext, Rule, RuleCategory, RuleCode, register


@register
class ML500(Rule):
    """Detects American English spelling in code and comments.

    This rule enforces the project mandate to use Australian English (e.g., 'colour'
    instead of 'color', 'initialise' instead of 'initialize').

    To avoid false positives with external APIs, it ignores:
    - Attribute access (e.g., `obj.color`)
    - Keyword arguments in calls (e.g., `func(color="red")`)
    - String literals (e.g., `"color"`) that are not docstrings.
    """

    code: ClassVar[RuleCode] = RuleCode.ML500
    category: ClassVar[RuleCategory] = RuleCategory.LOCALISATION
    summary: ClassVar[str] = "American English spelling detected"
    suggestion: ClassVar[str] = "Use Australian English spelling instead"

    # Lazy-loaded spelling map from JSON
    _SPELLING_MAP: ClassVar[dict[str, str] | None] = None

    # Cross-file cache: (module_path, import_attr, getattr_chain) -> frozenset of method
    # names, or None if the module could not be imported.  Shared across instances to avoid
    # re-importing the same library for every file in a multi-file run.
    _BASE_METHODS_CACHE: ClassVar[dict[tuple[str, str | None, tuple[str, ...]], frozenset[str] | None]] = {}

    # Regex to split identifiers into words (handles camelCase, snake_case, and kebab-case)
    # This splits on transitions from lower to upper, or digits/underscores/hyphens.
    WORDS_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|$)|[0-9]+|_|-")

    def __init__(self, context: CheckContext) -> None:
        super().__init__(context)
        if self._SPELLING_MAP is None:
            map_path = Path(__file__).parent / "spelling_map.json"
            if map_path.exists():
                with map_path.open("r", encoding="utf-8") as f:
                    ML500._SPELLING_MAP = json.load(f)
            else:
                ML500._SPELLING_MAP = {}
        self._imported_names: set[str] = set()
        # Maps each local import alias to (module_path, attribute_name_or_None).
        # Only absolute imports are tracked; relative imports stay in _imported_names only.
        self._import_map: dict[str, tuple[str, str | None]] = {}
        # Stack of resolved base-class method sets, one entry per enclosing ClassDef.
        # frozenset[str]: the union of all base-class methods — skip if method is in set.
        # None: at least one base was external but not importable — skip all method names.
        self._class_method_stack: list[frozenset[str] | None] = []

    @property
    def spelling_map(self) -> dict[str, str]:
        return self._SPELLING_MAP or {}

    def _match_case(self, original: str, replacement: str) -> str:
        """Matches the case of replacement to original.

        - ALL CAPS -> ALL CAPS
        - Title Case -> Title Case
        - lower case -> lower case
        """
        if original.isupper():
            return replacement.upper()
        if original and original[0].isupper():
            return replacement.capitalize()
        return replacement.lower()

    def _check_text(self, text: str, line: int, col: int, extra_noqa_lines: list[int] | None = None) -> None:
        """Check a block of text (like a comment or identifier) for US spellings."""
        url_spans = [(m.start(), m.end()) for m in re.finditer(r"https?://\S+", text)]
        # Any dotted name (e.g. colors.get, api.get_color) is treated as an inline
        # attribute/method reference — both sides of the dot are an external API name
        # the developer cannot rename.
        dotted_spans = [(m.start(), m.end()) for m in re.finditer(r"\b[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+", text)]
        for match in re.finditer(r"\b[a-zA-Z]+\b", text):
            if any(start <= match.start() < end for start, end in url_spans):
                continue
            if any(start <= match.start() < end for start, end in dotted_spans):
                continue
            word = match.group()
            lower_word = word.lower()
            if lower_word in self.spelling_map:
                # Calculate line and column for multi-line support
                prefix = text[: match.start()]
                line_offset = prefix.count("\n")
                if line_offset == 0:
                    current_col = col + match.start()
                else:
                    last_newline = prefix.rfind("\n")
                    current_col = match.start() - last_newline - 1

                violation_line = line + line_offset
                noqa_lines = [violation_line, *(extra_noqa_lines or [])]
                suggestion = self._match_case(word, self.spelling_map[lower_word])
                self.report(
                    violation_line,
                    current_col + 1,
                    f"Use Australian English: '{suggestion}' instead of '{word}'",
                    noqa_lines=noqa_lines,
                )

    def _check_name(self, name: str, line: int, col: int) -> None:
        """Check an identifier for US spellings by splitting it into words."""
        found_any = False

        def _replace(match: re.Match) -> str:
            nonlocal found_any
            part = match.group()
            lower_part = part.lower()
            if lower_part in self.spelling_map:
                found_any = True
                return self._match_case(part, self.spelling_map[lower_part])
            return part

        # Reconstruct the name with all parts replaced
        suggested_name = self.WORDS_RE.sub(_replace, name)

        if found_any:
            self.report(
                line,
                col + 1,
                f"Use Australian English: '{suggested_name}' instead of '{name}'",
            )

    def _check_docstring(self, node: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        """Check if a node has a docstring and validate its spelling."""
        if not node.body:
            return
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            doc_node = first.value
            value = cast("str", doc_node.value)  # narrowed by isinstance above; ast.Constant.value is typed broadly

            # Determine the offset to skip quotes/prefixes (r, f, u, b)
            line_text = self._context.source_lines[doc_node.lineno - 1]
            token_prefix = line_text[doc_node.col_offset :]
            match = re.match(r'^[rfub]*("{3}|\'{3}|"|\')', token_prefix, re.IGNORECASE)
            offset = len(match.group(0)) if match else 0

            closing_line = [doc_node.end_lineno] if doc_node.end_lineno is not None else None
            self._check_text(value, doc_node.lineno, doc_node.col_offset + offset, extra_noqa_lines=closing_line)

    @staticmethod
    def _extract_attr_chain(node: ast.expr) -> list[str]:
        """Walk an AST attribute/name chain and return the dotted parts, root first.

        Returns [] for nodes that are not a simple chain of Name and Attribute nodes
        (e.g. subscripts or calls), signalling that the base cannot be statically resolved.
        """
        parts: list[str] = []
        current: ast.expr = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        else:
            return []
        parts.reverse()
        return parts

    def _resolve_base_methods(self, base: ast.expr) -> frozenset[str] | None:
        """Return the method set of a base class expression, or None if unresolvable.

        frozenset[str] — the names exposed by dir() on that class.
        None — the base is from an external import but the module cannot be loaded;
               callers should conservatively skip all method-name checks.
        Empty frozenset — the base is local (not from an import); proceed normally.
        """
        parts = self._extract_attr_chain(base)
        if not parts:
            return frozenset()

        root = parts[0]
        if root not in self._import_map:
            return frozenset()

        module_path, import_attr = self._import_map[root]
        chain_after_root = parts[1:]

        # For non-aliased imports like `import a.b.c`, the local root name "a" is the
        # first component of module_path.  The remaining module-path components ["b", "c"]
        # are implicit in the imported module object and must NOT be traversed again via
        # getattr — they are already "baked in".
        module_components = module_path.split(".")
        baked_count = len(module_components) - 1 if module_components[0] == root else 0

        # Build the getattr chain from the non-baked tail, prepending any attr from the
        # import map (e.g. `from a import B` -> import_attr="B" must be getattr'd first).
        getattr_chain = list(chain_after_root[baked_count:])
        if import_attr is not None:
            getattr_chain = [import_attr, *getattr_chain]

        cache_key = (module_path, import_attr, tuple(getattr_chain))
        if cache_key in self._BASE_METHODS_CACHE:
            return self._BASE_METHODS_CACHE[cache_key]

        try:
            obj: object = importlib.import_module(module_path)
            for attr in getattr_chain:
                obj = getattr(obj, attr)
            result: frozenset[str] | None = frozenset(dir(obj))
        except Exception:
            result = None

        self._BASE_METHODS_CACHE[cache_key] = result
        return result

    def enter_Module(self, node: ast.Module) -> None:
        """Scan comments in the entire file and check module docstring."""
        self._check_docstring(node)
        for i, line_text in enumerate(self._context.source_lines, 1):
            if "#" in line_text:
                comment_part = line_text.split("#", 1)[1]
                comment_col = line_text.find("#") + 1
                self._check_text(comment_part, i, comment_col)

    def enter_Import(self, node: ast.Import) -> None:
        """Track imported names so they are exempt from spelling checks."""
        for alias in node.names:
            local_name = alias.asname if alias.asname is not None else alias.name.split(".")[0]
            self._imported_names.add(local_name)
            self._import_map[local_name] = (alias.name, None)

    def enter_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track imported names so they are exempt from spelling checks."""
        for alias in node.names:
            local_name = alias.asname if alias.asname is not None else alias.name
            self._imported_names.add(local_name)
            if node.level == 0 and node.module:  # absolute imports only
                self._import_map[local_name] = (node.module, alias.name)

    def enter_Name(self, node: ast.Name) -> None:
        """Check variable names, skipping imported names."""
        if node.id not in self._imported_names:
            self._check_name(node.id, node.lineno, node.col_offset)

    def enter_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Check function names and docstrings, skipping names that override a base-class method."""
        if not self._is_inherited_method(node.name):
            self._check_name(node.name, node.lineno, node.col_offset)
        self._check_docstring(node)

    def _is_inherited_method(self, name: str) -> bool:
        """Return True if name should be skipped because it is an inherited method."""
        if not self._class_method_stack:
            return False
        top = self._class_method_stack[-1]
        return top is None or name in top

    def enter_ClassDef(self, node: ast.ClassDef) -> None:
        """Check class names, docstrings, and push base-class method set onto the stack."""
        self._check_name(node.name, node.lineno, node.col_offset)
        self._check_docstring(node)
        combined: frozenset[str] | None = frozenset()
        for base in node.bases:
            result = self._resolve_base_methods(base)
            if result is None:
                combined = None
                break
            combined = combined | result
        self._class_method_stack.append(combined)

    def leave_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_method_stack.pop()

    def enter_arg(self, node: ast.arg) -> None:
        """Check function argument names."""
        self._check_name(node.arg, node.lineno, node.col_offset)

    # Note: enter_AsyncFunctionDef is aliased below
    enter_AsyncFunctionDef = enter_FunctionDef

    # -------------------------------------------------------------------------
    # Examples
    # -------------------------------------------------------------------------

    exemptions: ClassVar[str] = """\
Method names that match a method already defined on an externally-imported base class are
exempt, because the developer cannot rename them without breaking the override.  The rule
uses Python's import machinery to resolve base-class methods at lint time.  If the base
module is not installed in the current environment, all method names in that subclass are
conservatively exempt to avoid false positives.
"""

    bad_example: ClassVar[str] = """
def initialize_color():
    my_favorite_color = "red"  # string literals are ignored, but variable names aren't
    # This color is nice
    ...
"""

    good_examples: ClassVar[list[str]] = [
        """
def initialise_colour():
    _my_favourite_colour = "red"
    # This colour is nice
    ...
""",
        """
# Override methods from base classes are exempted
import appdaemon.plugins.hass.hassapi as hass

class MyAutomation(hass.Hass):
    def initialize(self) -> None: ...
""",
    ]
