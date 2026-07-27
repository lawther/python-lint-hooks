"""Tests for ML300 — class defined inside a function."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from tests.conftest import check, codes

if TYPE_CHECKING:
    from pathlib import Path


def test_class_inside_function_flagged(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            def outer() -> None:
                class Inner:
                    pass
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML300"]


def test_class_at_module_level_ok(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            class Foo:
                pass
        """),
        tmp_path,
    )
    assert violations == []


def test_class_inside_method_flagged(tmp_path: Path) -> None:
    # A class defined inside a method is still inside a function.
    violations = check(
        textwrap.dedent("""\
            class Outer:
                def method(self) -> None:
                    class Inner:
                        pass
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML300"]


def test_noqa_ml300_suppresses(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            def outer() -> None:
                class Inner:  # noqa: ML300
                    pass
        """),
        tmp_path,
    )
    assert violations == []
