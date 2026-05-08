"""Tests for ML102 — function returns a dict of primitive types."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes


def test_bare_dict_subscript_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> dict[str, str]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_capital_dict_flagged(tmp_path: Path) -> None:
    # typing.Dict (pre-3.9 style) with primitives is ML102.
    violations = check("from typing import Dict\ndef foo() -> Dict[str, str]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_typing_attribute_dict_flagged(tmp_path: Path) -> None:
    violations = check("import typing\ndef foo() -> typing.Dict[str, str]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_dict_union_none_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> dict[str, str] | None: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_none_union_dict_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> None | dict[str, str]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_optional_dict_flagged(tmp_path: Path) -> None:
    violations = check(
        "from typing import Optional\ndef foo() -> Optional[dict[str, str]]: ...\n",
        tmp_path,
    )
    assert codes(violations) == ["ML102"]


def test_union_dict_none_flagged(tmp_path: Path) -> None:
    violations = check(
        "from typing import Union\ndef foo() -> Union[dict[str, str], None]: ...\n",
        tmp_path,
    )
    assert codes(violations) == ["ML102"]


def test_chained_union_with_dict_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> str | int | dict[str, str]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_dict_message_suggests_dataclass(tmp_path: Path) -> None:
    violations = check("def foo() -> dict[str, str]: ...\n", tmp_path)
    assert len(violations) == 1
    assert "dataclass" in violations[0].message
    assert "NamedTuple" not in violations[0].message


def test_async_function_dict_flagged(tmp_path: Path) -> None:
    violations = check("async def foo() -> dict[str, str]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_list_return_deep_flagged(tmp_path: Path) -> None:
    # list[dict[...]] — the dict is caught even when nested inside list.
    violations = check("def foo() -> list[dict[str, str]]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_newtype_dict_ok(tmp_path: Path) -> None:
    # dict[UserId, Address] — non-primitive types are not flagged.
    violations = check("def foo() -> dict[UserId, Address]: ...\n", tmp_path)
    assert violations == []


def test_noqa_ml102_suppresses_dict(tmp_path: Path) -> None:
    violations = check("def foo() -> dict[str, str]: ...  # noqa: ML102\n", tmp_path)
    assert violations == []


def test_noqa_on_annotation_line_suppresses(tmp_path: Path) -> None:
    # For multi-line signatures the noqa may appear on the annotation line.
    violations = check(
        textwrap.dedent("""\
            def foo(
                x: str,
            ) -> dict[str, str]:  # noqa: ML102
                ...
        """),
        tmp_path,
    )
    assert violations == []


def test_noqa_wrong_code_does_not_suppress(tmp_path: Path) -> None:
    # ML103 noqa does not suppress an ML102 dict violation.
    violations = check("def foo() -> dict[str, str]: ...  # noqa: ML103\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_bare_noqa_does_not_suppress(tmp_path: Path) -> None:
    violations = check("def foo() -> dict[str, str]: ...  # noqa\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_typing_any_value_flagged(tmp_path: Path) -> None:
    # typing.Any is listed in _PRIMITIVE_NAMES, so dict[str, typing.Any] should be ML102.
    # This exercises _is_primitive() for an ast.Attribute node (qualified name).
    violations = check("import typing\ndef foo() -> dict[str, typing.Any]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]


def test_subscript_key_not_primitive_ok(tmp_path: Path) -> None:
    # dict[list[str], str] — the key type is ast.Subscript, which is not Name/Attribute/Constant.
    # _is_primitive() returns False (the fallback branch), so this is NOT ML102.
    violations = check("def foo() -> dict[list[str], str]: ...\n", tmp_path)
    assert violations == []


def test_none_constant_key_is_primitive_flagged(tmp_path: Path) -> None:
    # None as a dict key appears as ast.Constant(value=None) in the AST, not ast.Name('None').
    # _is_primitive() has a separate Constant branch for this case; dict[None, str] should
    # be ML102 because None is a primitive type per the rule.
    violations = check("def foo() -> dict[None, str]: ...\n", tmp_path)
    assert codes(violations) == ["ML102"]
