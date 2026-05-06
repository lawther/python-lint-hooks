"""Tests for the ML rule checker.

Each test isolates one behaviour of the AST visitor. We test the checker
directly (via check_file) rather than through the CLI to keep tests fast and
focused.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from python_lint_hooks.checker import Violation, check_file


def _check(code: str, tmp_path: Path) -> list[Violation]:
    """Write code to a temp file and run the checker against it."""
    f = tmp_path / "sample.py"
    f.write_text(textwrap.dedent(code))
    return check_file(f)


def _codes(violations: list[Violation]) -> list[str]:
    return [v.code for v in violations]


# ---------------------------------------------------------------------------
# ML001 — bare dict / tuple returns
# ---------------------------------------------------------------------------


def test_bare_dict_subscript_flagged(tmp_path: Path) -> None:
    # The most common case: a typed dict return.
    violations = _check("def foo() -> dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_bare_tuple_subscript_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> tuple[str, int]: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_bare_dict_no_subscript_flagged(tmp_path: Path) -> None:
    # Unparameterised dict is even less informative — still flagged.
    violations = _check("def foo() -> dict: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_bare_tuple_no_subscript_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> tuple: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_capital_dict_flagged(tmp_path: Path) -> None:
    # typing.Dict (pre-3.9 style) must also be caught.
    violations = _check("from typing import Dict\ndef foo() -> Dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_capital_tuple_flagged(tmp_path: Path) -> None:
    violations = _check("from typing import Tuple\ndef foo() -> Tuple[str, int]: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_typing_attribute_dict_flagged(tmp_path: Path) -> None:
    # typing.Dict used as a dotted attribute reference.
    violations = _check("import typing\ndef foo() -> typing.Dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_dict_union_none_flagged(tmp_path: Path) -> None:
    # dict | None — the return type is still logically a dict.
    violations = _check("def foo() -> dict[str, str] | None: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_none_union_dict_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> None | dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_optional_dict_flagged(tmp_path: Path) -> None:
    violations = _check(
        "from typing import Optional\ndef foo() -> Optional[dict[str, str]]: ...\n",
        tmp_path,
    )
    assert _codes(violations) == ["ML001"]


def test_union_dict_none_flagged(tmp_path: Path) -> None:
    violations = _check(
        "from typing import Union\ndef foo() -> Union[dict[str, str], None]: ...\n",
        tmp_path,
    )
    assert _codes(violations) == ["ML001"]


def test_chained_union_with_dict_flagged(tmp_path: Path) -> None:
    # str | int | dict — dict appears in a multi-way union.
    violations = _check("def foo() -> str | int | dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_async_function_flagged(tmp_path: Path) -> None:
    violations = _check("async def foo() -> dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML001"]


# ---------------------------------------------------------------------------
# ML001 — cases that must NOT be flagged
# ---------------------------------------------------------------------------


def test_str_return_ok(tmp_path: Path) -> None:
    violations = _check("def foo() -> str: ...\n", tmp_path)
    assert violations == []


def test_list_return_ok(tmp_path: Path) -> None:
    # list[dict[...]] — the return type is a list, not a dict.
    violations = _check("def foo() -> list[dict[str, str]]: ...\n", tmp_path)
    assert violations == []


def test_named_tuple_return_ok(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            from typing import NamedTuple

            class Result(NamedTuple):
                name: str

            def foo() -> Result: ...
        """),
        tmp_path,
    )
    assert violations == []


def test_no_return_annotation_ok(tmp_path: Path) -> None:
    violations = _check("def foo(): ...\n", tmp_path)
    assert violations == []


def test_none_return_ok(tmp_path: Path) -> None:
    violations = _check("def foo() -> None: ...\n", tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# ML001 — nesting rules
# ---------------------------------------------------------------------------


def test_nested_function_not_flagged(tmp_path: Path) -> None:
    # Inner functions are exempt; outer function has no annotation here.
    violations = _check(
        textwrap.dedent("""\
            def outer() -> None:
                def inner() -> dict[str, str]:
                    return {}
        """),
        tmp_path,
    )
    assert violations == []


def test_outer_function_flagged_inner_exempt(tmp_path: Path) -> None:
    # Outer's bare dict return is flagged; inner's is not (it's nested).
    violations = _check(
        textwrap.dedent("""\
            def outer() -> dict[str, str]:
                def inner() -> dict[str, str]:
                    return {}
                return inner()
        """),
        tmp_path,
    )
    assert len(violations) == 1
    assert violations[0].code == "ML001"
    assert violations[0].line == 1


def test_class_method_flagged(tmp_path: Path) -> None:
    # Methods in top-level classes are not nested in a function — they must be checked.
    violations = _check(
        textwrap.dedent("""\
            class Foo:
                def method(self) -> dict[str, str]: ...
        """),
        tmp_path,
    )
    assert _codes(violations) == ["ML001"]


def test_class_in_class_method_flagged(tmp_path: Path) -> None:
    # Nested classes (class-in-class) are fine; their methods are still checked.
    violations = _check(
        textwrap.dedent("""\
            class Outer:
                class Inner:
                    def method(self) -> dict[str, str]: ...
        """),
        tmp_path,
    )
    assert _codes(violations) == ["ML001"]


# ---------------------------------------------------------------------------
# ML001 — noqa suppression
# ---------------------------------------------------------------------------


def test_noqa_ml001_suppresses(tmp_path: Path) -> None:
    violations = _check("def foo() -> dict[str, str]: ...  # noqa: ML001\n", tmp_path)
    assert violations == []


def test_bare_noqa_suppresses(tmp_path: Path) -> None:
    violations = _check("def foo() -> dict[str, str]: ...  # noqa\n", tmp_path)
    assert violations == []


def test_noqa_other_code_does_not_suppress(tmp_path: Path) -> None:
    # noqa for a different code must not suppress ML001.
    violations = _check("def foo() -> dict[str, str]: ...  # noqa: ML002\n", tmp_path)
    assert _codes(violations) == ["ML001"]


def test_noqa_on_annotation_line_suppresses(tmp_path: Path) -> None:
    # For multi-line signatures the noqa may appear on the annotation line.
    violations = _check(
        textwrap.dedent("""\
            def foo(
                x: str,
            ) -> dict[str, str]:  # noqa: ML001
                ...
        """),
        tmp_path,
    )
    assert violations == []


# ---------------------------------------------------------------------------
# ML002 — class defined inside a function
# ---------------------------------------------------------------------------


def test_class_inside_function_flagged(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            def outer() -> None:
                class Inner:
                    pass
        """),
        tmp_path,
    )
    assert _codes(violations) == ["ML002"]


def test_class_at_module_level_ok(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            class Foo:
                pass
        """),
        tmp_path,
    )
    assert violations == []


def test_class_inside_method_flagged(tmp_path: Path) -> None:
    # A class defined inside a method is still inside a function.
    violations = _check(
        textwrap.dedent("""\
            class Outer:
                def method(self) -> None:
                    class Inner:
                        pass
        """),
        tmp_path,
    )
    assert _codes(violations) == ["ML002"]


def test_noqa_ml002_suppresses(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            def outer() -> None:
                class Inner:  # noqa: ML002
                    pass
        """),
        tmp_path,
    )
    assert violations == []


# ---------------------------------------------------------------------------
# Mixed violations
# ---------------------------------------------------------------------------


def test_multiple_violations_reported(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            def foo() -> dict[str, str]: ...
            def bar() -> tuple[int, str]: ...
        """),
        tmp_path,
    )
    assert len(violations) == 2
    assert all(v.code == "ML001" for v in violations)
