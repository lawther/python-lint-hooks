from __future__ import annotations

import textwrap
from pathlib import Path

from python_lint_hooks.checker import check_file


def _check(code: str, tmp_path: Path) -> list:
    path = tmp_path / "sample.py"
    path.write_text(code, encoding="utf-8")
    return check_file(path)


def _codes(violations: list) -> list[str]:
    return [v.code for v in violations]


# ---------------------------------------------------------------------------
# ML100 / ML102 — bare dict returns
# ---------------------------------------------------------------------------


def test_bare_dict_subscript_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML102"]


def test_bare_dict_no_subscript_flagged(tmp_path: Path) -> None:
    # Unparameterised dict is even less informative — still flagged.
    violations = _check("def foo() -> dict: ...\n", tmp_path)
    assert _codes(violations) == ["ML100"]


def test_capital_dict_flagged(tmp_path: Path) -> None:
    # typing.Dict (pre-3.9 style) with primitives is ML102.
    violations = _check("from typing import Dict\ndef foo() -> Dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML102"]


def test_typing_attribute_dict_flagged(tmp_path: Path) -> None:
    # typing.Dict used as a dotted attribute reference.
    violations = _check("import typing\ndef foo() -> typing.Dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML102"]


def test_dict_union_none_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> dict[str, str] | None: ...\n", tmp_path)
    assert _codes(violations) == ["ML102"]


def test_none_union_dict_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> None | dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML102"]


def test_optional_dict_flagged(tmp_path: Path) -> None:
    violations = _check(
        "from typing import Optional\ndef foo() -> Optional[dict[str, str]]: ...\n",
        tmp_path,
    )
    assert _codes(violations) == ["ML102"]


def test_union_dict_none_flagged(tmp_path: Path) -> None:
    violations = _check(
        "from typing import Union\ndef foo() -> Union[dict[str, str], None]: ...\n",
        tmp_path,
    )
    assert _codes(violations) == ["ML102"]


def test_chained_union_with_dict_flagged(tmp_path: Path) -> None:
    # str | int | dict — dict appears in a multi-way union.
    violations = _check("def foo() -> str | int | dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML102"]


def test_dict_message_suggests_dataclass(tmp_path: Path) -> None:
    # The message for a dict violation must mention dataclass, not NamedTuple.
    violations = _check("def foo() -> dict[str, str]: ...\n", tmp_path)
    assert len(violations) == 1
    assert "dataclass" in violations[0].message
    assert "NamedTuple" not in violations[0].message


# ---------------------------------------------------------------------------
# ML101 / ML103 — bare tuple returns
# ---------------------------------------------------------------------------


def test_bare_tuple_subscript_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> tuple[str, int]: ...\n", tmp_path)
    assert _codes(violations) == ["ML103"]


def test_bare_tuple_no_subscript_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> tuple: ...\n", tmp_path)
    assert _codes(violations) == ["ML101"]


def test_capital_tuple_flagged(tmp_path: Path) -> None:
    violations = _check("from typing import Tuple\ndef foo() -> Tuple[str, int]: ...\n", tmp_path)
    assert _codes(violations) == ["ML103"]


def test_typing_attribute_tuple_flagged(tmp_path: Path) -> None:
    violations = _check("import typing\ndef foo() -> typing.Tuple[str, int]: ...\n", tmp_path)
    assert _codes(violations) == ["ML103"]


def test_tuple_union_none_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> tuple[str, int] | None: ...\n", tmp_path)
    assert _codes(violations) == ["ML103"]


def test_optional_tuple_flagged(tmp_path: Path) -> None:
    violations = _check(
        "from typing import Optional\ndef foo() -> Optional[tuple[str, int]]: ...\n",
        tmp_path,
    )
    assert _codes(violations) == ["ML103"]


def test_tuple_message_suggests_namedtuple(tmp_path: Path) -> None:
    # The message for a tuple violation must mention NamedTuple, not dataclass.
    violations = _check("def foo() -> tuple[str, int]: ...\n", tmp_path)
    assert len(violations) == 1
    assert "NamedTuple" in violations[0].message
    assert "dataclass" not in violations[0].message


def test_async_function_dict_flagged(tmp_path: Path) -> None:
    violations = _check("async def foo() -> dict[str, str]: ...\n", tmp_path)
    assert _codes(violations) == ["ML102"]


def test_async_function_tuple_flagged(tmp_path: Path) -> None:
    violations = _check("async def foo() -> tuple[str, int]: ...\n", tmp_path)
    assert _codes(violations) == ["ML103"]


# ---------------------------------------------------------------------------
# ML100 - ML104 — cases that must NOT be flagged (NewType exception)
# ---------------------------------------------------------------------------


def test_str_return_ok(tmp_path: Path) -> None:
    violations = _check("def foo() -> str: ...\n", tmp_path)
    assert violations == []


def test_list_return_deep_flagged(tmp_path: Path) -> None:
    # list[dict[...]] — the return type is a list, but it contains a dict of primitives.
    # Now it is caught (deep enforcement).
    violations = _check("def foo() -> list[dict[str, str]]: ...\n", tmp_path)
    assert _codes(violations) == ["ML102"]


def test_newtype_dict_ok(tmp_path: Path) -> None:
    # dict[UserId, Address] — non-primitive types are allowed.
    violations = _check("def foo() -> dict[UserId, Address]: ...\n", tmp_path)
    assert violations == []


def test_named_tuple_return_ok(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            from typing import NamedTuple

            class User(NamedTuple):
                id: int
                name: str

            def get_user() -> User: ...
        """),
        tmp_path,
    )
    assert violations == []


def test_dataclass_return_ok(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            from dataclasses import dataclass

            @dataclass(frozen=True)
            class User:
                id: int
                name: str

            def get_user() -> User: ...
        """),
        tmp_path,
    )
    assert violations == []


# ---------------------------------------------------------------------------
# ML104 — Variable-length tuples
# ---------------------------------------------------------------------------


def test_variable_length_tuple_flagged(tmp_path: Path) -> None:
    violations = _check("def foo() -> tuple[int, ...]: ...\n", tmp_path)
    assert _codes(violations) == ["ML104"]


# ---------------------------------------------------------------------------
# ML300 — class defined inside a function
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
    assert _codes(violations) == ["ML300"]


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
    assert _codes(violations) == ["ML300"]


def test_noqa_ml300_suppresses(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            def outer() -> None:
                class Inner:  # noqa: ML300
                    pass
        """),
        tmp_path,
    )
    assert violations == []


# ---------------------------------------------------------------------------
# Mixed violations
# ---------------------------------------------------------------------------


def test_dict_and_tuple_violations_separate_codes(tmp_path: Path) -> None:
    # Primitive dict gets ML102, fixed tuple gets ML103.
    violations = _check(
        textwrap.dedent("""\
            def foo() -> dict[str, str]: ...
            def bar() -> tuple[int, str]: ...
        """),
        tmp_path,
    )
    assert _codes(violations) == ["ML102", "ML103"]


def test_multiple_dict_violations(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            def foo() -> dict[str, str]: ...
            def bar() -> dict[str, int]: ...
        """),
        tmp_path,
    )
    assert len(violations) == 2
    assert all(v.code == "ML102" for v in violations)


# ---------------------------------------------------------------------------
# ML200: Frozen Dataclasses
# ---------------------------------------------------------------------------


def test_dataclass_not_frozen(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert _codes(violations) == ["ML200"]


def test_dataclass_frozen_explicit(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert _codes(violations) == []


def test_dataclass_frozen_false(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass(frozen=False)
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert _codes(violations) == ["ML200"]


def test_dataclass_attr_style(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert _codes(violations) == ["ML200"]


def test_dataclass_noqa(tmp_path: Path) -> None:
    violations = _check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass  # noqa: ML200
            class Mutable:
                x: int
        """),
        tmp_path,
    )
    assert _codes(violations) == []


# ---------------------------------------------------------------------------
# Suppression via noqa on return annotations
# ---------------------------------------------------------------------------


def test_noqa_on_annotation_line_suppresses(tmp_path: Path) -> None:
    # For multi-line signatures the noqa may appear on the annotation line.
    violations = _check(
        textwrap.dedent("""\
            def foo(
                x: str,
            ) -> dict[str, str]:  # noqa: ML102
                ...
        """),
        tmp_path,
    )
    assert violations == []


def test_noqa_ml102_suppresses_dict(tmp_path: Path) -> None:
    violations = _check("def foo() -> dict[str, str]: ...  # noqa: ML102\n", tmp_path)
    assert violations == []


def test_noqa_ml103_suppresses_tuple(tmp_path: Path) -> None:
    violations = _check("def foo() -> tuple[str, int]: ...  # noqa: ML103\n", tmp_path)
    assert violations == []


def test_noqa_wrong_code_does_not_suppress(tmp_path: Path) -> None:
    # ML103 noqa does not suppress an ML102 dict violation.
    violations = _check("def foo() -> dict[str, str]: ...  # noqa: ML103\n", tmp_path)
    assert _codes(violations) == ["ML102"]
