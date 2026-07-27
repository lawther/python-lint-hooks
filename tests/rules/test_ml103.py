"""Tests for ML103 — function returns a fixed-length typed tuple."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import check, codes

if TYPE_CHECKING:
    from pathlib import Path


def test_bare_tuple_subscript_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple[str, int]: ...\n", tmp_path)
    assert codes(violations) == ["ML103"]


def test_capital_tuple_flagged(tmp_path: Path) -> None:
    violations = check("from typing import Tuple\ndef foo() -> Tuple[str, int]: ...\n", tmp_path)
    assert codes(violations) == ["ML103"]


def test_typing_attribute_tuple_flagged(tmp_path: Path) -> None:
    violations = check("import typing\ndef foo() -> typing.Tuple[str, int]: ...\n", tmp_path)
    assert codes(violations) == ["ML103"]


def test_tuple_union_none_flagged(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple[str, int] | None: ...\n", tmp_path)
    assert codes(violations) == ["ML103"]


def test_optional_tuple_flagged(tmp_path: Path) -> None:
    violations = check(
        "from typing import Optional\ndef foo() -> Optional[tuple[str, int]]: ...\n",
        tmp_path,
    )
    assert codes(violations) == ["ML103"]


def test_tuple_message_suggests_namedtuple(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple[str, int]: ...\n", tmp_path)
    assert len(violations) == 1
    assert "NamedTuple" in violations[0].message
    assert "dataclass" not in violations[0].message


def test_async_function_tuple_flagged(tmp_path: Path) -> None:
    violations = check("async def foo() -> tuple[str, int]: ...\n", tmp_path)
    assert codes(violations) == ["ML103"]


def test_named_tuple_return_ok(tmp_path: Path) -> None:
    import textwrap

    violations = check(
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


def test_noqa_ml103_suppresses_tuple(tmp_path: Path) -> None:
    violations = check("def foo() -> tuple[str, int]: ...  # noqa: ML103\n", tmp_path)
    assert violations == []
