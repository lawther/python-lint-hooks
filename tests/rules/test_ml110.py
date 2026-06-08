"""Tests for ML110 — function parameter has variable-length tuple annotation."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes

# ---------------------------------------------------------------------------
# Positive tests — the rule SHOULD fire
# ---------------------------------------------------------------------------


def test_variable_tuple_param_flagged(tmp_path: Path) -> None:
    violations = check("def f(row: tuple[object, ...]) -> None: ...\n", tmp_path)
    assert codes(violations) == ["ML110"]


def test_variable_tuple_typed_flagged(tmp_path: Path) -> None:
    # Any element type, not just object.
    violations = check("def f(scores: tuple[int, ...]) -> None: ...\n", tmp_path)
    assert codes(violations) == ["ML110"]


def test_keyword_only_param_flagged(tmp_path: Path) -> None:
    violations = check("def f(*, rows: tuple[str, ...]) -> None: ...\n", tmp_path)
    assert codes(violations) == ["ML110"]


def test_posonly_param_flagged(tmp_path: Path) -> None:
    violations = check("def f(rows: tuple[str, ...], /) -> None: ...\n", tmp_path)
    assert codes(violations) == ["ML110"]


def test_vararg_param_flagged(tmp_path: Path) -> None:
    # *args annotated as tuple[T, ...] is still a variable-length tuple annotation.
    violations = check("def f(*args: tuple[int, ...]) -> None: ...\n", tmp_path)
    assert codes(violations) == ["ML110"]


def test_kwargs_param_flagged(tmp_path: Path) -> None:
    # **kwargs annotated as tuple[T, ...] must also be caught; the kwarg node
    # is separate from args/vararg and is only appended when non-None.
    violations = check("def f(**kwargs: tuple[int, ...]) -> None: ...\n", tmp_path)
    assert codes(violations) == ["ML110"]


def test_async_function_flagged(tmp_path: Path) -> None:
    violations = check("async def f(row: tuple[object, ...]) -> None: ...\n", tmp_path)
    assert codes(violations) == ["ML110"]


# ---------------------------------------------------------------------------
# Negative tests — the rule MUST NOT fire
# ---------------------------------------------------------------------------


def test_sequence_param_ok(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from collections.abc import Sequence
        def f(row: Sequence[object]) -> None: ...
    """)
    violations = check(code, tmp_path)
    assert "ML110" not in codes(violations)


def test_list_param_ok(tmp_path: Path) -> None:
    violations = check("def f(items: list[int]) -> None: ...\n", tmp_path)
    assert "ML110" not in codes(violations)


def test_named_tuple_param_ok(tmp_path: Path) -> None:
    code = textwrap.dedent("""\
        from typing import NamedTuple
        class Row(NamedTuple):
            id: int
            name: str
        def f(row: Row) -> None: ...
    """)
    violations = check(code, tmp_path)
    assert "ML110" not in codes(violations)


def test_fixed_tuple_param_is_not_ml110(tmp_path: Path) -> None:
    # Fixed-length tuples are ML103, not ML110.
    violations = check("def f(point: tuple[int, int]) -> None: ...\n", tmp_path)
    assert "ML110" not in codes(violations)


def test_nested_function_not_flagged(tmp_path: Path) -> None:
    # Only top-level functions are checked; nested functions are skipped.
    code = textwrap.dedent("""\
        def outer() -> None:
            def inner(row: tuple[object, ...]) -> None: ...
    """)
    violations = check(code, tmp_path)
    assert "ML110" not in codes(violations)


def test_variable_tuple_return_is_ml104_not_ml110(tmp_path: Path) -> None:
    # Return-type variable tuples are ML104's domain, not ML110.
    violations = check("def f() -> tuple[int, ...]: ...\n", tmp_path)
    assert "ML110" not in codes(violations)
    assert "ML104" in codes(violations)


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


def test_noqa_ml110_suppresses(tmp_path: Path) -> None:
    violations = check(
        "def f(row: tuple[object, ...]) -> None: ...  # noqa: ML110\n",
        tmp_path,
    )
    assert "ML110" not in codes(violations)
