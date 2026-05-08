"""Tests for ML200 — dataclass is not frozen."""

from __future__ import annotations

import textwrap
from pathlib import Path

from tests.conftest import check, codes


def test_dataclass_not_frozen(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML200"]


def test_dataclass_frozen_explicit_ok(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == []


def test_dataclass_frozen_false_flagged(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass(frozen=False)
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML200"]


def test_dataclass_attr_style_flagged(tmp_path: Path) -> None:
    # @dataclasses.dataclass (attribute access style) is also caught.
    violations = check(
        textwrap.dedent("""\
            import dataclasses
            @dataclasses.dataclass
            class Point:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML200"]


def test_subscript_decorator_before_dataclass_flagged(tmp_path: Path) -> None:
    # A subscript-style decorator (DECS[0]) is neither ast.Name nor ast.Attribute,
    # so _is_dataclass_decorator() falls through to return False (line 22).
    # The loop must then continue (line 45) and still detect the @dataclass below it.
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            DECS = [None]
            @DECS[0]
            @dataclass
            class Foo:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML200"]


def test_aliased_module_decorator_flagged(tmp_path: Path) -> None:
    # @dc.dataclass — aliased import. The rule checks node.value.id == "dataclasses"
    # literally, so this may be a false negative.
    violations = check(
        textwrap.dedent("""\
            import dataclasses as dc
            @dc.dataclass
            class Foo:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == ["ML200"]


def test_noqa_ml200_suppresses(tmp_path: Path) -> None:
    violations = check(
        textwrap.dedent("""\
            from dataclasses import dataclass
            @dataclass  # noqa: ML200
            class Mutable:
                x: int
        """),
        tmp_path,
    )
    assert codes(violations) == []
