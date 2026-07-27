"""Tests for ML108 — no-op NewType self-cast."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from tests.conftest import check_project, codes

if TYPE_CHECKING:
    from pathlib import Path


def test_self_cast_on_parameter_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)

            def greet(user: UserId) -> None:
                print(UserId(user))
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML108"]
    assert "'UserId'" in violations[0].message


def test_self_cast_on_annotated_local_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)

            def make() -> None:
                user: UserId = UserId("abc")
                print(UserId(user))
        """),
    }
    violations = check_project(files, tmp_path)
    # Only the second call is a self-cast; the first wraps a plain literal.
    assert codes(violations) == ["ML108"]


def test_self_cast_on_attribute_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/models.py": textwrap.dedent("""\
            from typing import NamedTuple, NewType

            EventId = NewType("EventId", str)

            class Pending(NamedTuple):
                event_id: EventId
        """),
        "pkg/app.py": textwrap.dedent("""\
            from pkg.models import EventId, Pending

            def use(pending: Pending) -> None:
                print(EventId(pending.event_id))
        """),
    }
    violations = check_project(files, tmp_path)
    self_casts = [v for v in violations if v.code == "ML108"]
    assert len(self_casts) == 1
    assert self_casts[0].path.name == "app.py"


def test_self_cast_on_function_return_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)

            def find() -> UserId: ...

            def caller() -> None:
                print(UserId(find()))
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML108"]


def test_construction_from_literal_not_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)

            def make() -> UserId:
                return UserId("abc")
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_explicit_widening_not_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)

            def coerce(x: UserId) -> UserId:
                return UserId(str(x))
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_unresolvable_argument_not_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)

            def opaque():
                return "x"

            def caller() -> None:
                print(UserId(opaque()))
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_noqa_suppresses(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)

            def greet(user: UserId) -> None:
                print(UserId(user))  # noqa: ML108
        """),
    }
    violations = check_project(files, tmp_path)
    assert violations == []


def test_self_cast_on_for_loop_variable_flagged(tmp_path: Path) -> None:
    # The motivating casey_ai case: pending comes from a `for` loop over a typed list,
    # and we cast its attribute back to its already-known NewType.
    files = {
        "pkg/models.py": textwrap.dedent("""\
            from typing import NamedTuple, NewType

            EventId = NewType("EventId", str)

            class Pending(NamedTuple):
                event_id: EventId
        """),
        "pkg/app.py": textwrap.dedent("""\
            from pkg.models import EventId, Pending

            def process(pendings: list[Pending]) -> None:
                for pending in pendings:
                    use(EventId(pending.event_id))

            def use(_x: EventId) -> None: ...
        """),
    }
    violations = check_project(files, tmp_path)
    ml108 = [v for v in violations if v.code == "ML108"]
    assert len(ml108) == 1
    assert ml108[0].path.name == "app.py"


def test_self_cast_on_comprehension_target_flagged(tmp_path: Path) -> None:
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            EventId = NewType("EventId", str)

            def collect(events: list[EventId]) -> list[EventId]:
                return [EventId(eid) for eid in events]
        """),
    }
    violations = check_project(files, tmp_path)
    assert codes(violations) == ["ML108"]


def test_for_loop_over_class_iterable_attribute_flagged(tmp_path: Path) -> None:
    # for ev in events: where events: list[Pending] and Pending.event_id: EventId
    files = {
        "pkg/models.py": textwrap.dedent("""\
            from typing import NamedTuple, NewType

            EventId = NewType("EventId", str)

            class Pending(NamedTuple):
                event_id: EventId
        """),
        "pkg/app.py": textwrap.dedent("""\
            from pkg.models import EventId, Pending

            def process(events: list[Pending]) -> None:
                for ev in events:
                    _ = EventId(ev.event_id)
        """),
    }
    violations = check_project(files, tmp_path)
    ml108 = [v for v in violations if v.code == "ML108"]
    assert len(ml108) == 1


def test_different_newtypes_not_flagged_by_ml108(tmp_path: Path) -> None:
    # ML108 must not fire on a cross-cast — that's ML109's job.
    files = {
        "pkg/app.py": textwrap.dedent("""\
            from typing import NewType

            UserId = NewType("UserId", str)
            CustomerId = NewType("CustomerId", str)

            def caller(user: UserId) -> None:
                print(CustomerId(user))
        """),
    }
    violations = check_project(files, tmp_path)
    assert "ML108" not in [v.code for v in violations]
